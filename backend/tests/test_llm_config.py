"""LLM 配置校验测试。"""

import unittest

from pydantic import ValidationError

from app.config import Settings


class LLMConfigTest(unittest.TestCase):
    def test_missing_llm_config_raises_clear_error(self):
        with self.assertRaises(ValidationError) as context:
            Settings(
                _env_file=None,
                llm_api_key="",
                llm_api_base="",
                llm_model="",
            )

        message = str(context.exception)
        self.assertIn("LLM_API_KEY", message)
        self.assertIn("LLM_API_BASE", message)
        self.assertIn("LLM_MODEL", message)

    def test_explicit_llm_config_is_accepted(self):
        settings = Settings(
            _env_file=None,
            llm_api_key="test-key",
            llm_api_base="https://example.com/v1",
            llm_model="test-model",
        )

        self.assertEqual(settings.llm_model, "test-model")


if __name__ == "__main__":
    unittest.main()
