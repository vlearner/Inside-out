"""
Streamlit UI for Inside Out Multi-Agent System
Modern GROUP CHAT with Decision Agent for intelligent routing
Features: @mentions, intelligent response selection, personality reactions
"""
import streamlit as st
import time
import sys
import os
import random
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import MultiAgentSystem
from utils.jan_client import JanClient, JanClientError

# Page configuration
st.set_page_config(
    page_title="🎭 Inside Out Friends Chat",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Emotion friends configuration
EMOTION_FRIENDS = {
    "joy": {
        "name": "Joy", 
        "emoji": "😊", 
        "color": "#FFD700",
        "status": "Always happy! ✨",
        "base_delay": 0.5,
    },
    "sadness": {
        "name": "Sadness", 
        "emoji": "😢", 
        "color": "#4169E1",
        "status": "It's okay to feel blue...",
        "base_delay": 1.5,
    },
    "anger": {
        "name": "Anger", 
        "emoji": "😠", 
        "color": "#DC143C",
        "status": "JUSTICE! 🔥",
        "base_delay": 0.8,
    },
    "fear": {
        "name": "Fear", 
        "emoji": "😨", 
        "color": "#9370DB",
        "status": "Stay safe! ⚠️",
        "base_delay": 1.2,
    },
    "disgust": {
        "name": "Disgust", 
        "emoji": "🤢", 
        "color": "#228B22",
        "status": "High standards 💅",
        "base_delay": 1.0,
    },
}


# Available tools configuration
AVAILABLE_TOOLS = {
    "weather": {
        "name": "Weather Lookup",
        "emoji": "🌤️",
        "description": "Get current weather and forecasts for any location",
        "module": "tools.weather_tool",
    },
}


def test_ai_model_connection() -> dict:
    """
    Test connectivity to the Jan AI server and return status details.

    Returns:
        dict with keys: connected (bool), model (str), base_url (str), error (str|None)
    """
    try:
        client = JanClient()
        connected = client.test_connection()
        return {
            "connected": connected,
            "model": client.model_name,
            "base_url": client.base_url,
            "error": None if connected else "Server is not responding",
        }
    except JanClientError as exc:
        return {
            "connected": False,
            "model": "N/A",
            "base_url": "N/A",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "connected": False,
            "model": "N/A",
            "base_url": "N/A",
            "error": str(exc),
        }


def parse_mentions(message: str) -> tuple[list, str]:
    """
    Parse @mentions from message.
    Returns: (list of mentioned emotions, cleaned message)
    """
    mentioned = []
    clean_message = message
    
    for emotion in EMOTION_FRIENDS.keys():
        pattern = rf'@{emotion}\b'
        if re.search(pattern, message.lower()):
            mentioned.append(emotion)
            clean_message = re.sub(pattern, '', message, flags=re.IGNORECASE).strip()
    
    return mentioned, clean_message


def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "agent_system" not in st.session_state:
        st.session_state.agent_system = MultiAgentSystem()
    
    if "active_friends" not in st.session_state:
        st.session_state.active_friends = {
            "joy": True,
            "sadness": True,
            "anger": True,
            "fear": True,
            "disgust": True
        }
    
    if "pending_responses" not in st.session_state:
        st.session_state.pending_responses = []

    if "enabled_tools" not in st.session_state:
        st.session_state.enabled_tools = {tool: True for tool in AVAILABLE_TOOLS}


def get_single_response(agent_system, emotion: str, message: str):
    """Get response from a single emotion agent"""
    agent = agent_system.agents.get(emotion)
    if agent and agent.enabled:
        response = agent.get_response(message)
        if response:
            response_text = response
            if "**:" in response_text:
                parts = response_text.split("**:", 1)
                if len(parts) > 1:
                    response_text = parts[1].strip()
            return response_text
    return None


def main():
    """Main Streamlit app with Decision Agent"""
    initialize_session_state()
    
    # === SIDEBAR ===
    with st.sidebar:
        st.header("🎭 Friends in Chat")
        st.write("Toggle who's online:")
        
        for emotion, config in EMOTION_FRIENDS.items():
            st.session_state.active_friends[emotion] = st.checkbox(
                f"{config['emoji']} {config['name']}",
                value=st.session_state.active_friends[emotion],
                key=f"toggle_{emotion}",
                help=config['status']
            )
        
        st.divider()
        
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_responses = []
            st.rerun()
        
        # --- Test AI Model Connection ---
        if st.button("🔌 Test AI Model Connection", use_container_width=True):
            with st.spinner("Testing connection to Jan AI server..."):
                status = test_ai_model_connection()
            if status["connected"]:
                st.success(
                    f"✅ Connected!\n\n"
                    f"**Model:** {status['model']}\n\n"
                    f"**URL:** {status['base_url']}"
                )
            else:
                st.error(
                    f"❌ Connection failed\n\n"
                    f"**Error:** {status['error']}\n\n"
                    f"Make sure Jan AI server is running."
                )

        st.divider()

        # --- Tools Section ---
        st.subheader("🛠️ Tools")
        st.write("Enable/disable agent tools:")

        for tool_key, tool_config in AVAILABLE_TOOLS.items():
            st.session_state.enabled_tools[tool_key] = st.checkbox(
                f"{tool_config['emoji']} {tool_config['name']}",
                value=st.session_state.enabled_tools.get(tool_key, True),
                key=f"tool_{tool_key}",
                help=tool_config["description"],
            )

        # Show tool connection status when a tool is enabled
        for tool_key, enabled in st.session_state.enabled_tools.items():
            if enabled:
                tool_config = AVAILABLE_TOOLS[tool_key]
                st.caption(f"  ↳ {tool_config['emoji']} {tool_config['name']} — active")
            else:
                tool_config = AVAILABLE_TOOLS[tool_key]
                st.caption(f"  ↳ {tool_config['emoji']} {tool_config['name']} — disabled")

        st.divider()
        st.subheader("💬 How to Chat")
        st.markdown("""
        **Direct message:**
        `@joy What's fun today?`
        
        **Ask the group:**
        Type without @ and the Decision Agent picks who responds!
        
        🧠 *Smart routing - not everyone responds to everything!*
        """)
    
    # === MAIN CONTENT ===
    st.title("🎭 Inside Out Friends Chat")
    
    # Online friends display
    active_friends = [e for e, a in st.session_state.active_friends.items() if a]
    if active_friends:
        friend_display = " ".join([f"{EMOTION_FRIENDS[e]['emoji']}" for e in active_friends])
        st.caption(f"**Online:** {friend_display}")
        mention_hints = " ".join([f"`@{e}`" for e in active_friends])
        st.caption(f"Mention: {mention_hints}")
    else:
        st.warning("⚠️ No friends online!")
    
    st.divider()
    
    # Chat display
    if not st.session_state.messages:
        st.info("👋 **Welcome!** Chat with your emotion friends!")
        st.markdown("""
        **Try these:**
        - `@joy What's your favorite food?` - Ask Joy directly
        - `What's the worst fashion trend?` - Decision Agent picks Disgust!
        - `I'm worried about something` - Fear might respond
        """)
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    display_text = msg["content"]
                    for emotion in EMOTION_FRIENDS:
                        display_text = re.sub(
                            rf'@{emotion}\b',
                            f'**@{emotion}**',
                            display_text,
                            flags=re.IGNORECASE
                        )
                    st.markdown(display_text)
            elif msg["role"] == "friend":
                emotion = msg.get("emotion", "joy")
                config = EMOTION_FRIENDS.get(emotion, EMOTION_FRIENDS["joy"])
                was_mentioned = msg.get("was_mentioned", False)
                
                with st.chat_message("assistant", avatar=config["emoji"]):
                    if was_mentioned:
                        st.markdown(f"**{config['name']}** 💬")
                    else:
                        st.markdown(f"**{config['name']}**")
                    st.write(msg["content"])
            elif msg["role"] == "system":
                st.warning(f"🚦 {msg['content']}")
            elif msg["role"] == "decision":
                st.caption(f"🧠 {msg['content']}")
    
    # Process pending responses with typing indicators
    if st.session_state.pending_responses:
        pending = st.session_state.pending_responses.pop(0)
        emotion = pending["emotion"]
        config = EMOTION_FRIENDS[emotion]
        
        typing_placeholder = st.empty()
        typing_placeholder.info(f"{config['emoji']} **{config['name']}** is typing...")
        
        time.sleep(pending.get("delay", 1.0))
        
        # Prefer the already-computed response; only re-fetch if it's absent
        response_text = pending.get("cached_response") or get_single_response(
            st.session_state.agent_system, emotion, pending["message"]
        )

        typing_placeholder.empty()
        
        if response_text:
            st.session_state.messages.append({
                "role": "friend",
                "emotion": emotion,
                "content": response_text,
                "was_mentioned": pending.get("was_mentioned", False)
            })
        
        st.rerun()
    
    st.divider()
    
    # Input
    user_input = st.chat_input("Message (use @joy, @anger, etc. for direct chat)")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        agent_system = st.session_state.agent_system
        
        # Update agent states
        for emotion, active in st.session_state.active_friends.items():
            agent_system.agents[emotion].enabled = active
        
        # Parse mentions
        mentioned, clean_message = parse_mentions(user_input)
        
        # Get responses via Decision Agent
        result = agent_system.get_responses(user_input, mentioned=mentioned if mentioned else None)
        
        if not result["approved"]:
            if "**Monitor**:" in result["monitor_message"]:
                msg = result["monitor_message"].split("**Monitor**:")[-1].strip()
            else:
                msg = result["monitor_message"]
            st.session_state.messages.append({
                "role": "system",
                "content": msg
            })
            st.rerun()
        
        # Show decision info if no mentions (Decision Agent made the call)
        if not mentioned and result.get("decisions"):
            responders = [e for e, v in result["decisions"].items() if v and st.session_state.active_friends.get(e, False)]
            if responders:
                names = ", ".join([EMOTION_FRIENDS[e]["name"] for e in responders])
                st.session_state.messages.append({
                    "role": "decision",
                    "content": f"Decision Agent selected: {names}"
                })
        
        # Queue responses with typing delays
        pending = []
        for resp in result["responses"]:
            emotion = resp.get("emotion", resp["agent"].lower())
            if st.session_state.active_friends.get(emotion, False):
                config = EMOTION_FRIENDS.get(emotion, {})
                # Strip the raw response text (remove "emoji **Name**: " prefix)
                response_text = resp.get("response", "")
                if "**:" in response_text:
                    parts = response_text.split("**:", 1)
                    if len(parts) > 1:
                        response_text = parts[1].strip()
                pending.append({
                    "emotion": emotion,
                    "delay": config.get("base_delay", 1.0),
                    "message": clean_message,   # @mention-stripped message
                    "was_mentioned": emotion in (mentioned or []),
                    "cached_response": response_text,  # use this; skip re-fetch
                })
        
        # Sort: mentioned first, then by delay
        pending.sort(key=lambda x: (0 if x["was_mentioned"] else 1, x["delay"]))
        
        st.session_state.pending_responses = pending
        st.rerun()
    
    # Footer
    st.divider()
    st.caption("🎬 Inspired by Pixar's Inside Out | 🧠 Decision Agent routes your messages!")


if __name__ == "__main__":
    main()
