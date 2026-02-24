"""
ConversationMemory — rolling window context for personality agents.

Keeps the last `max_turns` user/assistant exchange pairs and exposes them
as a messages list that can be prepended to any LLM call.
"""
from typing import List, Dict


class ConversationMemory:
    """
    Rolling window conversation memory.

    Stores conversation history as a list of ``{"role": ..., "content": ...}``
    dicts (the format LLMs already expect).  Only the most recent `max_turns`
    *exchange pairs* (one user message + one or more agent responses per turn)
    are kept; older messages are silently discarded.

    Args:
        max_turns: Maximum number of user/assistant exchange pairs to retain.
                   Defaults to 5.
    """

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self._history: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """Append a user message to history."""
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_agent_response(self, agent_name: str, content: str) -> None:
        """Append an agent response tagged with the agent's name."""
        tagged = f"{agent_name} said: {content}"
        self._history.append({"role": "assistant", "content": tagged})
        self._trim()

    def get_context(self) -> List[Dict[str, str]]:
        """Return the current history slice as a messages list for the LLM."""
        return list(self._history)

    def clear(self) -> None:
        """Erase all stored history (call on session reset)."""
        self._history = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        """Keep only the last `max_turns` exchange pairs (2 * max_turns messages)."""
        max_messages = self.max_turns * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]
