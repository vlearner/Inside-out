"""
Tests for utils/jan_client.py

Run with:
    pytest tests/test_jan_client.py -v

You can override the model / API key used in integration-style tests by
setting environment variables before running:

    JAN_TEST_API_KEY=test-key-override  JAN_TEST_MODEL=my-model  pytest -v

Or pass them directly in code via the JanClient constructor:

    client = JanClient(api_key="test-only-key", model_name="test-model")

NOTE: No real credentials are stored in this file.
      All values are either clearly-labelled test dummies or read from env vars.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# ── project root on path ────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.jan_client import JanClient, JanClientError, get_llm_config, validate_environment

# ============================================================================
# Dummy values used ONLY in tests — not real credentials
# ============================================================================
DUMMY_API_KEY = "test-api-key-not-real"
DUMMY_MODEL = "test-model-not-real"
DUMMY_BASE_URL = "http://localhost:1337/v1"

# Configurable overrides — set these env vars to test against a real server
TEST_API_KEY = os.getenv("JAN_TEST_API_KEY", DUMMY_API_KEY)
TEST_MODEL = os.getenv("JAN_TEST_MODEL", JanClient.DEFAULT_MODEL)
TEST_BASE_URL = os.getenv("JAN_TEST_BASE_URL", DUMMY_BASE_URL)


# ============================================================================
# Helpers
# ============================================================================

def _make_client(**kwargs) -> JanClient:
    """
    Create a JanClient with safe test overrides (no real credentials).
    Any kwarg is forwarded; defaults use DUMMY_* constants above.
    """
    defaults = dict(
        base_url=TEST_BASE_URL,
        api_key=TEST_API_KEY,
        model_name=TEST_MODEL,
    )
    defaults.update(kwargs)
    with patch("utils.jan_client.load_dotenv"):
        return JanClient(**defaults)


# ============================================================================
# Initialisation
# ============================================================================

class TestJanClientInit:
    """Test constructor priority: kwarg > env-var > default constant."""

    def test_defaults_used_when_no_env_or_kwarg(self):
        """All class-level defaults are applied when nothing else is set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("utils.jan_client.load_dotenv"):
                client = JanClient()
        assert client.base_url == JanClient.DEFAULT_BASE_URL
        assert client.api_key == JanClient.DEFAULT_API_KEY
        assert client.model_name == JanClient.DEFAULT_MODEL

    def test_env_vars_override_defaults(self):
        """Environment variables take precedence over class defaults."""
        env = {
            "JAN_BASE_URL": "http://custom-host:9999/v1",
            "JAN_API_KEY": "env-key",
            "JAN_MODEL_NAME": "env-model",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("utils.jan_client.load_dotenv"):
                client = JanClient()
        assert client.base_url == "http://custom-host:9999/v1"
        assert client.api_key == "env-key"
        assert client.model_name == "env-model"

    def test_constructor_kwargs_override_env_and_defaults(self):
        """Explicit constructor kwargs beat env vars and defaults."""
        env = {"JAN_API_KEY": "env-key", "JAN_MODEL_NAME": "env-model"}
        with patch.dict(os.environ, env, clear=False):
            with patch("utils.jan_client.load_dotenv"):
                client = JanClient(api_key="kwarg-key", model_name="kwarg-model")
        assert client.api_key == "kwarg-key"
        assert client.model_name == "kwarg-model"

    def test_custom_api_key_via_constructor(self):
        """Verify a custom API key can be injected without env changes."""
        client = _make_client(api_key="super-secret-key")
        assert client.api_key == "super-secret-key"

    def test_custom_model_via_constructor(self):
        """Verify a custom model name can be injected without env changes."""
        client = _make_client(model_name="mistral-7b-instruct")
        assert client.model_name == "mistral-7b-instruct"

    def test_missing_base_url_raises(self):
        """Passing an empty base_url should raise JanClientError."""
        with patch.dict(os.environ, {"JAN_BASE_URL": ""}, clear=False):
            with patch("utils.jan_client.load_dotenv"):
                with pytest.raises(JanClientError, match="JAN_BASE_URL"):
                    JanClient(base_url="")


# ============================================================================
# test_connection()
# ============================================================================

class TestJanClientTestConnection:
    """Unit tests for test_connection() — no real network calls."""

    @patch("requests.get")
    def test_returns_true_on_200(self, mock_get):
        """A 200 response means the server is reachable."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = _make_client()
        assert client.test_connection() is True

    @patch("requests.get")
    def test_sends_auth_header(self, mock_get):
        """test_connection must include the Authorization header."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = _make_client(api_key="bearer-token-123")
        client.test_connection()

        call_kwargs = mock_get.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer bearer-token-123"

    @patch("requests.get")
    def test_returns_false_on_401(self, mock_get):
        """A 401 Unauthorized response should return False (not raise)."""
        import requests as req_lib

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_resp

        client = _make_client()
        assert client.test_connection() is False

    @patch("requests.get")
    def test_returns_false_on_connection_error(self, mock_get):
        """A connection-refused error should return False (not raise)."""
        import requests as req_lib

        mock_get.side_effect = req_lib.exceptions.ConnectionError("refused")
        client = _make_client()
        assert client.test_connection() is False

    @patch("requests.get")
    def test_returns_false_on_timeout(self, mock_get):
        """A timeout should return False (not raise)."""
        import requests as req_lib

        mock_get.side_effect = req_lib.exceptions.Timeout("timeout")
        client = _make_client()
        assert client.test_connection() is False


# ============================================================================
# chat()
# ============================================================================

class TestJanClientChat:
    """Unit tests for the chat() convenience method."""

    @patch("requests.post")
    def test_chat_returns_content(self, mock_post):
        """chat() should return the message content string."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "  Hello from the model!  "}}]
        }
        mock_post.return_value = mock_resp

        client = _make_client()
        result = client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello from the model!"

    @patch("requests.post")
    def test_chat_sends_correct_model(self, mock_post):
        """chat() must use the model configured on the client."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = mock_resp

        client = _make_client(model_name="custom-model-test")
        client.chat([{"role": "user", "content": "Hi"}])

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "custom-model-test"

    @patch("requests.post")
    def test_chat_sends_auth_header(self, mock_post):
        """chat() must include the Authorization header when api_key is set."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = mock_resp

        client = _make_client(api_key="secret-key")
        client.chat([{"role": "user", "content": "Hi"}])

        headers = mock_post.call_args[1]["headers"]
        assert headers.get("Authorization") == "Bearer secret-key"

    @patch("requests.post")
    def test_chat_raises_on_bad_response_format(self, mock_post):
        """chat() should raise JanClientError when response has no choices."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"unexpected": "format"}
        mock_post.return_value = mock_resp

        client = _make_client()
        with pytest.raises(JanClientError, match="Unexpected response format"):
            client.chat([{"role": "user", "content": "Hi"}])

    @patch("requests.post")
    def test_chat_raises_on_4xx(self, mock_post):
        """chat() should raise JanClientError on a 4xx HTTP error (no retry)."""
        import requests as req_lib

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_post.return_value = mock_resp

        client = _make_client()
        with pytest.raises(JanClientError):
            client.chat([{"role": "user", "content": "Hi"}])


# ============================================================================
# get_llm_config()
# ============================================================================

class TestGetLlmConfig:
    """Tests for the get_llm_config() helper."""

    def test_returns_config_list(self):
        env = {
            "JAN_BASE_URL": "http://localhost:1337/v1",
            "JAN_API_KEY": "test-key",
            "JAN_MODEL_NAME": "llama-3.1-8b-instruct",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("utils.jan_client.load_dotenv"):
                config = get_llm_config()
        assert "config_list" in config
        assert config["config_list"][0]["model"] == "llama-3.1-8b-instruct"
        assert config["config_list"][0]["base_url"] == "http://localhost:1337/v1"

    def test_temperature_override(self):
        with patch("utils.jan_client.load_dotenv"):
            config = get_llm_config(temperature=0.3)
        assert config["temperature"] == 0.3

    def test_max_tokens_override(self):
        with patch("utils.jan_client.load_dotenv"):
            config = get_llm_config(max_tokens=1024)
        assert config["max_tokens"] == 1024


# ============================================================================
# validate_environment()
# ============================================================================

class TestValidateEnvironment:
    """Tests for validate_environment()."""

    def test_valid_when_base_url_set(self):
        env = {"JAN_BASE_URL": "http://localhost:1337/v1"}
        with patch.dict(os.environ, env, clear=False):
            with patch("utils.jan_client.load_dotenv"):
                is_valid, msg = validate_environment()
        assert is_valid is True

    def test_invalid_when_base_url_missing(self):
        # Temporarily remove JAN_BASE_URL
        env = os.environ.copy()
        env.pop("JAN_BASE_URL", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("utils.jan_client.load_dotenv"):
                is_valid, msg = validate_environment()
        assert is_valid is False
        assert "JAN_BASE_URL" in msg


# ============================================================================
# Standalone runner (no pytest required)
# ============================================================================

def run_jan_client_tests():
    """
    Quick smoke-test runner that can be called directly:

        python tests/test_jan_client.py
    """
    from unittest.mock import patch, MagicMock
    import requests as req_lib

    print("=" * 70)
    print("RUNNING JAN CLIENT TESTS")
    print(f"  API key  : {TEST_API_KEY[:4]}****")
    print(f"  Model    : {TEST_MODEL}")
    print(f"  Base URL : {TEST_BASE_URL}")
    print("=" * 70)

    # --- init with constructor kwargs ---
    print("\n▶ Constructor kwarg overrides...")
    client = _make_client(api_key="test-key", model_name="test-model")
    assert client.api_key == "test-key"
    assert client.model_name == "test-model"
    print("  ✅ api_key and model_name set via constructor")

    # --- test_connection success ---
    print("\n▶ test_connection — success (200)...")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        assert client.test_connection() is True
    print("  ✅ Returns True on 200")

    # --- test_connection 401 ---
    print("\n▶ test_connection — 401 Unauthorized...")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_resp
        assert client.test_connection() is False
    print("  ✅ Returns False on 401")

    # --- chat sends correct model ---
    print("\n▶ chat() — sends correct model name...")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hi"}}]
        }
        mock_post.return_value = mock_resp
        _make_client(model_name="my-custom-model").chat(
            [{"role": "user", "content": "hello"}]
        )
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "my-custom-model"
    print("  ✅ Correct model in request payload")

    # --- validate_environment ---
    print("\n▶ validate_environment — with JAN_BASE_URL set...")
    with patch.dict(os.environ, {"JAN_BASE_URL": "http://localhost:1337/v1"}):
        with patch("utils.jan_client.load_dotenv"):
            is_valid, msg = validate_environment()
    assert is_valid is True
    print("  ✅ Valid environment recognised")

    print("\n" + "=" * 70)
    print("✅ ALL JAN CLIENT TESTS PASSED!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_jan_client_tests()
    sys.exit(0 if success else 1)
