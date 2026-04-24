from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from .settings import AgentSettings


class OpenAIClientError(RuntimeError):
    pass


def supports_reasoning(model_name: str) -> bool:
    return model_name.startswith("o") or model_name.startswith("gpt-5")


def normalize_reasoning_effort(thinking: str) -> str | None:
    value = (thinking or "off").lower().replace("-", "_")
    if value in {"off", "none", "false"}:
        return None
    if value in {"extra_high", "xhigh", "very_high"}:
        return "high"
    if value in {"low", "medium", "high"}:
        return value
    return "high"


def extract_json_block(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        json.loads(stripped)
        return stripped
    except Exception:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    raise ValueError("No JSON object found in model output")


def extract_response_text(payload: dict[str, Any]) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"].strip()
    status = payload.get("status")
    incomplete = payload.get("incomplete_details")
    output_types = [item.get("type") for item in payload.get("output", []) if isinstance(item, dict)]
    raise ValueError(
        f"No output_text found in OpenAI response (status={status}, incomplete={incomplete}, output_types={output_types})"
    )


class OpenAIResponsesClient:
    def __init__(self, api_key: str, *, timeout_seconds: int = 90, max_attempts: int = 3) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return min(12.0, 1.5 * (2 ** max(0, attempt - 1)))

    @staticmethod
    def _is_retryable_http(code: int) -> bool:
        return code in {408, 409, 429, 500, 502, 503, 504}

    def call_json(self, *, system: str, user: str, settings: AgentSettings | dict[str, Any]) -> dict[str, Any]:
        if not isinstance(settings, AgentSettings):
            settings = AgentSettings(
                name=str(settings.get("name", "agent")),
                role=str(settings.get("role", "")),
                provider=str(settings.get("provider", "openai")),
                model=str(settings.get("model", "gpt-4o")),
                temperature=float(settings.get("temperature", 0.0)),
                thinking=str(settings.get("thinking", "off")),
                max_output_tokens=int(settings.get("max_output_tokens", 4096)),
                response_format=str(settings.get("response_format", "json_object")),
            )

        payload: dict[str, Any] = {
            "model": settings.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": user}]},
            ],
            "temperature": settings.temperature,
            "max_output_tokens": settings.max_output_tokens,
        }
        effort = normalize_reasoning_effort(settings.thinking)
        if effort and supports_reasoning(settings.model):
            payload["reasoning"] = {"effort": effort}

        request_payload = dict(payload)
        notes: list[str] = []
        temperature_omitted = False
        max_tokens_omitted = False

        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = self._post(request_payload)
                text = extract_response_text(raw)
                parsed = json.loads(extract_json_block(text))
                return {
                    "parsed": parsed,
                    "text": text,
                    "raw": raw,
                    "retry_count": attempt - 1,
                    "temperature_omitted": temperature_omitted,
                    "max_tokens_omitted": max_tokens_omitted,
                    "attempt_notes": notes,
                }
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                try:
                    error_payload = json.loads(detail)
                except Exception:
                    error_payload = None
                error_info = (error_payload or {}).get("error", {}) if isinstance(error_payload, dict) else {}
                message = str(error_info.get("message", detail))
                param = error_info.get("param")

                if exc.code == 400 and "temperature" in request_payload and (
                    param == "temperature" or "temperature" in message.lower()
                ):
                    request_payload = dict(request_payload)
                    request_payload.pop("temperature", None)
                    temperature_omitted = True
                    notes.append("temperature parameter removed and request retried")
                    continue
                if exc.code == 400 and "max_output_tokens" in request_payload and (
                    param == "max_output_tokens" or "max_output_tokens" in message.lower()
                ):
                    request_payload = dict(request_payload)
                    request_payload.pop("max_output_tokens", None)
                    max_tokens_omitted = True
                    notes.append("max_output_tokens parameter removed and request retried")
                    continue
                if self._is_retryable_http(exc.code) and attempt < self.max_attempts:
                    notes.append(f"transient OpenAI HTTP {exc.code} on attempt {attempt}: retrying")
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise OpenAIClientError(f"OpenAI HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                if attempt < self.max_attempts:
                    notes.append(f"network timeout/error on attempt {attempt}: {exc}")
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise OpenAIClientError(f"OpenAI request failed after {self.max_attempts} attempts: {exc}") from exc
            except (ValueError, json.JSONDecodeError) as exc:
                if attempt < self.max_attempts:
                    notes.append(f"invalid/empty JSON response on attempt {attempt}: retrying ({exc})")
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise OpenAIClientError(f"OpenAI response did not contain usable JSON: {exc}") from exc

        raise OpenAIClientError("OpenAI request failed without a usable response")
