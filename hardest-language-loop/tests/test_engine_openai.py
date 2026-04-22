from __future__ import annotations

import io
import json
import socket
import urllib.error
import unittest
from unittest.mock import patch

from app.engine import AgentLoopService


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _http_error(code: int, payload: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.openai.com/v1/responses",
        code=code,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


class SolveWithOpenAITests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AgentLoopService()
        self.kwargs = {
            "api_key": "test-key",
            "model_name": "o4-mini",
            "thinking": "medium",
            "temperature": 0.2,
            "candidate": {
                "name": "PL-TEST",
                "mutation_summary": "smoke",
                "metadata": {"strategy_family": "semantic_conflict", "strategy_leaf": "inverted_if"},
            },
            "interpreter_source": "type exp = NUM of int\nlet runb _ = 1",
            "ast_schema": {"schema_name": "json_ast_v1"},
            "task": {
                "task_name": "abs",
                "entry_name": "abs_val",
                "params": ["x"],
                "prompt": "Implement abs_val(x)",
                "expected_behavior": "Return abs(x)",
                "tests": [{"args": [-1], "expected": 1}],
            },
            "prompt_text": 'Return only this JSON object: {"type":"NUM","value":1}',
        }

    @patch("app.engine.time.sleep", return_value=None)
    def test_retries_without_temperature_for_unsupported_models(self, _sleep) -> None:
        calls = []

        def fake_urlopen(req, timeout=0):
            payload = json.loads(req.data.decode("utf-8"))
            calls.append(payload)
            if len(calls) == 1:
                raise _http_error(
                    400,
                    {
                        "error": {
                            "message": "Unsupported parameter: 'temperature' is not supported with this model.",
                            "param": "temperature",
                        }
                    },
                )
            return _FakeResponse({"status": "completed", "output_text": '{"type":"NUM","value":1}'})

        with patch("app.engine.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.service._solve_with_openai(**self.kwargs)

        self.assertTrue(result["temperature_omitted"])
        self.assertEqual(result["program"], {"type": "NUM", "value": 1})
        self.assertEqual(len(calls), 2)
        self.assertIn("temperature", calls[0])
        self.assertNotIn("temperature", calls[1])

    @patch("app.engine.time.sleep", return_value=None)
    def test_retries_after_timeout(self, _sleep) -> None:
        calls = []

        def fake_urlopen(req, timeout=0):
            calls.append(timeout)
            if len(calls) == 1:
                raise socket.timeout("The read operation timed out")
            return _FakeResponse({"status": "completed", "output_text": '{"type":"NUM","value":1}'})

        with patch("app.engine.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.service._solve_with_openai(**self.kwargs)

        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["program"], {"type": "NUM", "value": 1})
        self.assertGreaterEqual(result["request_timeout_seconds"], 45)

    @patch("app.engine.time.sleep", return_value=None)
    def test_retries_after_empty_output(self, _sleep) -> None:
        responses = [
            _FakeResponse({"status": "completed", "output": []}),
            _FakeResponse({"status": "completed", "output_text": '{"type":"NUM","value":1}'}),
        ]

        with patch("app.engine.urllib.request.urlopen", side_effect=responses):
            result = self.service._solve_with_openai(**self.kwargs)

        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["program"], {"type": "NUM", "value": 1})


if __name__ == "__main__":
    unittest.main()
