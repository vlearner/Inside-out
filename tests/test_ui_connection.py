"""
Tests for Streamlit UI — AI Model Connection and Tool Selection
Uses mocking to test without actual LLM backend server or running Streamlit.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient, LLMClientError

# Import the helper under test (avoid importing streamlit at module level)
# We import from ui.streamlit_app inside tests to allow patching.


# ============================================================================
# Test Data
# ============================================================================

MOCK_MODELS_RESPONSE = {
    "data": [
        {"id": "llama-3.1-8b-instruct", "object": "model"}
    ]
}


# ============================================================================
# test_ai_model_connection() Tests
# ============================================================================

class TestAIModelConnection:
    """Tests for the test_ai_model_connection helper function."""

    @patch("ui.streamlit_app.LLMClient")
    def test_connection_success(self, mock_jan_cls):
        """When LLM backend server is reachable, return connected=True."""
        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.model_name = "llama-3.1-8b-instruct"
        mock_client.base_url = "http://localhost:1337/v1"
        mock_jan_cls.return_value = mock_client

        from ui.streamlit_app import test_ai_model_connection

        result = test_ai_model_connection()

        assert result["connected"] is True
        assert result["model"] == "llama-3.1-8b-instruct"
        assert result["base_url"] == "http://localhost:1337/v1"
        assert result["error"] is None

    @patch("ui.streamlit_app.LLMClient")
    def test_connection_server_not_responding(self, mock_jan_cls):
        """When server is not responding, return connected=False with message."""
        mock_client = MagicMock()
        mock_client.test_connection.return_value = False
        mock_client.model_name = "llama-3.1-8b-instruct"
        mock_client.base_url = "http://localhost:1337/v1"
        mock_jan_cls.return_value = mock_client

        from ui.streamlit_app import test_ai_model_connection

        result = test_ai_model_connection()

        assert result["connected"] is False
        assert result["error"] == "Server is not responding"

    @patch("ui.streamlit_app.LLMClient")
    def test_connection_llm_client_error(self, mock_jan_cls):
        """When LLMClient raises LLMClientError, return error details."""
        mock_jan_cls.side_effect = LLMClientError("Config missing")

        from ui.streamlit_app import test_ai_model_connection

        result = test_ai_model_connection()

        assert result["connected"] is False
        assert "Config missing" in result["error"]
        assert result["model"] == "N/A"

    @patch("ui.streamlit_app.LLMClient")
    def test_connection_unexpected_exception(self, mock_jan_cls):
        """When an unexpected exception occurs, return error details."""
        mock_jan_cls.side_effect = RuntimeError("Unexpected boom")

        from ui.streamlit_app import test_ai_model_connection

        result = test_ai_model_connection()

        assert result["connected"] is False
        assert "Unexpected boom" in result["error"]


# ============================================================================
# AVAILABLE_TOOLS Configuration Tests
# ============================================================================

class TestAvailableToolsConfig:
    """Tests for the AVAILABLE_TOOLS configuration dict."""

    def test_weather_tool_present(self):
        """Weather tool must be defined in AVAILABLE_TOOLS."""
        from ui.streamlit_app import AVAILABLE_TOOLS

        assert "weather" in AVAILABLE_TOOLS

    def test_tool_has_required_keys(self):
        """Every tool entry must have name, emoji, description, and module."""
        from ui.streamlit_app import AVAILABLE_TOOLS

        required_keys = {"name", "emoji", "description", "module"}
        for tool_key, tool_config in AVAILABLE_TOOLS.items():
            for key in required_keys:
                assert key in tool_config, (
                    f"Tool '{tool_key}' missing required key '{key}'"
                )

    def test_weather_tool_module_path(self):
        """Weather tool module path should point to an importable module."""
        from ui.streamlit_app import AVAILABLE_TOOLS

        module_path = AVAILABLE_TOOLS["weather"]["module"]
        assert module_path == "tools.weather_tool"


# ============================================================================
# EMOTION_FRIENDS Configuration Tests
# ============================================================================

class TestEmotionFriendsConfig:
    """Tests for the EMOTION_FRIENDS configuration dict."""

    def test_all_five_emotions_present(self):
        """All five Inside Out emotions must be defined."""
        from ui.streamlit_app import EMOTION_FRIENDS

        expected = {"joy", "sadness", "anger", "fear", "disgust"}
        assert set(EMOTION_FRIENDS.keys()) == expected

    def test_emotion_has_required_keys(self):
        """Each emotion must have name, emoji, color, status, and base_delay."""
        from ui.streamlit_app import EMOTION_FRIENDS

        required_keys = {"name", "emoji", "color", "status", "base_delay"}
        for emotion, config in EMOTION_FRIENDS.items():
            for key in required_keys:
                assert key in config, (
                    f"Emotion '{emotion}' missing required key '{key}'"
                )


# ============================================================================
# parse_mentions() Tests
# ============================================================================

class TestParseMentions:
    """Tests for the parse_mentions helper."""

    def test_single_mention(self):
        from ui.streamlit_app import parse_mentions

        mentioned, cleaned = parse_mentions("@joy What's fun today?")
        assert "joy" in mentioned
        assert "@joy" not in cleaned

    def test_multiple_mentions(self):
        from ui.streamlit_app import parse_mentions

        mentioned, cleaned = parse_mentions("@anger @fear This is scary and unfair!")
        assert "anger" in mentioned
        assert "fear" in mentioned

    def test_no_mentions(self):
        from ui.streamlit_app import parse_mentions

        mentioned, cleaned = parse_mentions("Just a regular message")
        assert mentioned == []
        assert cleaned == "Just a regular message"


# ============================================================================
# LLMClient.test_connection() Unit Tests (low-level)
# ============================================================================

class TestLLMClientTestConnection:
    """Low-level tests for LLMClient.test_connection()."""

    @patch("requests.get")
    def test_test_connection_success(self, mock_get):
        """Successful /models response should return True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_MODELS_RESPONSE
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.test_connection() is True

    @patch("requests.get")
    def test_test_connection_failure(self, mock_get):
        """Connection error should return False."""
        mock_get.side_effect = ConnectionError("refused")

        client = LLMClient()
        assert client.test_connection() is False


