"""
AG2 Configuration for GroupChat and GroupChatManager
Handles the orchestration of emotion agents
"""
import logging
from typing import Dict, List, Optional, Any
from autogen import GroupChat, GroupChatManager, ConversableAgent

from utils.jan_client import get_llm_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_group_chat(
    agents: List[ConversableAgent],
    max_round: int = 10,
    speaker_selection_method: str = "auto"
) -> GroupChat:
    """
    Create an AG2 GroupChat with the provided agents
    
    Args:
        agents: List of ConversableAgent instances (emotion agents)
        max_round: Maximum number of conversation rounds
        speaker_selection_method: How to select the next speaker
            - "auto": Let the manager decide based on context
            - "round_robin": Each agent speaks in turn
            - "random": Random speaker selection
            
    Returns:
        Configured GroupChat instance
    """
    group_chat = GroupChat(
        agents=agents,
        messages=[],
        max_round=max_round,
        speaker_selection_method=speaker_selection_method,
        allow_repeat_speaker=False
    )
    
    logger.info(f"Created GroupChat with {len(agents)} agents")
    return group_chat


def create_group_chat_manager(
    group_chat: GroupChat,
    llm_config: Optional[Dict[str, Any]] = None
) -> GroupChatManager:
    """
    Create a GroupChatManager to orchestrate the conversation
    
    Args:
        group_chat: The GroupChat instance to manage
        llm_config: LLM configuration for the manager
        
    Returns:
        Configured GroupChatManager instance
    """
    if llm_config is None:
        llm_config = get_llm_config()
    
    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
        system_message="""You are managing a group of emotion characters from Inside Out.
Your job is to select which emotions should respond based on the user's message.

Guidelines for speaker selection:
- If the user mentions worry, anxiety, or danger -> Fear should respond first
- If the user mentions something sad, loss, or difficulty -> Sadness should respond
- If the user mentions something unfair or frustrating -> Anger should respond
- If the user mentions something gross or cringe-worthy -> Disgust should respond
- If the user asks about fun, positive things -> Joy should respond first
- Allow 2-4 emotions to respond per message, not all 5 every time
- Let emotions react to each other naturally
- Keep the conversation flowing and natural"""
    )
    
    logger.info("Created GroupChatManager")
    return manager


def analyze_message_for_emotions(message: str) -> List[str]:
    """
    Analyze a user message to determine which emotions are most relevant
    
    Args:
        message: The user's input message
        
    Returns:
        List of emotion names in priority order
    """
    message_lower = message.lower()
    
    # Keywords associated with each emotion
    emotion_keywords = {
        "fear": ["worried", "worry", "scared", "afraid", "nervous", "anxious", 
                 "dangerous", "risky", "what if", "scary", "fear", "terrified",
                 "panic", "concern", "unsafe"],
        "sadness": ["sad", "depressing", "miss", "lost", "lonely", "cry", 
                    "upset", "disappointed", "melancholy", "blue", "down",
                    "sorry", "heartbreak", "grief"],
        "anger": ["angry", "mad", "unfair", "frustrated", "annoyed", "hate",
                  "ridiculous", "outrageous", "furious", "irritated", "wrong",
                  "stupid", "terrible", "awful"],
        "disgust": ["gross", "disgusting", "ew", "yuck", "cringe", "tacky",
                    "tasteless", "ugly", "nasty", "awful", "terrible",
                    "embarrassing", "lame"],
        "joy": ["happy", "excited", "fun", "love", "great", "amazing",
                "wonderful", "awesome", "best", "favorite", "yay", "hooray",
                "fantastic", "brilliant", "perfect"]
    }
    
    # Score each emotion based on keyword matches
    scores = {emotion: 0 for emotion in emotion_keywords}
    
    for emotion, keywords in emotion_keywords.items():
        for keyword in keywords:
            if keyword in message_lower:
                scores[emotion] += 1
    
    # Sort emotions by score (descending)
    sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return emotions with scores > 0, or default to Joy if no matches
    relevant = [e[0] for e in sorted_emotions if e[1] > 0]
    
    if not relevant:
        # Default: Joy leads, others can follow
        return ["joy", "fear", "sadness"]
    
    # Add some variety - include at least 2-3 emotions
    result = relevant[:3]
    if len(result) < 2:
        # Add complementary emotions
        all_emotions = ["joy", "sadness", "anger", "fear", "disgust"]
        for emotion in all_emotions:
            if emotion not in result:
                result.append(emotion)
                if len(result) >= 3:
                    break
    
    return result


def get_emotion_config() -> Dict[str, Dict[str, Any]]:
    """
    Get temperature and other config overrides for each emotion
    
    Returns:
        Dictionary mapping emotion names to their config overrides
    """
    return {
        "joy": {"temperature": 0.9},      # More variety
        "sadness": {"temperature": 0.7},  # More consistent
        "anger": {"temperature": 0.8},    # Balanced
        "fear": {"temperature": 0.75},    # Slightly cautious
        "disgust": {"temperature": 0.85}  # Sassy variety
    }

