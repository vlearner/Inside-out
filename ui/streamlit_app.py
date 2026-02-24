"""
Streamlit UI for Inside Out Multi-Agent System
Modern GROUP CHAT with Decision Agent for intelligent routing
Features: @mentions with autocomplete, colored tags, conversation starters,
          intelligent response selection, personality reactions
"""
import streamlit as st
import time
import sys
import os
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

# ── Custom CSS for colored mentions, starters, and autocomplete ──
st.markdown("""
<style>
/* Colored @mention tags in chat */
.mention-tag {
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.95em;
}

/* Starter card styling */
.starter-card {
    background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
    border: 1px solid #3d3d5c;
    border-radius: 12px;
    padding: 12px 16px;
    margin: 4px 0;
    cursor: pointer;
    transition: all 0.2s ease;
}
.starter-card:hover {
    border-color: #6c6c9c;
    transform: translateY(-1px);
}
.starter-label {
    font-size: 0.8em;
    opacity: 0.7;
    margin-bottom: 2px;
}
.starter-text {
    font-size: 0.95em;
}

/* Hide the iframe border for the custom input component */
iframe[title="streamlit_app.html"] {
    border: none !important;
}
</style>
""", unsafe_allow_html=True)

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

# Pre-built conversation starters for quick start
CONVERSATION_STARTERS = [
    {"emoji": "😊", "label": "Ask Joy", "text": "@joy What's the most fun thing to do today?"},
    {"emoji": "😢", "label": "Talk to Sadness", "text": "@sadness What makes you feel better on a bad day?"},
    {"emoji": "😠", "label": "Vent with Anger", "text": "@anger What's the most unfair thing ever?"},
    {"emoji": "😨", "label": "Ask Fear", "text": "@fear What should I be careful about today?"},
    {"emoji": "🤢", "label": "Judge with Disgust", "text": "@disgust What's the worst fashion trend right now?"},
    {"emoji": "🎭", "label": "Ask Everyone", "text": "What do you all think about pineapple on pizza?"},
    {"emoji": "🌤️", "label": "Check Weather", "text": "@joy What's the weather like in New York?"},
    {"emoji": "💬", "label": "Start a Debate", "text": "Is it better to be too hot or too cold?"},
]


