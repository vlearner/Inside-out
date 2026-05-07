"""JavaScript injection helpers for browser-backed memory sync."""
from __future__ import annotations

import json
import streamlit as st


def _j(value):
    return json.dumps(value)


def sync_memory_with_browser(session_memory, agent_memory):
    st.markdown(
        f"""
        <script>
        (function() {{
          const SESSION_KEY = 'insideout_session_memory';
          const AGENT_KEY = 'insideout_agent_memory';
          const ACTIVE_KEY = 'insideout_browser_session_active';
          const incomingSession = {_j(session_memory)};
          const incomingAgent = {_j(agent_memory)};

          const wasActive = localStorage.getItem(ACTIVE_KEY);
          sessionStorage.setItem(ACTIVE_KEY, '1');
          if (!wasActive) {{
            localStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(AGENT_KEY);
          }}
          localStorage.setItem(ACTIVE_KEY, '1');

          localStorage.setItem(SESSION_KEY, JSON.stringify(incomingSession));
          localStorage.setItem(AGENT_KEY, JSON.stringify(incomingAgent));

          window.addEventListener('beforeunload', function() {{
            if (sessionStorage.length <= 1) {{
              localStorage.removeItem(ACTIVE_KEY);
            }}
          }});
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def inject_browser_memory_bootstrap():
    st.markdown(
        """
        <script>
        (function() {
          const SESSION_KEY = 'insideout_session_memory';
          const AGENT_KEY = 'insideout_agent_memory';
          const params = new URLSearchParams(window.location.search);
          const sm = localStorage.getItem(SESSION_KEY);
          const am = localStorage.getItem(AGENT_KEY);
          if (sm && !params.get('session_memory')) params.set('session_memory', sm);
          if (am && !params.get('agent_memory')) params.set('agent_memory', am);
          const newUrl = window.location.pathname + '?' + params.toString();
          if (newUrl !== window.location.pathname + window.location.search) {
            window.history.replaceState({}, '', newUrl);
            window.location.reload();
          }
          window.addEventListener('storage', function(event) {
            if (event.key === SESSION_KEY || event.key === AGENT_KEY) {
              window.location.reload();
            }
          });
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )
