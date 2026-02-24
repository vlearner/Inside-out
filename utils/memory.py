"""
Conversation memory for the Inside Out multi-agent system.

Provides a rolling-window history that is injected into each LLM call so
personality agents can reference earlier turns in the conversation.
"""
from typing import List, Dict


class ConversationMemory:
    """Rolling-window conversation memory.

    Stores the last *max_turns* user+assistant turn pairs as a flat list of
    ``{"role": "user"|"assistant", "content": "..."}`` dicts — the format
    already understood by the LLM chat API.

    Args:
        max_turns: Maximum number of user+assistant pairs to retain.
                   Older pairs are dropped when the window is exceeded.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns
        self._history: List[Dict[str, str]] = []

    def add_user_message(self, content: str) -> None:
        """Append a user message to the history."""
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_agent_response(self, agent_name: str, content: str) -> None:
        """Append an agent response to the history.

        The *content* should be the raw LLM text (not the already-formatted
        ``"😄 **Joy**: ..."`` string).  It is tagged with the agent name so
        subsequent agents and future turns can reference the emotional source.

        Example stored string: ``"😄 Joy said: 'Ooh, I love that!'"``
        """
        tagged = f"{agent_name} said: '{content}'"
        self._history.append({"role": "assistant", "content": tagged})
        self._trim()

    def get_context(self) -> List[Dict[str, str]]:
        """Return the capped history slice for injection into an LLM call.

        Returns at most ``max_turns * 2`` messages (``max_turns`` user/assistant
        pairs).
        """
        max_messages = self.max_turns * 2
        return list(self._history[-max_messages:])

    def clear(self) -> None:
        """Empty the conversation history completely."""
        self._history = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        """Keep the internal list within the rolling window."""
        max_messages = self.max_turns * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]
