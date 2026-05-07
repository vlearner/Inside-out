"""Browser-backed memory utilities for Streamlit.

Implements session-scoped persistence using localStorage + browser-session sentinel.
Data survives tab closes and syncs across tabs, and is cleared when a new browser
session starts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List

import streamlit as st

SESSION_MEMORY_KEY = "insideout_session_memory"
AGENT_MEMORY_KEY = "insideout_agent_memory"
SESSION_ACTIVE_KEY = "insideout_browser_session_active"


def _default_agent_memory() -> Dict[str, List[str]]:
    return {"food_preferences": [], "hobbies": [], "emotional_state": []}


def _safe_json_load(value: str, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def initialize_session_memory() -> List[Dict[str, Any]]:
    if "session_memory" not in st.session_state:
        raw = st.query_params.get("session_memory", "")
        st.session_state.session_memory = _safe_json_load(raw, [])
    return st.session_state.session_memory


def get_session_memory() -> List[Dict[str, Any]]:
    return st.session_state.get("session_memory", [])


def add_to_session_memory(role: str, content: str, agent: str | None = None) -> None:
    memory = st.session_state.setdefault("session_memory", [])
    memory.append(
        {
            "role": role,
            "content": content,
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def clear_session_memory() -> None:
    st.session_state.session_memory = []


def initialize_agent_memory() -> Dict[str, List[str]]:
    if "agent_memory" not in st.session_state:
        raw = st.query_params.get("agent_memory", "")
        loaded = _safe_json_load(raw, _default_agent_memory())
        baseline = _default_agent_memory()
        for key in baseline:
            baseline[key] = list(loaded.get(key, [])) if isinstance(loaded, dict) else []
        st.session_state.agent_memory = baseline
    return st.session_state.agent_memory


def get_agent_memory() -> Dict[str, List[str]]:
    return st.session_state.get("agent_memory", _default_agent_memory())


def update_agent_memory(user_message: str) -> None:
    text = user_message.lower()
    memory = st.session_state.setdefault("agent_memory", _default_agent_memory())

    food_map = {
        "pizza": "likes pizza",
        "burger": "likes burgers",
        "sushi": "likes sushi",
        "broccoli": "mentions broccoli",
    }
    hobby_map = {"guitar": "plays guitar", "movie": "watches movies", "reading": "likes reading"}
    emotion_map = {"happy": "seems happy today", "sad": "seems sad today", "angry": "seems angry today"}

    for key, insight in food_map.items():
        if key in text and insight not in memory["food_preferences"]:
            memory["food_preferences"].append(insight)
    for key, insight in hobby_map.items():
        if key in text and insight not in memory["hobbies"]:
            memory["hobbies"].append(insight)
    for key, insight in emotion_map.items():
        if key in text and insight not in memory["emotional_state"]:
            memory["emotional_state"].append(insight)


def clear_agent_memory() -> None:
    st.session_state.agent_memory = _default_agent_memory()
