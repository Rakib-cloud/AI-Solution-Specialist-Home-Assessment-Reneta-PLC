from __future__ import annotations

import json
import re

from app.config import Settings


class LLMError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise LLMError("Add OPENAI_API_KEY to the .env file and restart the app.", 400)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("The OpenAI package is not installed. Run pip install -r requirements.txt.") from exc
        kwargs = {"api_key": settings.openai_api_key, "timeout": 60}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self._client = OpenAI(**kwargs)
        self._model = settings.openai_model

    def complete_json(self, system: str, user: str) -> dict:
        try:
            return self._request(system, user, json_mode=True)
        except LLMError:
            raise
        except Exception as exc:
            if "response_format" in str(exc).lower() or "json_object" in str(exc).lower():
                return self._request(system, user, json_mode=False)
            raise LLMError(_friendly(exc)) from exc

    def _request(self, system: str, user: str, json_mode: bool) -> dict:
        kwargs = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(_friendly(exc)) from exc
        content = response.choices[0].message.content or ""
        return _parse_json(content)


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise LLMError("The model did not return JSON. Try the question again.")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("The model did not return JSON. Try the question again.") from exc
    if not isinstance(parsed, dict):
        raise LLMError("The model did not return a JSON object.")
    return parsed


def _friendly(exc: Exception) -> str:
    name = exc.__class__.__name__
    if "Authentication" in name or "401" in str(exc):
        return "The API key was rejected. Check OPENAI_API_KEY in the .env file."
    if "RateLimit" in name or "429" in str(exc):
        return "The model provider rate-limited the request. Wait a moment and try again."
    if "APIConnection" in name or "ConnectError" in name or "Timeout" in name:
        return "Could not reach the model provider. Check the network and OPENAI_BASE_URL."
    return "The model request failed. Check the API key, model name, and base URL."
