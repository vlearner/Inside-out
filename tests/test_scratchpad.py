"""
Tests for the Shared Scratchpad inter-agent communication feature.

Covers:
  1. config/agents.py — SCRATCHPAD_AGENT_ORDER constant.
  2. MultiAgentSystem(use_scratchpad=True) — sequential execution in defined order.
  3. Scratchpad context injection — later agents receive prior agents' text.
  4. use_scratchpad=False — original parallel behaviour is unchanged.
  5. Scratchpad with @mentions — still respects mention override.
  6. Performance logging — elapsed time is logged.

Run with:
    pytest tests/test_scratchpad.py -v
"""
import os
import sys
import re
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.agents import SCRATCHPAD_AGENT_ORDER
from agents.personality_agents import MultiAgentSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system(**kwargs) -> MultiAgentSystem:
    """Return a MultiAgentSystem with mocked monitor (always approves)."""
    system = MultiAgentSystem(**kwargs)
    system.monitor = MagicMock()
    system.monitor.check_question.return_value = (True, "✅ Approved!")
    return system


# ---------------------------------------------------------------------------
# 1. SCRATCHPAD_AGENT_ORDER config
# ---------------------------------------------------------------------------

class TestScratchpadConfig:
    def test_order_is_list(self):
        assert isinstance(SCRATCHPAD_AGENT_ORDER, list)

    def test_order_contains_all_five_emotions(self):
        expected = {"joy", "sadness", "anger", "fear", "disgust"}
        assert set(SCRATCHPAD_AGENT_ORDER) == expected

    def test_order_starts_with_joy(self):
        assert SCRATCHPAD_AGENT_ORDER[0] == "joy"

    def test_order_has_no_duplicates(self):
        assert len(SCRATCHPAD_AGENT_ORDER) == len(set(SCRATCHPAD_AGENT_ORDER))


# ---------------------------------------------------------------------------
# 2. MultiAgentSystem use_scratchpad flag
# ---------------------------------------------------------------------------

class TestScratchpadFlag:
    def test_default_is_false(self):
        system = MultiAgentSystem()
        assert system.use_scratchpad is False

    def test_can_enable(self):
        system = MultiAgentSystem(use_scratchpad=True)
        assert system.use_scratchpad is True


# ---------------------------------------------------------------------------
# 3. Sequential execution with scratchpad context
# ---------------------------------------------------------------------------

class TestScratchpadExecution:
    def test_agents_called_in_scratchpad_order(self):
        """When scratchpad is enabled, agents are called in SCRATCHPAD_AGENT_ORDER."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        # Decision agent selects all 5
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            e: True for e in SCRATCHPAD_AGENT_ORDER
        }

        call_order = []
        for agent_type in SCRATCHPAD_AGENT_ORDER:
            agent = system.agents[agent_type]
            original_name = agent.name

            def make_response(name, atype):
                def _response(*args, **kwargs):
                    call_order.append(atype)
                    return f"{system.agents[atype].emoji} **{name}**: Test response from {name}"
                return _response

            agent.get_response = MagicMock(side_effect=make_response(original_name, agent_type))

        system.get_responses("What do you all think?")

        assert call_order == SCRATCHPAD_AGENT_ORDER

    def test_later_agents_receive_scratchpad_context(self):
        """The second agent receives context about the first agent's response."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": True,
            "anger": False, "fear": False, "disgust": False,
        }

        joy_text = "Ooh, I love that! ✨"
        system.agents["joy"].get_response = MagicMock(
            return_value=f"😄 **Joy**: {joy_text}"
        )
        system.agents["sadness"].get_response = MagicMock(
            return_value="😢 **Sadness**: *sigh* That's bittersweet..."
        )

        system.get_responses("Tell me about ice cream")

        # Sadness should have been called with scratchpad context from Joy
        sadness_call_args = system.agents["sadness"].get_response.call_args
        question_arg = sadness_call_args[0][0]  # first positional arg
        assert "[Joy already responded:" in question_arg
        assert joy_text in question_arg

    def test_first_agent_gets_no_scratchpad_context(self):
        """The first agent (Joy) should not receive any scratchpad context."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False,
            "anger": False, "fear": False, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Yay! ✨"
        )

        system.get_responses("Tell me something fun")

        joy_call_args = system.agents["joy"].get_response.call_args
        question_arg = joy_call_args[0][0]
        assert "[" not in question_arg  # No scratchpad brackets
        assert "already responded" not in question_arg

    def test_scratchpad_accumulates_across_agents(self):
        """The third agent receives scratchpad entries from both prior agents."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        # Joy, Sadness, Fear active
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": True,
            "anger": False, "fear": True, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Love it! ✨"
        )
        system.agents["sadness"].get_response = MagicMock(
            return_value="😢 **Sadness**: *sigh* So bittersweet..."
        )
        system.agents["fear"].get_response = MagicMock(
            return_value="😰 **Fear**: But what if it goes wrong?!"
        )

        system.get_responses("What about adventures?")

        # Fear (3rd in order) should see both Joy and Sadness
        fear_call_args = system.agents["fear"].get_response.call_args
        question_arg = fear_call_args[0][0]
        assert "[Joy already responded:" in question_arg
        assert "[Sadness already responded:" in question_arg


