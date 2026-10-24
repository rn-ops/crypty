import json
import os
import unittest
from unittest.mock import patch

from chatbot import answer_question, build_request, load_project_context


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "CRYPTY is a demo."}],
            }]
        }).encode("utf-8")


class ChatbotTests(unittest.TestCase):
    def test_request_is_read_only_and_includes_project_context(self):
        payload = build_request("What is CRYPTY?", context="project docs")

        self.assertIn("project docs", payload["instructions"])
        self.assertEqual(payload["input"][-1]["content"], "What is CRYPTY?")
        self.assertNotIn("tools", payload)
        self.assertNotIn("functionDeclarations", payload)

    def test_recent_chat_history_is_forwarded_in_order(self):
        payload = build_request(
            "And recovery?",
            history=[{"role": "user", "text": "What is CRYPTY?"},
                     {"role": "model", "text": "A demo."}],
            context="docs",
        )

        self.assertEqual([item["role"] for item in payload["input"]],
                         ["user", "assistant", "user"])

    def test_live_request_uses_xai_bearer_key_and_returns_text(self):
        captured = {}

        def fake_open(request, timeout):
            captured["request"] = request
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            reply = answer_question("What is CRYPTY?", opener=fake_open)

        self.assertEqual(reply, "CRYPTY is a demo.")
        self.assertEqual(captured["request"].get_header("Authorization"), "Bearer test-key")
        self.assertEqual(captured["timeout"], 45)
        self.assertEqual(captured["request"].full_url, "https://api.x.ai/v1/responses")
        self.assertEqual(captured["payload"]["model"], "grok-4.7")
        self.assertIn("instructions", captured["payload"])
        self.assertNotIn("tools", captured["payload"])

    def test_context_loads_from_repository_documentation(self):
        context = load_project_context()

        self.assertIn("Crypty", context)
        self.assertIn("core/include/crypty/workflow.hpp", context)

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            build_request("  ")


if __name__ == "__main__":
    unittest.main()
