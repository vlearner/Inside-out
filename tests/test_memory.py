"""
Tests for ConversationMemory — rolling window context.

Covers:
  1. add_user_message / add_agent_response / get_context basic round-trip
  2. Rolling window trim — history never exceeds max_turns exchange pairs
  3. clear() erases all history
  4. get_context() returns a copy (mutations don't affect stored history)
  5. Integration: MultiAgentSystem.memory exists and clear_memory() works
  6. PersonalityAgent.get_response() prepends history to LLM messages

Run with:
    pytest tests/test_memory.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.memory import ConversationMemory
from agents.personality_agents import MultiAgentSystem, PersonalityAgent


# ============================================================================
# ConversationMemory unit tests
# ============================================================================

class TestConversationMemoryBasics:
    """Basic add / get round-trip."""

    def test_empty_on_init(self):
        mem = ConversationMemory()
        assert mem.get_context() == []

    def test_add_user_message(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello!")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0] == {"role": "user", "content": "Hello!"}

    def test_add_agent_response_tagged(self):
        mem = ConversationMemory()
        mem.add_agent_response("Joy", "So exciting! ✨")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0]["role"] == "assistant"
        assert "Joy" in ctx[0]["content"]
        assert "So exciting!" in ctx[0]["content"]

    def test_message_order_preserved(self):
        mem = ConversationMemory()
        mem.add_user_message("Turn 1 user")
        mem.add_agent_response("Joy", "Turn 1 joy")
        mem.add_user_message("Turn 2 user")
        mem.add_agent_response("Sadness", "Turn 2 sadness")
        ctx = mem.get_context()
        assert ctx[0]["role"] == "user"
        assert ctx[1]["role"] == "assistant"
        assert ctx[2]["role"] == "user"
        assert ctx[3]["role"] == "assistant"


class TestConversationMemoryRollingWindow:
    """The window must never grow beyond max_turns exchange pairs."""

    def test_window_not_exceeded(self):
        mem = ConversationMemory(max_turns=2)
        for i in range(4):
            mem.add_user_message(f"user {i}")
            mem.add_agent_response("Joy", f"joy {i}")
        # Only last 2 exchange pairs = 4 messages
        ctx = mem.get_context()
        assert len(ctx) == 4

    def test_oldest_messages_dropped(self):
        mem = ConversationMemory(max_turns=2)
        mem.add_user_message("old user")
        mem.add_agent_response("Joy", "old joy")
        mem.add_user_message("new user")
        mem.add_agent_response("Joy", "new joy")
        mem.add_user_message("newest user")
        mem.add_agent_response("Joy", "newest joy")
        ctx = mem.get_context()
        assert len(ctx) == 4
        # The oldest pair should be gone
        contents = [m["content"] for m in ctx]
        assert not any("old user" in c for c in contents)
        assert not any("old joy" in c for c in contents)

    def test_default_max_turns_is_five(self):
        mem = ConversationMemory()
        assert mem.max_turns == 5
        for i in range(6):
            mem.add_user_message(f"u{i}")
            mem.add_agent_response("Joy", f"j{i}")
        assert len(mem.get_context()) == 10  # 5 pairs × 2

    def test_single_max_turn(self):
        mem = ConversationMemory(max_turns=1)
        mem.add_user_message("first")
        mem.add_agent_response("Joy", "first response")
        mem.add_user_message("second")
        mem.add_agent_response("Joy", "second response")
        ctx = mem.get_context()
        assert len(ctx) == 2
        assert "second" in ctx[0]["content"]


class TestConversationMemoryClear:
    """clear() must wipe all stored history."""

    def test_clear_empties_history(self):
        mem = ConversationMemory()
        mem.add_user_message("something")
        mem.add_agent_response("Joy", "something back")
        mem.clear()
        assert mem.get_context() == []

    def test_can_add_after_clear(self):
        mem = ConversationMemory()
        mem.add_user_message("before clear")
        mem.clear()
        mem.add_user_message("after clear")
        ctx = mem.get_context()
        assert len(ctx) == 1
        assert ctx[0]["content"] == "after clear"


class TestConversationMemoryIsolation:
    """get_context() must return a copy so callers can't mutate stored history."""

    def test_get_context_returns_copy(self):
        mem = ConversationMemory()
        mem.add_user_message("original")
        ctx = mem.get_context()
        ctx.append({"role": "user", "content": "injected"})
        # Internal state should be unaffected
        assert len(mem.get_context()) == 1


# ============================================================================
# MultiAgentSystem integration tests
# ============================================================================

class TestMultiAgentSystemMemoryIntegration:
    """MultiAgentSystem must own a ConversationMemory and expose clear_memory()."""

    def test_has_memory_attribute(self):
        system = MultiAgentSystem()
        assert hasattr(system, "memory")
        assert isinstance(system.memory, ConversationMemory)

    def test_clear_memory_empties_memory(self):
        system = MultiAgentSystem()
        system.memory.add_user_message("test")
        system.clear_memory()
        assert system.memory.get_context() == []

    def test_get_responses_populates_memory(self):
        """After a successful get_responses call, memory should have 1+ messages."""
        system = MultiAgentSystem()

        mock_client = MagicMock()
        mock_client.chat.return_value = "APPROVE"

        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            system.get_responses("What is your favourite pizza?")

        # At minimum the user message should be recorded
        ctx = system.memory.get_context()
        assert any(m["role"] == "user" for m in ctx)

    def test_memory_cleared_after_clear_memory(self):
        """clear_memory() removes all messages added by get_responses()."""
        system = MultiAgentSystem()

        mock_client = MagicMock()
        mock_client.chat.return_value = "APPROVE"

        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            system.get_responses("What is your favourite pizza?")

        system.clear_memory()
        assert system.memory.get_context() == []


# ============================================================================
# PersonalityAgent history prepend tests
# ============================================================================

class TestPersonalityAgentHistory:
    """history parameter must be prepended between system prompt and user message."""

    def test_history_prepended_to_messages(self):
        agent = PersonalityAgent("joy", enabled=True)
        history = [
            {"role": "user", "content": "I asked something earlier"},
            {"role": "assistant", "content": "Joy said: Earlier response"},
        ]

        captured_messages = []

        def fake_chat(messages, max_tokens=None):
            captured_messages.extend(messages)
            return "Great response!"

        mock_client = MagicMock()
        mock_client.chat.side_effect = fake_chat

        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            agent.get_response("What's your favourite colour?", history=history)

        # system → history[0] → history[1] → new user message
        assert len(captured_messages) >= 4
        assert captured_messages[0]["role"] == "system"
        assert captured_messages[1] == history[0]
        assert captured_messages[2] == history[1]
        assert captured_messages[3]["role"] == "user"

    def test_no_history_still_works(self):
        """Calling get_response without history must behave as before."""
        agent = PersonalityAgent("joy", enabled=True)

        mock_client = MagicMock()
        mock_client.chat.return_value = "So exciting! ✨"

        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            response = agent.get_response("What is your favourite food?")

        assert response is not None
        assert "Joy" in response

    def test_empty_history_still_works(self):
        agent = PersonalityAgent("joy", enabled=True)
        mock_client = MagicMock()
        mock_client.chat.return_value = "Yay! ✨"

        with patch.object(PersonalityAgent, "get_jan_client", return_value=mock_client):
            response = agent.get_response("What's your favourite colour?", history=[])

        assert response is not None
