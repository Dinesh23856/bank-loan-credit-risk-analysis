import React from "react";

/**
 * Safe, zero-dependency React Markdown Renderer.
 * Parses markdown into native React Virtual DOM elements without dangerouslySetInnerHTML.
 * React natively escapes all text node values, preventing any XSS/injection.
 */
export default function SafeMarkdown({ content = "" }) {
  if (!content) return null;

  // Split into block elements by double newlines or single newlines
  const lines = content.split("\n");
  const elements = [];
  let currentList = [];
  let inCodeBlock = false;
  let codeBlockLines = [];

  const renderInline = (text) => {
    // Replace markdown bold, italic, and code safely
    // Split by inline code first
    const codeParts = text.split(/(`[^`]+`)/g);
    return codeParts.map((part, idx) => {
      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return (
          <code
            key={idx}
            style={{
              background: "#f1f5f9",
              padding: "2px 6px",
              borderRadius: "4px",
              fontSize: "12px",
              fontFamily: "monospace",
              color: "#0f172a"
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      // Handle bold **text**
      const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
      return boldParts.map((bPart, bIdx) => {
        if (bPart.startsWith("**") && bPart.endsWith("**") && bPart.length >= 4) {
          return <strong key={`${idx}-${bIdx}`} style={{ fontWeight: "600", color: "#0f172a" }}>{bPart.slice(2, -2)}</strong>;
        }

        // Handle italic *text*
        const italicParts = bPart.split(/(\*[^*]+\*)/g);
        return italicParts.map((iPart, iIdx) => {
          if (iPart.startsWith("*") && iPart.endsWith("*") && iPart.length >= 2) {
            return <em key={`${idx}-${bIdx}-${iIdx}`}>{iPart.slice(1, -1)}</em>;
          }
          return iPart;
        });
      });
    });
  };

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} style={{ margin: "6px 0", paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px" }}>
          {currentList.map((item, liIdx) => (
            <li key={liIdx} style={{ fontSize: "13px", lineHeight: "1.5", color: "#334155" }}>
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Code block toggle
    if (trimmed.startsWith("```")) {
      flushList();
      if (inCodeBlock) {
        elements.push(
          <pre
            key={`pre-${elements.length}`}
            style={{
              background: "#0f172a",
              color: "#f8fafc",
              padding: "10px 12px",
              borderRadius: "6px",
              fontSize: "12px",
              overflowX: "auto",
              fontFamily: "monospace",
              margin: "6px 0"
            }}
          >
            <code>{codeBlockLines.join("\n")}</code>
          </pre>
        );
        codeBlockLines = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(rawLine);
      continue;
    }

    // Unordered list item (- or *)
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      currentList.push(trimmed.slice(2));
      continue;
    }

    // Numbered list item (1. 2. etc)
    if (/^\d+\.\s+/.test(trimmed)) {
      currentList.push(trimmed.replace(/^\d+\.\s+/, ""));
      continue;
    }

    flushList();

    if (!trimmed) {
      continue;
    }

    // Header 3 (###) or Header 2 (##)
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={`h-${elements.length}`} style={{ margin: "10px 0 4px", fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>
          {renderInline(trimmed.slice(4))}
        </h4>
      );
    } else if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={`h-${elements.length}`} style={{ margin: "12px 0 6px", fontSize: "15px", fontWeight: "700", color: "#0f172a" }}>
          {renderInline(trimmed.slice(3))}
        </h3>
      );
    } else if (trimmed.startsWith("# ")) {
      elements.push(
        <h2 key={`h-${elements.length}`} style={{ margin: "14px 0 6px", fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
          {renderInline(trimmed.slice(2))}
        </h2>
      );
    } else {
      elements.push(
        <p key={`p-${elements.length}`} style={{ margin: "4px 0", fontSize: "13px", lineHeight: "1.55", color: "#334155" }}>
          {renderInline(trimmed)}
        </p>
      );
    }
  }

  flushList();

  return <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>{elements}</div>;
}
