from __future__ import annotations
import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

class AIProviderError(Exception):
    """Base exception for AI provider failures."""
    pass

class AIProviderUnavailableError(AIProviderError):
    """Provider API key missing or service temporarily offline."""
    pass

class AIProviderTimeoutError(AIProviderError):
    """Provider request exceeded timeout threshold."""
    pass

class AIProviderRateLimitError(AIProviderError):
    """Upstream provider rate limit reached."""
    pass

class BaseAIProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str,
        thinking_level: str = "medium",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate response from provider.

        Returns dict:
            text: str
            prompt_tokens: int
            completion_tokens: int
            total_tokens: int
            model: str
            provider: str
        """
        pass

class GeminiProvider(BaseAIProvider):
    """Production Google Gemini provider using official v1beta REST endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        self.model = (model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()
        self.timeout_seconds = float(timeout_seconds or os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0"))
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _get_thinking_level(self, level: str) -> str:
        lvl = (level or "medium").lower()
        if lvl in ("low", "medium", "high"):
            return lvl
        return "medium"

    def get_sanitized_request_payload(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str,
        thinking_level: str = "medium"
    ) -> Dict[str, Any]:
        """Return safe, sanitized JSON representation of outgoing request without credentials."""
        chosen_level = self._get_thinking_level(thinking_level)
        return {
            "model": self.model,
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": self._format_contents(messages),
            "generationConfig": {
                "maxOutputTokens": 2048,
                "thinkingConfig": {
                    "thinkingLevel": chosen_level
                }
            }
        }

    def _format_contents(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Map role: assistant -> model for Gemini
            gemini_role = "model" if role == "assistant" else "user"
            content_text = msg.get("content", "")
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content_text}]
            })
        return contents

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str,
        thinking_level: str = "medium",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise AIProviderUnavailableError("GEMINI_API_KEY is not configured on server.")

        endpoint = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        chosen_level = self._get_thinking_level(thinking_level)
        contents = self._format_contents(messages)

        # Gemini 3.8 official contract: clean generationConfig with thinkingLevel enum
        generation_config: Dict[str, Any] = {
            "maxOutputTokens": 2048,
            "thinkingConfig": {
                "thinkingLevel": chosen_level
            }
        }

        payload: Dict[str, Any] = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": generation_config
        }

        logger.debug("Dispatched Gemini request: model=%s, thinking_level=%s", self.model, chosen_level)

        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(endpoint, params=params, json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("Gemini API request timed out after %ss: %s", self.timeout_seconds, exc)
                raise AIProviderTimeoutError(f"Gemini API timed out after {self.timeout_seconds}s.") from exc
            except httpx.RequestError as exc:
                logger.error("Gemini network error: %s", exc)
                raise AIProviderUnavailableError(f"Network error connecting to Gemini API: {exc}") from exc

        if response.status_code == 429:
            raise AIProviderRateLimitError("Gemini upstream rate limit reached. Please try again in a moment.")
        elif response.status_code >= 500:
            raise AIProviderUnavailableError(f"Gemini service unavailable (HTTP {response.status_code}).")
        elif response.status_code != 200:
            # Fallback attempt if thinkingConfig was rejected
            if "thinkingConfig" in generation_config and response.status_code == 400:
                payload["generationConfig"].pop("thinkingConfig", None)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(endpoint, params=params, json=payload)
                if response.status_code != 200:
                    raise AIProviderError(f"Gemini API returned error {response.status_code}: {response.text}")
            else:
                raise AIProviderError(f"Gemini API returned error {response.status_code}: {response.text}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise AIProviderError("Gemini returned no candidates in response.")

        candidate = candidates[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])

        # Extract only user-facing answer text; do not expose internal thinking/reasoning
        text_parts = []
        for p in parts:
            if "text" in p and not p.get("thought", False):
                text_parts.append(p["text"])

        output_text = "\n".join(text_parts).strip()
        if not output_text and parts and "text" in parts[0]:
            output_text = parts[0]["text"].strip()

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

        return {
            "text": output_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": self.model,
            "provider": "gemini"
        }

_provider_instance: Optional[BaseAIProvider] = None

def get_ai_provider() -> BaseAIProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = GeminiProvider()
    return _provider_instance
