"""
Unified config/secrets loader.

Tries st.secrets first (Streamlit context), then falls back to os.getenv
(CLI / test context). This lets both the web UI and the CLI share the same
client code without any changes to callers.
"""
import os


def get_secret(section: str, key: str, env_var: str, default=None):
    """
    Read a configuration value from Streamlit secrets or environment variables.

    Priority:
      1. st.secrets[section][key]  — available when running via ``streamlit run``
      2. os.getenv(env_var)        — fallback for CLI / test context
      3. default                   — hard-coded last resort
    """
    try:
        import streamlit as st
        return st.secrets[section][key]
    except Exception:
        return os.getenv(env_var, default)
