"""
Integration tests for tiered graceful degradation and the ``degraded`` payload.

Covers:
  1. connection_refused  → degraded=True, degraded_reason="LLM offline"
  2. timeout             → degraded=True, degraded_reason="LLM overloaded"
  3. server_error (5xx)  → degraded=True, degraded_reason="LLM server error"
  4. healthy LLM         → degraded=False, degraded_reason=""
  5. monitor rejection   → degraded=False (not applicable)
  6. LLMError.error_type classification in _make_request()
  7. 4xx raises LLMError(error_type="client_error") immediately (no retry)

Run with:
    pytest tests/test_degraded_payload.py -v
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests as req_lib
from utils.jan_client import JanClient, LLMError
from agents.personality_agents import MultiAgentSystem, PersonalityAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jan_client(**kwargs) -> JanClient:
    """Create a JanClient with safe test overrides."""
    defaults = dict(
        base_url="http://localhost:1337/v1",
        api_key="test-key-not-real",
        model_name="test-model",
    )
    defaults.update(kwargs)
    with patch("utils.jan_client.load_dotenv"):
        return JanClient(**defaults)


def _make_system() -> MultiAgentSystem:
    """Create a MultiAgentSystem with synthesis disabled for speed."""
    return MultiAgentSystem(use_synthesis=False)


# ---------------------------------------------------------------------------
# LLMError classification via _make_request()
# ---------------------------------------------------------------------------

class TestLLMErrorClassification:
    """_make_request() raises LLMError with the correct error_type."""

    def test_llm_error_str_format(self):
        """LLMError.__str__() formats as '[error_type] message'."""
        err = LLMError("server gone", error_type="connection_refused")
        assert str(err) == "[connection_refused] server gone"

    def test_llm_error_is_jan_client_error(self):
        """LLMError subclasses JanClientError for backwards compatibility."""
        from utils.jan_client import JanClientError
        err = LLMError("oops", error_type="timeout")
        assert isinstance(err, JanClientError)

    @patch("requests.post")
    def test_connection_refused_raises_llm_error(self, mock_post):
        """ConnectionError → LLMError(error_type='connection_refused')."""
        mock_post.side_effect = req_lib.exceptions.ConnectionError("refused")
        client = _make_jan_client()
        with pytest.raises(LLMError) as exc_info:
            client._make_request([{"role": "user", "content": "hi"}], max_retries=1)
        assert exc_info.value.error_type == "connection_refused"

    @patch("requests.post")
    def test_timeout_raises_llm_error(self, mock_post):
        """Timeout → LLMError(error_type='timeout')."""
        mock_post.side_effect = req_lib.exceptions.Timeout("timed out")
        client = _make_jan_client()
        with pytest.raises(LLMError) as exc_info:
            client._make_request([{"role": "user", "content": "hi"}], max_retries=1)
        assert exc_info.value.error_type == "timeout"

    @patch("requests.post")
    def test_5xx_raises_server_error(self, mock_post):
        """5xx HTTP response → LLMError(error_type='server_error')."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_post.return_value = mock_resp

        client = _make_jan_client()
        with pytest.raises(LLMError) as exc_info:
            client._make_request([{"role": "user", "content": "hi"}], max_retries=1)
        assert exc_info.value.error_type == "server_error"

    @patch("requests.post")
    def test_4xx_raises_client_error_no_retry(self, mock_post):
        """4xx HTTP response → LLMError(error_type='client_error'), called only once."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_post.return_value = mock_resp

        client = _make_jan_client()
        with pytest.raises(LLMError) as exc_info:
            client._make_request([{"role": "user", "content": "hi"}], max_retries=3)
        assert exc_info.value.error_type == "client_error"
        # Must NOT have retried — only one POST call made
        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# Integration: degraded payload from MultiAgentSystem.get_responses()
# ---------------------------------------------------------------------------

class TestDegradedPayload:
    """MultiAgentSystem.get_responses() includes correct degraded fields."""

    def _mock_monitor_approve(self):
        """Patch MonitorAgent to always approve."""
        return patch(
            "agents.personality_agents.MonitorAgent.check_question",
            return_value=(True, "✅ Approved!"),
        )

    def _mock_decision_joy_only(self):
        """Patch DecisionAgent to always pick Joy only."""
        return patch(
            "agents.personality_agents.DecisionAgent.analyze_message",
            return_value={"joy": True, "sadness": False, "anger": False,
                          "fear": False, "disgust": False},
        )

    @patch("requests.post")
    def test_connection_refused_sets_degraded_true(self, mock_post):
        """Connection refused → degraded=True, degraded_reason='LLM offline'."""
        mock_post.side_effect = req_lib.exceptions.ConnectionError("refused")

        system = _make_system()
        # Give the system a real (but unreachable) JanClient so it tries
        with patch.object(PersonalityAgent, "get_jan_client",
                          return_value=_make_jan_client()):
            with self._mock_monitor_approve():
                with self._mock_decision_joy_only():
                    result = system.get_responses("What's your favourite colour?")

        assert result["approved"] is True
        assert result["degraded"] is True
        assert result["degraded_reason"] == "LLM offline"
        # Static fallback still returns a response
        assert len(result["responses"]) == 1

    @patch("requests.post")
    def test_timeout_sets_degraded_overloaded(self, mock_post):
        """Timeout → degraded=True, degraded_reason='LLM overloaded'."""
        mock_post.side_effect = req_lib.exceptions.Timeout("timed out")

        system = _make_system()
        with patch.object(PersonalityAgent, "get_jan_client",
                          return_value=_make_jan_client()):
            with self._mock_monitor_approve():
                with self._mock_decision_joy_only():
                    result = system.get_responses("What's your favourite colour?")

        assert result["degraded"] is True
        assert result["degraded_reason"] == "LLM overloaded"

    @patch("requests.post")
    def test_server_error_sets_degraded_server_error(self, mock_post):
        """5xx → degraded=True, degraded_reason='LLM server error'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_err = req_lib.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_post.return_value = mock_resp

        system = _make_system()
        with patch.object(PersonalityAgent, "get_jan_client",
                          return_value=_make_jan_client()):
            with self._mock_monitor_approve():
                with self._mock_decision_joy_only():
                    result = system.get_responses("What's your favourite colour?")

        assert result["degraded"] is True
        assert result["degraded_reason"] == "LLM server error"

    @patch("requests.post")
    def test_healthy_llm_sets_degraded_false(self, mock_post):
        """Healthy LLM response → degraded=False."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "I love everything!"}}]
        }
        mock_post.return_value = mock_resp

        system = _make_system()
        with patch.object(PersonalityAgent, "get_jan_client",
                          return_value=_make_jan_client()):
            with self._mock_monitor_approve():
                with self._mock_decision_joy_only():
                    result = system.get_responses("What's your favourite colour?")

        assert result["degraded"] is False
        assert result["degraded_reason"] == ""

    def test_monitor_rejection_degraded_false(self):
        """Rejected by monitor → degraded=False (not applicable)."""
        system = _make_system()
        with patch(
            "agents.personality_agents.MonitorAgent.check_question",
            return_value=(False, "🚦 **Monitor**: Too serious!"),
        ):
            result = system.get_responses("I want legal advice")

        assert result["approved"] is False
        assert result["degraded"] is False
        assert result["degraded_reason"] == ""

    def test_degraded_payload_shape(self):
        """Result always contains 'degraded' and 'degraded_reason' keys."""
        system = _make_system()
        with patch(
            "agents.personality_agents.MonitorAgent.check_question",
            return_value=(True, "✅ Approved!"),
        ):
            with patch(
                "agents.personality_agents.DecisionAgent.analyze_message",
                return_value={"joy": False, "sadness": False, "anger": False,
                              "fear": False, "disgust": False},
            ):
                with patch.object(PersonalityAgent, "get_jan_client", return_value=None):
                    result = system.get_responses("Hello?")

        assert "degraded" in result
        assert "degraded_reason" in result
        assert isinstance(result["degraded"], bool)
        assert isinstance(result["degraded_reason"], str)
