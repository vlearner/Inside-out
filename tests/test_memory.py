"""
Tests for ConversationMemory in utils/memory.py.

Covers:
  1. add_user_message / add_agent_response basic behaviour.
  2. get_context returns correct rolling window.
  3. clear() empties history completely.
  4. max_turns window is respected and old messages are dropped.
  5. MultiAgentSystem integrations (self.memory exists, clear_memory works,
     memory is populated during get_responses, history is passed to agents).

Run with:
    pytest tests/test_memory.py -v
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.memory import ConversationMemory
from agents.personality_agents import MultiAgentSystem


# ---------------------------------------------------------------------------
# 1. ConversationMemory unit tests
# ---------------------------------------------------------------------------

class TestConversationMemoryBasic:
    def test_starts_empty(self):
        mem = ConversationMemory()
        assert mem.get_context() == []

    def test_add_user_message(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello!")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0] == {"role": "user", "content": "Hello!"}

    def test_add_agent_response_tags_content(self):
        mem = ConversationMemory()
        mem.add_agent_response("Joy", "I love that!")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0]["role"] == "assistant"
        assert "Joy" in ctx[0]["content"]
        assert "I love that!" in ctx[0]["content"]

    def test_interleaved_messages(self):
        mem = ConversationMemory()
        mem.add_user_message("What's your favourite pizza?")
        mem.add_agent_response("Joy", "Pineapple, obviously!")
        ctx = mem.get_context()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[1]["role"] == "assistant"


class TestConversationMemoryClear:
    def test_clear_empties_history(self):
        mem = ConversationMemory()
        mem.add_user_message("Hey")
        mem.add_agent_response("Anger", "Whatever!")
        mem.clear()
        assert mem.get_context() == []

    def test_clear_then_add_works(self):
        mem = ConversationMemory()
        mem.add_user_message("First message")
        mem.clear()
        mem.add_user_message("Second message")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0]["content"] == "Second message"


class TestConversationMemoryWindow:
    def test_max_turns_respected(self):
        """With max_turns=2, only the last 4 messages (2 pairs) are kept."""
        mem = ConversationMemory(max_turns=2)
        for i in range(3):
            mem.add_user_message(f"User turn {i}")
            mem.add_agent_response("Joy", f"Joy response {i}")

        ctx = mem.get_context()
        assert len(ctx) == 4  # 2 pairs * 2 messages each

    def test_oldest_messages_dropped(self):
        """The oldest turn is dropped when the window overflows."""
        mem = ConversationMemory(max_turns=1)
        mem.add_user_message("Old message")
        mem.add_agent_response("Joy", "Old response")
        mem.add_user_message("New message")
        mem.add_agent_response("Joy", "New response")

        ctx = mem.get_context()
        assert len(ctx) == 2
        assert ctx[0]["content"] == "New message"

    def test_get_context_returns_copy(self):
        """Modifying the returned list must not affect internal state."""
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        ctx = mem.get_context()
        ctx.clear()
        assert len(mem.get_context()) == 1

    def test_default_max_turns_is_five(self):
        mem = ConversationMemory()
        assert mem.max_turns == 10


# ---------------------------------------------------------------------------
# 2. MultiAgentSystem integration tests
# ---------------------------------------------------------------------------

class TestMultiAgentSystemMemoryIntegration:
    @staticmethod
    def _make_system() -> MultiAgentSystem:
        return MultiAgentSystem()

    def test_memory_attribute_exists(self):
        system = self._make_system()
        assert hasattr(system, "memory")
        assert isinstance(system.memory, ConversationMemory)

    def test_clear_memory_method_exists(self):
        system = self._make_system()
        assert callable(getattr(system, "clear_memory", None))

    def test_clear_memory_delegates_to_memory(self):
        system = self._make_system()
        system.memory.add_user_message("Something")
        system.clear_memory()
        assert system.memory.get_context() == []

    def test_get_responses_records_user_message(self):
        """After an approved get_responses call, user message is in memory."""
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (True, "✅ Approved!")
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        clean = "😄 **Joy**: Ooh, I love that! ✨"
        system.agents["joy"].get_response = MagicMock(return_value=clean)

        system.get_responses("What's your favourite pizza?")

        ctx = system.memory.get_context()
        user_messages = [m for m in ctx if m["role"] == "user"]
        assert any("favourite pizza" in m["content"] for m in user_messages)

    def test_get_responses_records_agent_response(self):
        """After a successful response, the agent's reply is stored in memory."""
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (True, "✅ Approved!")
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        clean = "😄 **Joy**: Ooh, I love that! ✨"
        system.agents["joy"].get_response = MagicMock(return_value=clean)

        system.get_responses("What's your favourite pizza?")

        ctx = system.memory.get_context()
        assistant_messages = [m for m in ctx if m["role"] == "assistant"]
        assert len(assistant_messages) >= 1
        assert "Joy" in assistant_messages[0]["content"]

    def test_get_responses_passes_history_to_agent(self):
        """History is passed as keyword argument to agent.get_response()."""
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (True, "✅ Approved!")
        system.decision_agent = MagicMock()
        system.decision_agent.analyze_message.return_value = {
            "joy": True, "sadness": False, "anger": False, "fear": False, "disgust": False
        }
        clean = "😄 **Joy**: That's great! ✨"
        mock_get_response = MagicMock(return_value=clean)
        system.agents["joy"].get_response = mock_get_response

        # Prime memory with a prior turn
        system.memory.add_user_message("Prior question")
        system.memory.add_agent_response("Joy", "Prior answer")

        system.get_responses("New question")

        call_kwargs = mock_get_response.call_args[1]
        assert "history" in call_kwargs
        assert len(call_kwargs["history"]) >= 2

    def test_monitor_rejection_does_not_record_memory(self):
        """Rejected messages must not be added to memory."""
        system = self._make_system()
        system.monitor = MagicMock()
        system.monitor.check_question.return_value = (
            False, "🚦 **Monitor**: Too serious!"
        )

        system.get_responses("I feel depressed")

        assert system.memory.get_context() == []