def render_colored_mention(text: str) -> str:
    """Replace @emotion tokens with colored HTML <span> tags."""
    result = text
    for emotion, config in EMOTION_FRIENDS.items():
        pattern = rf'@{emotion}\b'
        colored_span = (
            f'<span class="mention-tag" style="color:{config["color"]}; '
            f'background:{config["color"]}20;">'
            f'{config["emoji"]} @{emotion}</span>'
        )
        result = re.sub(pattern, colored_span, result, flags=re.IGNORECASE)
    return result


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


    if "send_message" not in st.session_state:
        st.session_state.send_message = None


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
    active_friends_list = [e for e, a in st.session_state.active_friends.items() if a]
    if active_friends_list:
        friend_display = " ".join([f"{EMOTION_FRIENDS[e]['emoji']}" for e in active_friends_list])
        st.caption(f"**Online:** {friend_display}")
        # Colored mention hints
        mention_parts = []
        for e in active_friends_list:
            c = EMOTION_FRIENDS[e]
            mention_parts.append(
                f'<span class="mention-tag" style="color:{c["color"]};'
                f'background:{c["color"]}20;">@{e}</span>'
            )
        st.markdown(f"Mention: {' '.join(mention_parts)}", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No friends online!")
    
    st.divider()
    
    # Chat display
    if not st.session_state.messages:
        st.info("👋 **Welcome!** Chat with your emotion friends! Click a starter or type below.")

        # ── Conversation Starter Buttons ──
        st.markdown("##### 💡 Quick Starters")
        # Display in rows of 2
        for i in range(0, len(CONVERSATION_STARTERS), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(CONVERSATION_STARTERS):
                    starter = CONVERSATION_STARTERS[idx]
                    with col:
                        if st.button(
                            f"{starter['emoji']} {starter['label']}",
                            key=f"starter_{idx}",
                            use_container_width=True,
                            help=starter["text"],
                        ):
                            st.session_state.send_message = starter["text"]
                            st.rerun()
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    display_text = render_colored_mention(msg["content"])
                    st.markdown(display_text, unsafe_allow_html=True)
            elif msg["role"] == "friend":
                emotion = msg.get("emotion", "joy")
                config = EMOTION_FRIENDS.get(emotion, EMOTION_FRIENDS["joy"])
                was_mentioned = msg.get("was_mentioned", False)
                
                with st.chat_message("assistant", avatar=config["emoji"]):
                    name_html = (
                        f'<span style="color:{config["color"]};font-weight:700;">'
                        f'{config["name"]}</span>'
                    )
                    if was_mentioned:
                        st.markdown(f"{name_html} 💬", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{name_html}", unsafe_allow_html=True)
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

    # ── Chat Input with @Mention Autocomplete ──
    active_friends = [e for e, a in st.session_state.active_friends.items() if a]

    # Inject JS that enhances the native st.chat_input with an @mention autocomplete
    _friends_js = []
    for key in active_friends:
        f = EMOTION_FRIENDS[key]
        _friends_js.append(
            f'{{"key":"{key}","name":"{f["name"]}",'
            f'"emoji":"{f["emoji"]}","color":"{f["color"]}"}}'
        )
    _friends_js_str = "[" + ",".join(_friends_js) + "]"

    import streamlit.components.v1 as components
    components.html(f"""
<script>
(function() {{
  const friends = {_friends_js_str};
  const pdoc = window.parent.document;
  let mentionStart = -1, selectedIdx = 0, filtered = [], textarea = null;

  // Remove any old dropdown from a previous Streamlit rerun
  const old = pdoc.getElementById('ac-mention-dropdown');
  if (old) old.remove();
  const oldStyle = pdoc.getElementById('ac-mention-style');
  if (oldStyle) oldStyle.remove();

  // Inject styles into the parent document
  const style = pdoc.createElement('style');
  style.id = 'ac-mention-style';
  style.textContent = `
    #ac-mention-dropdown {{
      display:none;
      position:absolute;
      min-width:220px;
      background:#1a1a2e;
      border:1px solid #555;
      border-radius:10px;
      padding:4px;
      box-shadow:0 8px 24px rgba(0,0,0,.5);
      z-index:999999;
      max-height:260px;
      overflow-y:auto;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    }}
    #ac-mention-dropdown .ac-item {{
      display:flex;align-items:center;gap:8px;
      padding:8px 12px;border-radius:8px;cursor:pointer;
      transition:background .12s;
      color:#fafafa;
    }}
    #ac-mention-dropdown .ac-item:hover,
    #ac-mention-dropdown .ac-item.selected {{
      background:#2d2d44;
    }}
    #ac-mention-dropdown .ac-name {{ font-weight:600; }}
    #ac-mention-dropdown .ac-key {{ opacity:.5;font-size:.85em;margin-left:auto; }}
  `;
  pdoc.head.appendChild(style);

  // Create the dropdown in the parent document
  const dd = pdoc.createElement('div');
  dd.id = 'ac-mention-dropdown';
  pdoc.body.appendChild(dd);

  function findTextarea() {{
    return pdoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
  }}

  function positionDD() {{
    if (!textarea) return;
    const rect = textarea.getBoundingClientRect();
    dd.style.left = rect.left + 'px';
    dd.style.width = rect.width + 'px';
    dd.style.top = (rect.top - dd.offsetHeight - 4) + 'px';
  }}

  function showDD(items) {{
    selectedIdx = 0;
    filtered = items;
    dd.innerHTML = items.map((f,i) =>
      '<div class="ac-item' + (i===0?' selected':'') + '" data-idx="'+i+'">'
      + '<span style="font-size:1.2em;">'+f.emoji+'</span>'
      + '<span class="ac-name" style="color:'+f.color+';">'+f.name+'</span>'
      + '<span class="ac-key">@'+f.key+'</span>'
      + '</div>'
    ).join('');
    dd.style.display = 'block';
    positionDD();
    addListeners();
  }}

  function hideDD() {{
    dd.style.display = 'none';
    mentionStart = -1; filtered = [];
  }}

  function insertMention(friend) {{
    if(!textarea) return;
    const val = textarea.value;
    const pos = textarea.selectionStart;
    const before = val.slice(0, mentionStart);
    const after = val.slice(pos);
    const newVal = before + '@' + friend.key + ' ' + after;
    // Use native setter so React picks up the change
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.parent.HTMLTextAreaElement.prototype, 'value'
    ).set;
    nativeSetter.call(textarea, newVal);
    textarea.dispatchEvent(new window.parent.Event('input', {{bubbles:true}}));
    const newPos = mentionStart + friend.key.length + 2;
    textarea.setSelectionRange(newPos, newPos);
    hideDD();
    textarea.focus();
  }}

  function highlight(idx) {{
    dd.querySelectorAll('.ac-item').forEach((el,i) => {{
      el.classList.toggle('selected', i===idx);
    }});
    selectedIdx = idx;
  }}

  function addListeners() {{
    dd.querySelectorAll('.ac-item').forEach(el => {{
      el.addEventListener('mouseenter', () => highlight(parseInt(el.dataset.idx)));
      el.addEventListener('mousedown', (e) => {{
        e.preventDefault(); e.stopPropagation();
        insertMention(filtered[parseInt(el.dataset.idx)]);
      }});
    }});
  }}

  function onInput() {{
    const val = textarea.value;
    const pos = textarea.selectionStart;
    if(pos > 0 && val[pos-1] === '@' && (pos===1 || val[pos-2]===' ' || val[pos-2]==='\\n')) {{
      mentionStart = pos - 1;
    }}
    if(mentionStart >= 0) {{
      if(pos <= mentionStart) {{ hideDD(); return; }}
      const partial = val.slice(mentionStart+1, pos).toLowerCase();
      if(partial.includes(' ')) {{ hideDD(); return; }}
      const matches = partial.length === 0
        ? friends
        : friends.filter(f => f.key.startsWith(partial) || f.name.toLowerCase().startsWith(partial));
      if(matches.length === 0) {{ hideDD(); return; }}
      showDD(matches);
    }}
  }}

  function onKeyDown(e) {{
    if(dd.style.display === 'none' || filtered.length === 0) return;
    if(e.key === 'ArrowDown') {{
      e.preventDefault(); e.stopPropagation();
      highlight((selectedIdx+1)%filtered.length);
    }} else if(e.key === 'ArrowUp') {{
      e.preventDefault(); e.stopPropagation();
      highlight((selectedIdx-1+filtered.length)%filtered.length);
    }} else if(e.key === 'Tab' || (e.key === 'Enter' && dd.style.display !== 'none')) {{
      e.preventDefault(); e.stopPropagation();
      insertMention(filtered[selectedIdx]);
    }} else if(e.key === 'Escape') {{
      e.preventDefault();
      hideDD();
    }}
  }}

  // Poll for the textarea (it renders after this script)
  const poll = setInterval(() => {{
    textarea = findTextarea();
    if(textarea) {{
      clearInterval(poll);
      textarea.addEventListener('input', onInput);
      textarea.addEventListener('keydown', onKeyDown, true);
      pdoc.addEventListener('click', (e) => {{
        if(!textarea.contains(e.target) && !dd.contains(e.target)) hideDD();
      }});
    }}
  }}, 200);
}})();
</script>
""", height=0, scrolling=False)

    # Check for message from conversation starter buttons
    if st.session_state.send_message:
        user_input = st.session_state.send_message
        st.session_state.send_message = None
    else:
        user_input = st.chat_input(
            "Type a message… (type @ to mention a friend)",
        )

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