# ============================================================================
# build_friends_js_payload() Tests
# ============================================================================

class TestBuildFriendsJsPayload:
    """Tests for build_friends_js_payload — JSON-safe friends list for the autocomplete script."""

    def _fn(self):
        from ui.streamlit_app import build_friends_js_payload
        return build_friends_js_payload

    def test_returns_valid_json(self):
        """Output must always be parseable JSON."""
        import json
        build = self._fn()
        result = build(["joy", "sadness"])
        parsed = json.loads(result)  # raises if invalid
        assert isinstance(parsed, list)

    def test_all_active_friends_included(self):
        """Every key in active_friend_keys must appear in the output."""
        import json
        build = self._fn()
        keys = ["joy", "anger", "fear"]
        parsed = json.loads(build(keys))
        result_keys = [item["key"] for item in parsed]
        assert result_keys == keys

    def test_entry_has_required_fields(self):
        """Each entry must have key, name, emoji, and color."""
        import json
        build = self._fn()
        parsed = json.loads(build(["joy"]))
        entry = parsed[0]
        assert "key" in entry
        assert "name" in entry
        assert "emoji" in entry
        assert "color" in entry

    def test_empty_list_returns_empty_json_array(self):
        """No active friends → empty JSON array, not a broken string."""
        import json
        build = self._fn()
        result = build([])
        assert json.loads(result) == []

    def test_special_characters_are_escaped(self):
        """Names/colors with quotes or backslashes must be safely escaped."""
        import json
        build = self._fn()
        evil_friends = {
            "x": {
                "name": 'Joy"Evil\\',
                "emoji": "😊",
                "color": "#FF'00",
            }
        }
        result = build(["x"], emotion_friends=evil_friends)
        # Must still parse cleanly — no injection
        parsed = json.loads(result)
        assert parsed[0]["name"] == 'Joy"Evil\\'
        assert parsed[0]["color"] == "#FF'00"

    def test_no_raw_quotes_break_script_embedding(self):
        """The output must not contain unescaped double-quotes inside values."""
        import json
        build = self._fn()
        tricky_friends = {
            "q": {
                "name": 'Has"Quote',
                "emoji": "🔥",
                "color": "#000",
            }
        }
        result = build(["q"], emotion_friends=tricky_friends)
        # Re-parse to confirm round-trip integrity
        parsed = json.loads(result)
        assert parsed[0]["name"] == 'Has"Quote'

    def test_uses_emotion_friends_module_constant_by_default(self):
        """Without an explicit emotion_friends arg, EMOTION_FRIENDS is used."""
        import json
        from ui.streamlit_app import EMOTION_FRIENDS
        build = self._fn()
        result = build(["joy"])
        parsed = json.loads(result)
        assert parsed[0]["name"] == EMOTION_FRIENDS["joy"]["name"]
        assert parsed[0]["emoji"] == EMOTION_FRIENDS["joy"]["emoji"]
        assert parsed[0]["color"] == EMOTION_FRIENDS["joy"]["color"]

    def test_ordering_preserved(self):
        """Friends must appear in the same order as active_friend_keys."""
        import json
        build = self._fn()
        keys = ["disgust", "fear", "joy"]
        parsed = json.loads(build(keys))
        assert [e["key"] for e in parsed] == keys


# ============================================================================
# is_debug_ui_enabled() Tests
# ============================================================================

class TestDebugUiToggle:
    """Tests for UI debug-panel toggle config helper."""

    @patch("ui.streamlit_app.get_secret")
    def test_debug_toggle_true_boolean(self, mock_get_secret):
        from ui.streamlit_app import is_debug_ui_enabled
        mock_get_secret.return_value = True
        assert is_debug_ui_enabled() is True

    @patch("ui.streamlit_app.get_secret")
    def test_debug_toggle_false_boolean(self, mock_get_secret):
        from ui.streamlit_app import is_debug_ui_enabled
        mock_get_secret.return_value = False
        assert is_debug_ui_enabled() is False

    @patch("ui.streamlit_app.get_secret")
    def test_debug_toggle_string_true(self, mock_get_secret):
        from ui.streamlit_app import is_debug_ui_enabled
        mock_get_secret.return_value = "yes"
        assert is_debug_ui_enabled() is True


# ============================================================================
# Runner (no pytest)
# ============================================================================

def run_ui_connection_tests():
    """Run all UI connection tests without pytest."""
    print("=" * 70)
    print("RUNNING UI CONNECTION & TOOL SELECTION TESTS")
    print("=" * 70)

    # --- test_ai_model_connection ---
    print("\n▶ Testing test_ai_model_connection — success case...")
    with patch("ui.streamlit_app.LLMClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.model_name = "test-model"
        mock_client.base_url = "http://localhost:1337/v1"
        mock_cls.return_value = mock_client

        from ui.streamlit_app import test_ai_model_connection
        result = test_ai_model_connection()
        assert result["connected"] is True
        assert result["model"] == "test-model"
    print("  ✅ Passed")

    print("▶ Testing test_ai_model_connection — failure case...")
    with patch("ui.streamlit_app.LLMClient") as mock_cls:
        mock_cls.side_effect = LLMClientError("No config")
        result = test_ai_model_connection()
        assert result["connected"] is False
        assert "No config" in result["error"]
    print("  ✅ Passed")

    # --- AVAILABLE_TOOLS ---
    print("\n▶ Testing AVAILABLE_TOOLS configuration...")
    from ui.streamlit_app import AVAILABLE_TOOLS
    assert "weather" in AVAILABLE_TOOLS
    for key in ("name", "emoji", "description", "module"):
        assert key in AVAILABLE_TOOLS["weather"], f"Missing '{key}'"
    print("  ✅ Passed")

    # --- EMOTION_FRIENDS ---
    print("\n▶ Testing EMOTION_FRIENDS configuration...")
    from ui.streamlit_app import EMOTION_FRIENDS
    assert set(EMOTION_FRIENDS.keys()) == {"joy", "sadness", "anger", "fear", "disgust"}
    print("  ✅ Passed")

    # --- parse_mentions ---
    print("\n▶ Testing parse_mentions...")
    from ui.streamlit_app import parse_mentions
    mentioned, _ = parse_mentions("@joy hello")
    assert "joy" in mentioned
    mentioned, cleaned = parse_mentions("no mentions here")
    assert mentioned == []
    print("  ✅ Passed")

    print("\n" + "=" * 70)
    print("✅ ALL UI CONNECTION & TOOL SELECTION TESTS PASSED!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_ui_connection_tests()
    sys.exit(0 if success else 1)
