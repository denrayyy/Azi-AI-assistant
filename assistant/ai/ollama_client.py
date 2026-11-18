"""Ollama API client for local model inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import requests


@dataclass(frozen=True)
class ChatMessage:
    """Represents a single chat message for Ollama."""

    role: str
    content: str


class OllamaClient:
    """Minimal Ollama chat client for local models."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._session = requests.Session()
        self._session.trust_env = False

    def chat(self, messages: Iterable[ChatMessage]) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }

        try:
            response = self._session.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            if response.status_code == 404:
                return self._generate_fallback(messages)
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if hasattr(exc, "response") and exc.response is not None:
                detail = f" Response: {exc.response.text.strip()}"
            return f"[Ollama error] {exc}{detail}"

        data = response.json()
        return data.get("message", {}).get("content", "") or "[No response]"

    def _generate_fallback(self, messages: Iterable[ChatMessage]) -> str:
        prompt = "\n".join(
            f"{message.role.capitalize()}: {message.content}" for message in messages
        )
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = self._session.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if hasattr(exc, "response") and exc.response is not None:
                detail = f" Response: {exc.response.text.strip()}"
            return f"[Ollama error] {exc}{detail}"

        data = response.json()
        return data.get("response", "") or "[No response]"

    def build_messages(self, system_prompt: str, history: List[ChatMessage]) -> List[ChatMessage]:
        messages = [ChatMessage("system", system_prompt)]
        messages.extend(history)
        return messages