# ---------------------------------------------------------------------------
# 4. Parallel mode unchanged
# ---------------------------------------------------------------------------

class TestParallelModeUnchanged:
    def test_no_scratchpad_context_in_parallel_mode(self):
        """When use_scratchpad=False, agents don't receive scratchpad context."""
        system = _make_system(use_scratchpad=False, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": True,
            "anger": False, "fear": False, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Yay! ✨"
        )
        system.agents["sadness"].get_response = MagicMock(
            return_value="😢 **Sadness**: *sigh*..."
        )

        system.get_responses("Tell me about ice cream")

        # Neither agent should have scratchpad context
        for agent_type in ["joy", "sadness"]:
            call_args = system.agents[agent_type].get_response.call_args
            question_arg = call_args[0][0]
            assert "already responded" not in question_arg


# ---------------------------------------------------------------------------
# 5. Scratchpad with @mentions
# ---------------------------------------------------------------------------

class TestScratchpadWithMentions:
    def test_mentions_respected_in_scratchpad_mode(self):
        """@mention override still works when scratchpad is enabled."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.agents["anger"].get_response = MagicMock(
            return_value="😡 **Anger**: That fires me up! 😤"
        )
        system.agents["disgust"].get_response = MagicMock(
            return_value="🤢 **Disgust**: Ugh, seriously? 💅"
        )

        result = system.get_responses(
            "@anger @disgust This is outrageous!",
            mentioned=["anger", "disgust"],
        )

        assert result["approved"] is True
        emotions = [r["emotion"] for r in result["responses"]]
        # Only anger and disgust should respond (in scratchpad order: disgust, anger)
        assert set(emotions) == {"anger", "disgust"}


# ---------------------------------------------------------------------------
# 6. Performance logging
# ---------------------------------------------------------------------------

class TestScratchpadLogging:
    def test_elapsed_time_logged(self):
        """Scratchpad mode logs the total execution time."""
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False,
            "anger": False, "fear": False, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Yay! ✨"
        )

        with patch("agents.personality_agents.logger") as mock_logger:
            system.get_responses("Fun times!")

            # Find the scratchpad log message
            log_messages = [
                str(c) for c in mock_logger.info.call_args_list
            ]
            scratchpad_logs = [m for m in log_messages if "Scratchpad" in m]
            assert len(scratchpad_logs) >= 1, (
                f"Expected scratchpad timing log, got: {log_messages}"
            )


# ---------------------------------------------------------------------------
# 7. Response format matches parallel mode
# ---------------------------------------------------------------------------

class TestScratchpadResponseFormat:
    def test_response_dict_has_expected_keys(self):
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False,
            "anger": False, "fear": False, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Yay! ✨"
        )

        result = system.get_responses("Fun times!")

        assert "approved" in result
        assert "monitor_message" in result
        assert "responses" in result
        assert "decisions" in result
        assert "degraded" in result
        assert "degraded_reason" in result

    def test_individual_response_has_expected_keys(self):
        system = _make_system(use_scratchpad=True, use_synthesis=False)

        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False,
            "anger": False, "fear": False, "disgust": False,
        }

        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Yay! ✨"
        )

        result = system.get_responses("Fun times!")

        resp = result["responses"][0]
        assert resp["agent"] == "Joy"
        assert resp["emotion"] == "joy"
        assert resp["emoji"] == "😄"
        assert resp["color"] == "yellow"
        assert "response" in resp
