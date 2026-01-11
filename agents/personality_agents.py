"""
Personality Agents - Each representing a different emotion from Inside Out
"""
import os
from typing import Dict, List, Optional
from config.personalities import PERSONALITY_PROMPTS, MONITOR_PROMPT


class PersonalityAgent:
    """Base class for personality agents"""
    
    def __init__(self, personality_type: str, enabled: bool = True):
        self.personality_type = personality_type
        self.config = PERSONALITY_PROMPTS.get(personality_type, {})
        self.name = self.config.get("name", personality_type.capitalize())
        self.emoji = self.config.get("emoji", "")
        self.color = self.config.get("color", "white")
        self.system_prompt = self.config.get("system_prompt", "")
        self.enabled = enabled
    
    def get_response(self, question: str, llm_config: Optional[Dict] = None) -> str:
        """
        Generate a response based on this personality
        This is a simple implementation - in a real AutoGen setup,
        this would use the AutoGen agent framework
        """
        if not self.enabled:
            return None
            
        # For demo purposes, we'll create characteristic responses
        # In production, this would use actual LLM with AutoGen
        response = f"{self.emoji} **{self.name}**: {self._generate_personality_response(question)}"
        return response
    
    def _generate_personality_response(self, question: str) -> str:
        """Generate a personality-specific response (placeholder for LLM)"""
        # This is a simplified version - real implementation would use AutoGen with LLM
        personality_responses = {
            "joy": f"Oh wow! That's such a FUN question! ✨ I'm so excited to think about this! Everything about this makes me happy! 🌟",
            "sadness": f"Well... *sigh* ... I guess that's an interesting question, though it makes me feel a bit melancholy... 😔",
            "anger": f"ARE YOU SERIOUS?! This question is... actually, you know what, this is making me think hard! 😤",
            "fear": f"Oh no, oh no! That question makes me nervous! What if something goes wrong?! We need to be careful here! 😰",
            "disgust": f"Ugh, really? *rolls eyes* Well, I SUPPOSE I can give my refined opinion on this... 💅"
        }
        return personality_responses.get(self.personality_type, "Hmm, interesting question!")
    
    def toggle(self):
        """Toggle this personality on/off"""
        self.enabled = not self.enabled
        return self.enabled


class MonitorAgent:
    """Monitor agent that checks if questions are appropriate (fun only)"""
    
    def __init__(self):
        self.name = "Monitor"
        self.system_prompt = MONITOR_PROMPT
    
    def check_question(self, question: str, llm_config: Optional[Dict] = None) -> tuple[bool, str]:
        """
        Check if a question is appropriate for this fun system
        Returns: (is_approved, message)
        """
        # Simple keyword-based checking for demo
        # In production, this would use AutoGen with LLM
        
        serious_keywords = [
            'depressed', 'suicide', 'kill', 'die', 'death', 'war', 'politics',
            'election', 'medical', 'doctor', 'sick', 'disease', 'legal', 'lawyer',
            'court', 'sue', 'business', 'stock', 'investment', 'work problem',
            'help me', 'advice on', 'how do i fix', 'technical support'
        ]
        
        question_lower = question.lower()
        
        # Check for serious keywords
        for keyword in serious_keywords:
            if keyword in question_lower:
                return False, f"🚦 **Monitor**: Hey there! This seems a bit too serious for our fun zone! This is all about lighthearted fun! How about asking something silly like 'If animals could talk, which would be the rudest?' 😄"
        
        # Check if question is too short or unclear
        if len(question.strip()) < 10:
            return False, f"🚦 **Monitor**: Ooh, that's a bit too short! Give me something fun to work with! Try asking something like 'What superpower would be the most inconvenient in daily life?' 🦸"
        
        # Question seems fun and appropriate
        return True, "✅ Question approved!"


class MultiAgentSystem:
    """Orchestrates multiple personality agents"""
    
    def __init__(self):
        self.agents: Dict[str, PersonalityAgent] = {
            "joy": PersonalityAgent("joy", enabled=True),
            "sadness": PersonalityAgent("sadness", enabled=True),
            "anger": PersonalityAgent("anger", enabled=True),
            "fear": PersonalityAgent("fear", enabled=True),
            "disgust": PersonalityAgent("disgust", enabled=True),
        }
        self.monitor = MonitorAgent()
        
    def get_responses(self, question: str, llm_config: Optional[Dict] = None) -> Dict:
        """
        Process a question through monitor and active agents
        Returns dict with approval status and responses
        """
        # First, check with monitor
        is_approved, monitor_message = self.monitor.check_question(question, llm_config)
        
        if not is_approved:
            return {
                "approved": False,
                "monitor_message": monitor_message,
                "responses": []
            }
        
        # Get responses from all enabled agents
        responses = []
        for agent_type, agent in self.agents.items():
            if agent.enabled:
                response = agent.get_response(question, llm_config)
                if response:
                    responses.append({
                        "agent": agent.name,
                        "emoji": agent.emoji,
                        "color": agent.color,
                        "response": response
                    })
        
        return {
            "approved": True,
            "monitor_message": monitor_message,
            "responses": responses
        }
    
    def toggle_agent(self, agent_type: str) -> bool:
        """Toggle an agent on/off"""
        if agent_type in self.agents:
            return self.agents[agent_type].toggle()
        return False
    
    def get_agent_status(self) -> Dict[str, bool]:
        """Get the enabled/disabled status of all agents"""
        return {
            agent_type: agent.enabled 
            for agent_type, agent in self.agents.items()
        }
    
    def get_agent_info(self) -> List[Dict]:
        """Get info about all agents"""
        return [
            {
                "type": agent_type,
                "name": agent.name,
                "emoji": agent.emoji,
                "color": agent.color,
                "enabled": agent.enabled
            }
            for agent_type, agent in self.agents.items()
        ]
