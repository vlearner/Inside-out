"""
Tests for MonitorAgent.check_question() — two-stage (keyword + LLM) check.

Covers:
  1. keyword-rejected  — Stage 1 blocklist fires; LLM is never called.
  2. LLM-rejected      — Stage 1 passes; LLM returns REJECT.
  3. LLM-approved      — Stage 1 passes; LLM returns APPROVE.
  4. LLM-unavailable   — Stage 1 passes; no LLM client → fail-open (approved).
  5. LLM-exception     — Stage 1 passes; LLM raises an exception → fail-open.

Run with:
    pytest tests/test_monitor_agent.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.personality_agents import MonitorAgent, PersonalityAgent


# ============================================================================
# Stage 1 — keyword blocklist and length check
# ============================================================================

class TestMonitorStage1Keywords:
    """Stage 1 fast pre-check: keyword blocklist."""

    def test_keyword_depressed_rejected(self):
        """'depressed' in message → immediate rejection, no LLM call."""
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("I feel depressed today")
        mock_get_client.assert_not_called()
        assert approved is False
        assert "Monitor" in msg

    def test_keyword_suicide_rejected(self):
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("I'm thinking about suicide")
        mock_get_client.assert_not_called()
        assert approved is False

    def test_keyword_legal_rejected(self):
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("I need a legal opinion")
        mock_get_client.assert_not_called()
        assert approved is False

    def test_keyword_investment_rejected(self):
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("What stocks should I invest in?")
        mock_get_client.assert_not_called()
        assert approved is False

    def test_keyword_how_do_i_fix_rejected(self):
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("How do I fix my computer?")
        mock_get_client.assert_not_called()
        assert approved is False

    def test_too_short_rejected(self):
        """Messages shorter than 5 chars are rejected at Stage 1."""
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, msg = monitor.check_question("hi")
        mock_get_client.assert_not_called()
        assert approved is False

    def test_keyword_match_does_not_call_llm(self):
        """When a keyword triggers, the LLM MUST NOT be called (fast-path)."""
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client") as mock_get_client:
            approved, _ = monitor.check_question("I'm feeling depressed about my job")
        mock_get_client.assert_not_called()
        assert approved is False


# ============================================================================
# Stage 2 — LLM semantic check
# ============================================================================

class TestMonitorStage2LLM:
    """Stage 2 semantic LLM check (Stage 1 passes for all messages below)."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_client(response_text: str):
        client = MagicMock()
        client.chat.return_value = response_text
        return client

    # ------------------------------------------------------------------
    # LLM approves
    # ------------------------------------------------------------------

    def test_llm_approves_fun_question(self):
        """Fun question passes keywords → LLM returns APPROVE → approved."""
        monitor = MonitorAgent()
        mock_client = self._mock_client("APPROVE")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, msg = monitor.check_question("What is your favourite pizza topping?")
        assert approved is True
        assert "Approved" in msg
        mock_client.chat.assert_called_once()

    def test_llm_approve_case_insensitive(self):
        """'approve' in any case should pass."""
        monitor = MonitorAgent()
        mock_client = self._mock_client("approve")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, _ = monitor.check_question("What is the best dance move?")
        assert approved is True

    def test_llm_approves_neutral_question(self):
        """Neutral/informational question passes both stages."""
        monitor = MonitorAgent()
        mock_client = self._mock_client("APPROVE")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, _ = monitor.check_question("What is your favourite colour?")
        assert approved is True

    # ------------------------------------------------------------------
    # LLM rejects
    # ------------------------------------------------------------------

    def test_llm_rejects_semantic_harm_no_keywords(self):
        """LLM catches a harmful message that bypasses the keyword filter."""
        monitor = MonitorAgent()
        mock_client = self._mock_client("REJECT: This is a fun zone! Try something silly instead.")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, msg = monitor.check_question(
                "What is the optimal strategy for a hostile corporate takeover?"
            )
        assert approved is False
        assert "Monitor" in msg
        mock_client.chat.assert_called_once()

    def test_llm_reject_case_insensitive(self):
        """'reject' in any case should block the message."""
        monitor = MonitorAgent()
        mock_client = self._mock_client("reject: too serious")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, _ = monitor.check_question("Tell me about geopolitical tensions in Europe")
        assert approved is False

    def test_llm_uses_monitor_prompt_as_system_message(self):
        """The LLM must be called with the MONITOR_PROMPT as the system role."""
        from config.personalities import MONITOR_PROMPT
        monitor = MonitorAgent()
        mock_client = self._mock_client("APPROVE")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            monitor.check_question("What is the best board game?")
        call_args = mock_client.chat.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == MONITOR_PROMPT

    # ------------------------------------------------------------------
    # LLM unavailable / fail-open
    # ------------------------------------------------------------------

    def test_llm_unavailable_fails_open(self):
        """When Jan AI is down (client is None), monitor approves (fail-open)."""
        monitor = MonitorAgent()
        with patch.object(PersonalityAgent, "get_jan_client", return_value=None):
            approved, msg = monitor.check_question("What is your favourite colour?")
        assert approved is True
        assert "Approved" in msg

    def test_llm_exception_fails_open(self):
        """When LLM chat() raises an exception, monitor approves (fail-open)."""
        monitor = MonitorAgent()
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("Connection timeout")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            approved, msg = monitor.check_question("What is your favourite colour?")
        assert approved is True
        assert "Approved" in msg

    def test_llm_exception_does_not_raise(self):
        """An LLM exception must never propagate out of check_question()."""
        monitor = MonitorAgent()
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("Unexpected crash")
        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            try:
                result = monitor.check_question("What is your favourite colour?")
            except Exception as exc:
                pytest.fail(f"check_question() raised an unexpected exception: {exc}")
        assert result[0] is True
