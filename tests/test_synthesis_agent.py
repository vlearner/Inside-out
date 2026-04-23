"""
Tests for the SynthesisAgent and its integration with MultiAgentSystem.

Covers:
  1. _is_echo           — verbatim echo detection.
  2. _check_quality      — echo + length violation detection.
  3. review_responses     — regeneration on echo/length violations.
  4. generate_headline    — LLM headline, LLM fallback, and deterministic fallback.
  5. MultiAgentSystem integration — synthesis field, use_synthesis flag, single-agent
                                    responses.

Run with:
    pytest tests/test_synthesis_agent.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.personality_agents import SynthesisAgent, MultiAgentSystem, PersonalityAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system(**kwargs) -> MultiAgentSystem:
    """Return a MultiAgentSystem with mocked monitor (always approves)."""
    system = MultiAgentSystem(**kwargs)
    system.monitor = MagicMock()
    system.monitor.check_question.return_value = (True, "✅ Approved!")
    return system


def _joy_entry(text: str = "Ooh, I love that! ✨") -> dict:
    return {
        "agent": "Joy",
        "emotion": "joy",
        "emoji": "😄",
        "color": "yellow",
        "response": f"😄 **Joy**: {text}",
    }


def _anger_entry(text: str = "That fires me up! 😤") -> dict:
    return {
        "agent": "Anger",
        "emotion": "anger",
        "emoji": "😡",
        "color": "red",
        "response": f"😡 **Anger**: {text}",
    }


# ---------------------------------------------------------------------------
# 1. _is_echo
# ---------------------------------------------------------------------------

class TestIsEcho:
    def test_verbatim_echo_detected(self):
        synth = SynthesisAgent()
        assert synth._is_echo(
            "What's your favourite pizza?",
            "What's your favourite pizza? I love it!",
        ) is True

    def test_case_insensitive_echo(self):
        synth = SynthesisAgent()
        assert synth._is_echo(
            "WHAT IS YOUR FAVOURITE PIZZA",
            "what is your favourite pizza — yum!",
        ) is True

    def test_no_echo_when_different(self):
        synth = SynthesisAgent()
        assert synth._is_echo(
            "What's your favourite pizza?",
            "Ooh, I love thinking about food! ✨",
        ) is False

    def test_empty_question_not_echo(self):
        synth = SynthesisAgent()
        assert synth._is_echo("", "Some response") is False

    def test_whitespace_stripped(self):
        synth = SynthesisAgent()
        assert synth._is_echo(
            "  hello  ",
            "hello world",
        ) is True


# ---------------------------------------------------------------------------
# 2. _check_quality
# ---------------------------------------------------------------------------

class TestCheckQuality:
    def test_clean_response_returns_none(self):
        synth = SynthesisAgent()
        assert synth._check_quality(
            "What's your favourite pizza?",
            "Ooh, I love that! ✨",
        ) is None

    def test_echo_violation(self):
        synth = SynthesisAgent()
        assert synth._check_quality(
            "What's your favourite pizza?",
            "What's your favourite pizza? That's great!",
        ) == "echo"

    def test_length_violation(self):
        synth = SynthesisAgent()
        assert synth._check_quality(
            "Tell me something",
            "First. Second. Third. Fourth.",
        ) == "length_violation"

    def test_three_sentences_ok(self):
        synth = SynthesisAgent()
        assert synth._check_quality(
            "Tell me something",
            "First. Second. Third.",
        ) is None

    def test_echo_takes_priority_over_length(self):
        """When both echo and length violations exist, echo is reported first."""
        synth = SynthesisAgent()
        assert synth._check_quality(
            "Hello there",
            "Hello there is nice. One. Two. Three. Four.",
        ) == "echo"


# ---------------------------------------------------------------------------
# 3. review_responses — regeneration behaviour
# ---------------------------------------------------------------------------

class TestReviewResponses:
    def test_clean_responses_pass_through(self):
        synth = SynthesisAgent()
        entries = [_joy_entry(), _anger_entry()]
        agents = {
            "joy": PersonalityAgent("joy"),
            "anger": PersonalityAgent("anger"),
        }
        reviewed, headline = synth.review_responses(
            "What's your favourite pizza?", entries, agents
        )
        assert len(reviewed) == 2
        assert reviewed[0]["response"] == entries[0]["response"]
        assert reviewed[1]["response"] == entries[1]["response"]

    def test_echo_triggers_regeneration(self):
        """An echoing response triggers one regeneration with a corrective hint."""
        synth = SynthesisAgent()
        echo_entry = _joy_entry("What's your favourite pizza? I love pizza!")
        good_response = "😄 **Joy**: Pizza makes me so happy! ✨"

        agent = PersonalityAgent("joy")
        agent.get_response = MagicMock(return_value=good_response)

        reviewed, _ = synth.review_responses(
            "What's your favourite pizza?",
            [echo_entry],
            {"joy": agent},
        )

        agent.get_response.assert_called_once()
        _, kwargs = agent.get_response.call_args
        assert "corrective_hint" in kwargs
        assert "Do NOT repeat or echo" in kwargs["corrective_hint"]
        assert reviewed[0]["response"] == good_response

    def test_length_violation_triggers_regeneration(self):
        """A response with >3 sentences triggers one regeneration."""
        synth = SynthesisAgent()
        long_entry = _joy_entry("First! Second! Third! Fourth!")
        good_response = "😄 **Joy**: So exciting! ✨"

        agent = PersonalityAgent("joy")
        agent.get_response = MagicMock(return_value=good_response)

        reviewed, _ = synth.review_responses(
            "Tell me something fun",
            [long_entry],
            {"joy": agent},
        )

        agent.get_response.assert_called_once()
        _, kwargs = agent.get_response.call_args
        assert "1-2 sentences" in kwargs["corrective_hint"]
        assert reviewed[0]["response"] == good_response

    def test_keeps_original_when_regeneration_still_fails(self):
        """If the regenerated response also fails, the original is kept."""
        synth = SynthesisAgent()
        echo_entry = _joy_entry("What's your favourite pizza? It's pizza!")
        still_bad = "😄 **Joy**: What's your favourite pizza? Me too!"

        agent = PersonalityAgent("joy")
        agent.get_response = MagicMock(return_value=still_bad)

        reviewed, _ = synth.review_responses(
            "What's your favourite pizza?",
            [echo_entry],
            {"joy": agent},
        )

        assert reviewed[0]["response"] == echo_entry["response"]

    def test_keeps_original_when_regeneration_raises(self):
        """If regeneration raises, the original is kept."""
        synth = SynthesisAgent()
        echo_entry = _joy_entry("What's your favourite pizza? Love it!")

        agent = PersonalityAgent("joy")
        agent.get_response = MagicMock(side_effect=RuntimeError("boom"))

        reviewed, _ = synth.review_responses(
            "What's your favourite pizza?",
            [echo_entry],
            {"joy": agent},
        )

        assert reviewed[0]["response"] == echo_entry["response"]


# ---------------------------------------------------------------------------
# 4. generate_headline
# ---------------------------------------------------------------------------

class TestGenerateHeadline:
    def test_fallback_headline_two_agents(self):
        """With no LLM, a deterministic fallback headline is produced for 2 agents."""
        synth = SynthesisAgent()
        entries = [_joy_entry(), _anger_entry()]

        with patch.object(PersonalityAgent, "get_llm_client", return_value=None):
            headline = synth.generate_headline("test question", entries)

        assert "Joy" in headline
        assert "Anger" in headline

    def test_fallback_headline_three_agents(self):
        synth = SynthesisAgent()
        entries = [
            _joy_entry(),
            _anger_entry(),
            {
                "agent": "Fear", "emotion": "fear", "emoji": "😰",
                "color": "purple", "response": "😰 **Fear**: Oh no! 😰",
            },
        ]
        with patch.object(PersonalityAgent, "get_llm_client", return_value=None):
            headline = synth.generate_headline("test", entries)

        assert "Joy" in headline
        assert "Anger" in headline
        assert "Fear" in headline

    def test_llm_headline_used_when_available(self):
        synth = SynthesisAgent()
        entries = [_joy_entry(), _anger_entry()]
        mock_client = MagicMock()
        mock_client.chat.return_value = "Joy is thrilled but Anger wants a word!"

        with patch.object(PersonalityAgent, "get_llm_client", return_value=mock_client):
            headline = synth.generate_headline("test", entries)

        assert headline == "Joy is thrilled but Anger wants a word!"
        mock_client.chat.assert_called_once()

    def test_llm_exception_falls_back(self):
        synth = SynthesisAgent()
        entries = [_joy_entry(), _anger_entry()]
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("LLM down")

        with patch.object(PersonalityAgent, "get_llm_client", return_value=mock_client):
            headline = synth.generate_headline("test", entries)

        assert "Joy" in headline
        assert "Anger" in headline

    def test_no_headline_for_single_response(self):
        """review_responses returns None headline when only 1 agent responded."""
        synth = SynthesisAgent()
        entries = [_joy_entry()]
        agents = {"joy": PersonalityAgent("joy")}

        reviewed, headline = synth.review_responses("test", entries, agents)
        assert headline is None


# ---------------------------------------------------------------------------
# 5. MultiAgentSystem integration
# ---------------------------------------------------------------------------

class TestMultiAgentSystemSynthesisIntegration:

    def test_synthesis_field_present_two_agents(self):
        """When 2+ agents respond, the result contains a non-None 'synthesis' field."""
        system = _make_system()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": True, "fear": False, "disgust": False
        }
        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Ooh, I love that! ✨"
        )
        system.agents["anger"].get_response = MagicMock(
            return_value="😡 **Anger**: That fires me up! 😤"
        )

        result = system.get_responses("What's your favourite pizza?")

        assert result["approved"] is True
        assert "synthesis" in result
        assert result["synthesis"] is not None
        assert isinstance(result["synthesis"], str)

    def test_synthesis_field_none_single_agent(self):
        """When only 1 agent responds, 'synthesis' is None."""
        system = _make_system()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        system.agents["joy"].get_response = MagicMock(
            return_value="😄 **Joy**: Ooh, I love that! ✨"
        )

        result = system.get_responses("What's your favourite pizza?")

        assert result["approved"] is True
        assert result["synthesis"] is None

    def test_use_synthesis_false_no_extra_calls(self):
        """When use_synthesis=False, no extra LLM calls are made."""
        system = _make_system(use_synthesis=False)
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": True, "fear": False, "disgust": False
        }
        joy_resp = "😄 **Joy**: Ooh, I love that! ✨"
        anger_resp = "😡 **Anger**: That fires me up! 😤"
        system.agents["joy"].get_response = MagicMock(return_value=joy_resp)
        system.agents["anger"].get_response = MagicMock(return_value=anger_resp)

        result = system.get_responses("What's your favourite pizza?")

        assert result["approved"] is True
        assert result["synthesis"] is None
        # Each agent's get_response called exactly once — no regeneration from synthesis
        system.agents["joy"].get_response.assert_called_once()
        system.agents["anger"].get_response.assert_called_once()

    def test_echo_response_triggers_synthesis_regeneration(self):
        """An echoing response is caught by the synthesis agent and regenerated."""
        system = _make_system()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        question = "What's your favourite pizza?"
        echo_resp = f"😄 **Joy**: {question} I love it!"
        good_resp = "😄 **Joy**: Pizza makes me dance! ✨"

        # First call returns the echo, second (regeneration) returns good
        system.agents["joy"].get_response = MagicMock(
            side_effect=[echo_resp, good_resp]
        )

        result = system.get_responses(question)

        assert result["approved"] is True
        final = result["responses"][0]["response"]
        assert question.lower() not in final.lower()

    def test_length_violation_triggers_synthesis_regeneration(self):
        """A >3-sentence response is caught by the synthesis agent and regenerated."""
        system = _make_system()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        long_resp = "😄 **Joy**: First! Second! Third! Fourth!"
        good_resp = "😄 **Joy**: Yay! ✨"

        system.agents["joy"].get_response = MagicMock(
            side_effect=[long_resp, good_resp]
        )

        result = system.get_responses("Tell me something fun")

        assert result["approved"] is True
        # The final response should be the shorter one
        final_text = result["responses"][0]["response"]
        assert "Fourth" not in final_text

    def test_synthesis_attribute_exists(self):
        system = MultiAgentSystem()
        assert hasattr(system, "synthesis_agent")
        assert isinstance(system.synthesis_agent, SynthesisAgent)
        assert hasattr(system, "use_synthesis")
        assert system.use_synthesis is True

    def test_rejected_message_has_no_synthesis(self):
        """Rejected messages return no synthesis field (or None)."""
        system = MultiAgentSystem()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            False, "🚦 **Monitor**: Too serious!"
        )

        result = system.get_responses("I feel depressed")
        # Rejected results should not crash; synthesis is absent or None
        assert result["approved"] is False
        assert result.get("synthesis") is None
