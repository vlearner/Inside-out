"""
Agent configuration for the Inside Out Multi-Agent System.

Defines execution order for scratchpad (sequential) mode.
"""

# The order in which agents execute when scratchpad mode is enabled.
# Reflects the emotional arc from the film: Joy leads, followed by
# Sadness, Fear, Disgust, and Anger anchors the conversation.
SCRATCHPAD_AGENT_ORDER = ["joy", "sadness", "fear", "disgust", "anger"]
