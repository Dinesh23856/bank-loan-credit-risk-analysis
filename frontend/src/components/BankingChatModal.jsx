import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  X,
  Send,
  Sparkles,
  RefreshCw,
  Trash2,
  ChevronRight,
  AlertCircle,
  FileText,
  ShieldCheck,
  Minimize2,
  PlusCircle
} from "lucide-react";
import {
  chatSend,
  chatConversations,
  chatConversation,
  chatDeleteConversation
} from "../api/client";
import SafeMarkdown from "./SafeMarkdown";

const QUICK_PROMPTS = [
  "Explain my loan prediction",
  "Why was my application rejected?",
  "What factors affected my credit score?",
  "Explain my credit risk",
  "What can I improve in my financial profile?"
];

export default function BankingChatModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [appContextId, setAppContextId] = useState(null);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);

  const messagesEndRef = useRef(null);

  // Listen for custom trigger from ApplicationDetail page
  useEffect(() => {
    const handleOpen = (e) => {
      const targetAppId = e.detail?.applicationId;
      if (targetAppId) {
        setAppContextId(targetAppId);
      }
      setIsOpen(true);
    };
    window.addEventListener("open-banking-assistant", handleOpen);
    return () => window.removeEventListener("open-banking-assistant", handleOpen);
  }, []);

  // Fetch conversations when opening
  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const loadConversations = async () => {
    try {
      const list = await chatConversations();
      setConversations(list || []);
    } catch (e) {
      console.warn("Could not load conversations:", e.message);
    }
  };

  const handleSelectConversation = async (convId) => {
    setError("");
    setLoading(true);
    try {
      const detail = await chatConversation(convId);
      setActiveConvId(convId);
      setAppContextId(detail.application_id || null);
      setMessages(
        (detail.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources || [],
          created_at: m.created_at
        }))
      );
      setShowHistoryDrawer(false);
    } catch (e) {
      setError(e.message || "Failed to load conversation history.");
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    setActiveConvId(null);
    setMessages([]);
    setError("");
    setShowHistoryDrawer(false);
  };

  const handleDeleteConversation = async (convId, e) => {
    e.stopPropagation();
    try {
      await chatDeleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        handleNewConversation();
      }
    } catch (err) {
      alert(err.message || "Failed to delete conversation.");
    }
  };

  const handleSend = async (textToSend = null) => {
    const msg = (textToSend || inputMessage).trim();
    if (!msg || loading) return;

    setError("");
    setInputMessage("");

    // Optimistically append user message
    const userMsgObj = { role: "user", content: msg, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsgObj]);
    setLoading(true);

    try {
      const payload = {
        message: msg,
        conversation_id: activeConvId || null,
        application_id: appContextId ? parseInt(appContextId, 10) : null
      };

      const res = await chatSend(payload);

      if (!activeConvId && res.conversation_id) {
        setActiveConvId(res.conversation_id);
        loadConversations();
      }

      const assistantMsgObj = {
        role: "assistant",
        content: res.message,
        sources: res.sources || [],
        degraded: res.degraded,
        created_at: new Date().toISOString()
      };

      setMessages((prev) => [...prev, assistantMsgObj]);
    } catch (e) {
      setError(e.message || "Unable to receive AI response. Please retry.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Open Banking AI Assistant"
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "56px",
          height: "56px",
          borderRadius: "50%",
          background: "linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)",
          color: "#ffffff",
          border: "none",
          boxShadow: "0 8px 24px rgba(37, 99, 235, 0.4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          zIndex: 9999,
          transition: "transform 0.2s ease, box-shadow 0.2s ease"
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.05)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1.0)")}
      >
        {isOpen ? <X size={26} /> : <Sparkles size={26} />}
      </button>

      {/* Slide-in Assistant Panel */}
      {isOpen && (
        <div
          role="dialog"
          aria-labelledby="assistant-title"
          style={{
            position: "fixed",
            bottom: "90px",
            right: "24px",
            width: "420px",
            maxWidth: "calc(100vw - 32px)",
            height: "620px",
            maxHeight: "calc(100vh - 120px)",
            background: "#ffffff",
            borderRadius: "16px",
            boxShadow: "0 20px 40px rgba(15, 23, 42, 0.2), 0 0 0 1px rgba(15, 23, 42, 0.08)",
            display: "flex",
            flexDirection: "column",
            zIndex: 9999,
            overflow: "hidden",
            fontFamily: "inherit"
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 16px",
              background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#ffffff"
                }}
              >
                <Sparkles size={18} />
              </div>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span id="assistant-title" style={{ fontSize: "14px", fontWeight: "600" }}>
                    Banking AI Assistant
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      background: "rgba(59, 130, 246, 0.25)",
                      color: "#93c5fd",
                      padding: "1px 6px",
                      borderRadius: "10px",
                      fontWeight: "500"
                    }}
                  >
                    Gemini 3.5 Flash Lite
                  </span>
                </div>
                <div style={{ fontSize: "11px", color: "#94a3b8", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981", display: "inline-block" }}></span>
                  Grounded in ML Ground Truth
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <button
                onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
                title="Conversations History"
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "none",
                  color: "#cbd5e1",
                  borderRadius: "6px",
                  padding: "6px",
                  cursor: "pointer"
                }}
              >
                <MessageSquare size={16} />
              </button>
              <button
                onClick={handleNewConversation}
                title="New Chat"
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "none",
                  color: "#cbd5e1",
                  borderRadius: "6px",
                  padding: "6px",
                  cursor: "pointer"
                }}
              >
                <PlusCircle size={16} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                title="Minimize"
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "none",
                  color: "#cbd5e1",
                  borderRadius: "6px",
                  padding: "6px",
                  cursor: "pointer"
                }}
              >
                <Minimize2 size={16} />
              </button>
            </div>
          </div>

          {/* Application Context Banner */}
          {appContextId && (
            <div
              style={{
                padding: "8px 14px",
                background: "#f0f9ff",
                borderBottom: "1px solid #e0f2fe",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "12px",
                color: "#0369a1"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <FileText size={14} />
                <span>
                  Active Context: <strong>Application #{appContextId}</strong>
                </span>
              </div>
              <button
                onClick={() => setAppContextId(null)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#0369a1",
                  cursor: "pointer",
                  fontSize: "11px",
                  textDecoration: "underline"
                }}
              >
                Clear
              </button>
            </div>
          )}

          {/* History Drawer Overlay */}
          {showHistoryDrawer && (
            <div
              style={{
                position: "absolute",
                top: "60px",
                bottom: "0",
                left: "0",
                right: "0",
                background: "#ffffff",
                zIndex: 10,
                display: "flex",
                flexDirection: "column",
                padding: "16px",
                boxShadow: "inset 0 4px 6px rgba(0,0,0,0.05)"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <h4 style={{ margin: 0, fontSize: "14px", color: "#0f172a" }}>Your Conversations</h4>
                <button
                  onClick={() => setShowHistoryDrawer(false)}
                  style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer" }}
                >
                  <X size={18} />
                </button>
              </div>

              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
                {conversations.length === 0 ? (
                  <p style={{ fontSize: "13px", color: "#94a3b8", textAlign: "center", marginTop: "20px" }}>
                    No previous conversations yet.
                  </p>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      style={{
                        padding: "10px 12px",
                        borderRadius: "8px",
                        background: conv.id === activeConvId ? "#eff6ff" : "#f8fafc",
                        border: conv.id === activeConvId ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center"
                      }}
                    >
                      <div style={{ overflow: "hidden" }}>
                        <div style={{ fontSize: "13px", fontWeight: "500", color: "#0f172a", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {conv.title || "Conversation"}
                        </div>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>
                          {new Date(conv.updated_at).toLocaleDateString()}
                        </div>
                      </div>
                      <button
                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                        title="Delete conversation"
                        style={{
                          background: "none",
                          border: "none",
                          color: "#94a3b8",
                          cursor: "pointer",
                          padding: "4px"
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Messages Container */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              background: "#fafafa"
            }}
          >
            {messages.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px 8px" }}>
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "50%",
                    background: "#eff6ff",
                    color: "#2563eb",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 12px"
                  }}
                >
                  <Sparkles size={24} />
                </div>
                <h4 style={{ margin: "0 0 6px", fontSize: "15px", color: "#0f172a" }}>
                  How can I help you today?
                </h4>
                <p style={{ margin: "0 0 16px", fontSize: "12px", color: "#64748b", lineHeight: "1.4" }}>
                  Ask about your loan approval, credit score factors, TreeSHAP force values, or actionable financial recourse.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {QUICK_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(prompt)}
                      style={{
                        padding: "8px 12px",
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: "8px",
                        fontSize: "12px",
                        color: "#334155",
                        textAlign: "left",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        transition: "border-color 0.15s ease"
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#93c5fd")}
                      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e2e8f0")}
                    >
                      <span>{prompt}</span>
                      <ChevronRight size={14} color="#94a3b8" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, index) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: isUser ? "flex-end" : "flex-start"
                  }}
                >
                  <div
                    style={{
                      maxWidth: "85%",
                      padding: "10px 14px",
                      borderRadius: isUser ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                      background: isUser ? "#2563eb" : "#ffffff",
                      color: isUser ? "#ffffff" : "#0f172a",
                      boxShadow: isUser ? "0 2px 4px rgba(37, 99, 235, 0.2)" : "0 1px 3px rgba(0,0,0,0.06)",
                      border: isUser ? "none" : "1px solid #e2e8f0",
                      fontSize: "13px"
                    }}
                  >
                    {isUser ? (
                      <div style={{ whiteSpace: "pre-wrap", lineHeight: "1.4" }}>{msg.content}</div>
                    ) : (
                      <>
                        <SafeMarkdown content={msg.content} />

                        {/* Degraded offline badge */}
                        {msg.degraded && (
                          <div
                            style={{
                              marginTop: "8px",
                              padding: "4px 8px",
                              background: "#fffbeb",
                              border: "1px solid #fef3c7",
                              borderRadius: "4px",
                              fontSize: "11px",
                              color: "#b45309",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px"
                            }}
                          >
                            <AlertCircle size={12} />
                            <span>Verified Local Ground Truth Narrative</span>
                          </div>
                        )}

                        {/* Sources Pill Bar */}
                        {msg.sources && msg.sources.length > 0 && (
                          <div
                            style={{
                              marginTop: "8px",
                              paddingTop: "6px",
                              borderTop: "1px solid #f1f5f9",
                              display: "flex",
                              flexWrap: "wrap",
                              gap: "4px"
                            }}
                          >
                            {msg.sources.map((src, sIdx) => (
                              <span
                                key={sIdx}
                                style={{
                                  fontSize: "10px",
                                  background: "#f1f5f9",
                                  color: "#475569",
                                  padding: "2px 6px",
                                  borderRadius: "4px",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "3px"
                                }}
                              >
                                <ShieldCheck size={10} color="#059669" />
                                {src}
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", padding: "8px 12px", background: "#ffffff", borderRadius: "12px", width: "fit-content", border: "1px solid #e2e8f0" }}>
                <RefreshCw size={14} className="spin" color="#2563eb" />
                <span style={{ fontSize: "12px", color: "#64748b" }}>Analyzing credit profile...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error Banner */}
          {error && (
            <div
              style={{
                padding: "8px 14px",
                background: "#fef2f2",
                borderTop: "1px solid #fee2e2",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "12px",
                color: "#b91c1c"
              }}
            >
              <span>{error}</span>
              <button
                onClick={() => handleSend()}
                style={{
                  background: "#b91c1c",
                  color: "#ffffff",
                  border: "none",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "11px"
                }}
              >
                Retry
              </button>
            </div>
          )}

          {/* Input Area */}
          <div
            style={{
              padding: "12px 14px",
              background: "#ffffff",
              borderTop: "1px solid #e2e8f0",
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            <input
              type="text"
              placeholder="Ask about predictions, SHAP factors..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={2000}
              disabled={loading}
              style={{
                flex: 1,
                padding: "10px 14px",
                borderRadius: "20px",
                border: "1px solid #cbd5e1",
                fontSize: "13px",
                outline: "none"
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !inputMessage.trim()}
              aria-label="Send message"
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "50%",
                background: inputMessage.trim() && !loading ? "#2563eb" : "#94a3b8",
                color: "#ffffff",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: inputMessage.trim() && !loading ? "pointer" : "default"
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
