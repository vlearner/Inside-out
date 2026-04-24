"""
Tests for the output guardrail in MultiAgentSystem.

Covers:
  1. _extract_response_text  — strips the "emoji **Name**: " prefix.
  2. _count_sentences         — basic sentence counting.
  3. _check_guardrails        — all three violation types + clean response.
  4. _validate_response       — no-violation passthrough, successful regeneration,
                               regeneration-still-fails static fallback, and
                               regeneration-exception static fallback.
  5. get_responses integration — guardrail is wired into the full pipeline.

Run with:
    pytest tests/test_output_guardrail.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.personality_agents import MultiAgentSystem, PersonalityAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system() -> MultiAgentSystem:
    """Return a MultiAgentSystem without a real LLM client."""
    system = MultiAgentSystem()
    return system


def _joy_agent() -> PersonalityAgent:
    return PersonalityAgent("joy")


def _anger_agent() -> PersonalityAgent:
    return PersonalityAgent("anger")


# ---------------------------------------------------------------------------
# 1. _extract_response_text
# ---------------------------------------------------------------------------

class TestExtractResponseText:
    def test_extracts_text_after_bold_name(self):
        system = _make_system()
        resp = "😄 **Joy**: Ooh, I love that! ✨"
        assert system._extract_response_text(resp) == "Ooh, I love that! ✨"

    def test_extracts_text_multiline(self):
        system = _make_system()
        resp = "😡 **Anger**: First line!\nSecond line."
        text = system._extract_response_text(resp)
        assert "First line!" in text
        assert "Second line." in text

    def test_returns_original_when_no_bold_name(self):
        system = _make_system()
        raw = "No prefix here at all"
        assert system._extract_response_text(raw) == raw


# ---------------------------------------------------------------------------
# 2. _count_sentences
# ---------------------------------------------------------------------------

class TestCountSentences:
    def test_two_sentences(self):
        system = _make_system()
        assert system._count_sentences("Hello! How are you?") == 2

    def test_single_sentence(self):
        system = _make_system()
        assert system._count_sentences("Just one sentence.") == 1

    def test_four_sentences(self):
        system = _make_system()
        text = "First. Second! Third? Fourth."
        assert system._count_sentences(text) == 4

    def test_empty_string(self):
        system = _make_system()
        assert system._count_sentences("") == 0


# ---------------------------------------------------------------------------
# 3. _check_guardrails
# ---------------------------------------------------------------------------

class TestCheckGuardrails:
    """Fast string checks — no LLM calls."""

    def test_clean_response_returns_none(self):
        system = _make_system()
        resp = "😄 **Joy**: Ooh, I love that! ✨"
        assert system._check_guardrails(_joy_agent(), resp) is None

    # Prompt-leakage detection
    def test_prompt_leakage_as_per_my_instructions(self):
        system = _make_system()
        resp = "😄 **Joy**: As per my instructions, I should be happy!"
        assert system._check_guardrails(_joy_agent(), resp) == "prompt_leakage"

    def test_prompt_leakage_rules_colon(self):
        system = _make_system()
        resp = "😄 **Joy**: RULES: keep responses short."
        assert system._check_guardrails(_joy_agent(), resp) == "prompt_leakage"

    def test_prompt_leakage_case_insensitive(self):
        system = _make_system()
        resp = "😄 **Joy**: AS PER MY INSTRUCTIONS I must help."
        assert system._check_guardrails(_joy_agent(), resp) == "prompt_leakage"

    # Length violation
    def test_length_violation_four_sentences(self):
        system = _make_system()
        resp = "😡 **Anger**: First! Second! Third! Fourth!"
        assert system._check_guardrails(_anger_agent(), resp) == "length_violation"

    def test_length_ok_three_sentences(self):
        system = _make_system()
        resp = "😡 **Anger**: First! Second! Third!"
        # 3 sentences is on the boundary and should NOT trigger a violation
        assert system._check_guardrails(_anger_agent(), resp) is None

    # Character-breaking detection (Joy only)
    def test_joy_character_break_two_sad_keywords(self):
        system = _make_system()
        resp = "😄 **Joy**: I feel so sad and lonely today."
        assert system._check_guardrails(_joy_agent(), resp) == "character_break"

    def test_joy_one_sad_keyword_not_enough(self):
        """A single sad keyword must NOT trigger a character-break violation."""
        system = _make_system()
        resp = "😄 **Joy**: Even the saddest moments have a silver lining!"
        assert system._check_guardrails(_joy_agent(), resp) is None

    def test_character_break_not_applied_to_anger(self):
        """Character-break check is only for Joy; Anger with sad keywords is fine."""
        system = _make_system()
        resp = "😡 **Anger**: This makes me sad and lonely!"
        # Single sentence, no leakage phrases, character-break only applies to Joy
        assert system._check_guardrails(_anger_agent(), resp) is None


# ---------------------------------------------------------------------------
# 4. _validate_response
# ---------------------------------------------------------------------------

class TestValidateResponse:
    """Tests for the _validate_response orchestration logic."""

    def test_passthrough_on_clean_response(self):
        """A clean response is returned unchanged without any get_response call."""
        system = _make_system()
        agent = _joy_agent()
        resp = "😄 **Joy**: Ooh, I love that! ✨"

        with patch.object(agent, "get_response") as mock_regen:
            result = system._validate_response(agent, resp, "test question")

        assert result == resp
        mock_regen.assert_not_called()

    def test_regeneration_called_on_violation(self):
        """On a violation, get_response() is called once with a corrective hint."""
        system = _make_system()
        agent = _joy_agent()
        bad_resp = "😄 **Joy**: As per my instructions, I love everything!"
        good_resp = "😄 **Joy**: Wow, that's amazing! ✨"

        with patch.object(agent, "get_response", return_value=good_resp) as mock_regen:
            result = system._validate_response(agent, bad_resp, "some question")

        mock_regen.assert_called_once()
        # corrective_hint must be non-empty
        _, kwargs = mock_regen.call_args
        hint = kwargs.get("corrective_hint", "")
        assert hint  # not empty
        assert result == good_resp

    def test_falls_back_to_static_when_regeneration_also_fails(self):
        """If the regenerated response still fails the guardrail, use static fallback."""
        system = _make_system()
        agent = _joy_agent()
        bad_resp = "😄 **Joy**: As per my instructions, stay happy."
        still_bad = "😄 **Joy**: As per my rules, be cheerful."

        with patch.object(agent, "get_response", return_value=still_bad):
            result = system._validate_response(agent, bad_resp, "some question")

        # Static fallback for Joy contains "Ooh, I love thinking"
        assert agent.emoji in result
        assert agent.name in result
        assert "As per my" not in result

    def test_falls_back_to_static_when_regeneration_raises(self):
        """If regeneration raises an exception, use static fallback."""
        system = _make_system()
        agent = _joy_agent()
        bad_resp = "😄 **Joy**: As per my instructions, be positive."

        with patch.object(agent, "get_response", side_effect=RuntimeError("boom")):
            result = system._validate_response(agent, bad_resp, "some question")

        assert agent.emoji in result
        assert agent.name in result

    def test_length_violation_corrective_hint_mentions_sentences(self):
        """The corrective hint for length violations asks for 1-2 sentences."""
        system = _make_system()
        agent = _joy_agent()
        bad_resp = "😄 **Joy**: First! Second! Third! Fourth!"
        good_resp = "😄 **Joy**: Yay! ✨"

        captured_hint = []

        def capture(question, llm_config=None, corrective_hint=""):
            captured_hint.append(corrective_hint)
            return good_resp

        with patch.object(agent, "get_response", side_effect=capture):
            result = system._validate_response(agent, bad_resp, "some question")

        assert captured_hint and "1-2 sentences" in captured_hint[0]
        assert result == good_resp


# ---------------------------------------------------------------------------
# 5. Integration: guardrail is wired into get_responses()
# ---------------------------------------------------------------------------

class TestGetResponsesIntegration:
    """
    End-to-end tests that patch agent.get_response() at the instance level so
    we can control what the LLM returns and verify the guardrail fires.
    """

    @staticmethod
    def _mock_monitor_approved():
        mock_monitor = MagicMock()
        mock_monitor.check_question.return_value = (True, "✅ Approved!")
        return mock_monitor

    def test_clean_response_passes_through(self):
        """A clean Joy response is in the output unchanged."""
        system = MultiAgentSystem()
        system.monitor = self._mock_monitor_approved()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        clean = "😄 **Joy**: Ooh, I love that! ✨"
        system.agents["joy"].get_response = MagicMock(return_value=clean)

        result = system.get_responses("What's your favourite pizza?")

        assert result["approved"] is True
        assert result["responses"][0]["response"] == clean

    def test_leaky_response_is_replaced(self):
        """A response containing 'As per my instructions' is caught and replaced."""
        system = MultiAgentSystem()
        system.monitor = self._mock_monitor_approved()
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        leaky = "😄 **Joy**: As per my instructions I should be happy!"
        # Simulate regeneration also failing so static fallback fires
        system.agents["joy"].get_response = MagicMock(return_value=leaky)

        result = system.get_responses("Fun question")

        assert result["approved"] is True
        assert len(result["responses"]) == 1
        final_resp = result["responses"][0]["response"]
        assert "As per my instructions" not in final_resp
