"""
Tests for the Human-in-the-Loop clarification gate.

Covers:
  1. MonitorAgent uncertain → MultiAgentSystem returns clarification_needed.
  2. MonitorAgent approved  → status field is "approved".
  3. MonitorAgent rejected  → status field is "rejected".
  4. Uncertain messages are NOT recorded in conversation memory.
  5. Personality agents are NOT called on clarification_needed.

Run with:
    pytest tests/test_clarification.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.personality_agents import MonitorAgent, MultiAgentSystem, PersonalityAgent


class TestClarificationPayload:
    """get_responses() returns correct status for all three verdict states."""

    @staticmethod
    def _make_system() -> MultiAgentSystem:
        with patch.object(PersonalityAgent, "get_jan_client", return_value=None):
            return MultiAgentSystem(use_synthesis=False)

    def test_uncertain_returns_clarification_needed_status(self):
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            None,
            MonitorAgent.CLARIFICATION_PROMPT,
        )

        result = system.get_responses("I'm so sick of pineapple on pizza")

        assert result["approved"] is False
        assert result["status"] == "clarification_needed"
        assert result["clarification_prompt"] == MonitorAgent.CLARIFICATION_PROMPT
        assert result["responses"] == []
        assert result["decisions"] == {}

    def test_approved_returns_approved_status(self):
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (True, "✅ Approved!")
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False,
        }
        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: That's great! ✨"
        )

        result = system.get_responses("What's the best pizza topping?")

        assert result["approved"] is True
        assert result["status"] == "approved"

    def test_rejected_returns_rejected_status(self):
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            False,
            "🚦 **Monitor**: This seems too serious!",
        )

        result = system.get_responses("I need legal advice")

        assert result["approved"] is False
        assert result["status"] == "rejected"

    def test_uncertain_does_not_record_memory(self):
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            None,
            MonitorAgent.CLARIFICATION_PROMPT,
        )

        system.get_responses("Ambiguous message")

        assert system.memory.get_context() == []

    def test_uncertain_does_not_call_personality_agents(self):
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            None,
            MonitorAgent.CLARIFICATION_PROMPT,
        )
        system.decision_agent = MagicMock()

        system.get_responses("Ambiguous message")

        system.decision_agent.analyze_message.assert_not_called()
        for agent in system.agents.values():
            if hasattr(agent.get_response, "assert_not_called"):
                agent.get_response.assert_not_called()

    def test_clarification_payload_has_degraded_fields(self):
        """Even clarification responses include degraded/degraded_reason."""
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            None,
            MonitorAgent.CLARIFICATION_PROMPT,
        )

        result = system.get_responses("Ambiguous message")

        assert "degraded" in result
        assert result["degraded"] is False
        assert "degraded_reason" in result
        assert result["degraded_reason"] == ""
