"""
Personality Agents - Each representing a different emotion from Inside Out
Includes Decision Agent for intelligent response routing
"""
import logging
import sys
import json
import re
from typing import Dict, List, Optional
from config.personalities import PERSONALITY_PROMPTS, MONITOR_PROMPT

# Configure logging to show in terminal with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("INSIDE-OUT")

# Import Jan client for LLM integration
try:
    from utils.jan_client import JanClient, JanClientError
    JAN_AVAILABLE = True
    logger.info("✅ Jan AI client module loaded successfully")
except ImportError as e:
    JAN_AVAILABLE = False
    logger.warning(f"❌ Jan client not available: {e} - using static responses")

# Import weather tool for weather lookups
try:
    from tools.weather_tool import (
        get_weather,
        is_weather_query,
        extract_location_from_message
    )
    WEATHER_AVAILABLE = True
    logger.info("✅ Weather tool loaded successfully")
except ImportError as e:
    WEATHER_AVAILABLE = False
    logger.warning(f"⚠️ Weather tool not available: {e}")


# Decision Agent prompt for analyzing who should respond
DECISION_AGENT_PROMPT = """You are the Decision Agent for an Inside Out emotion chat.

Your job is to analyze messages and decide which emotions should respond.

Available emotions:
- joy: Responds to positive, fun, happy, exciting topics AND neutral informational queries (like weather, facts)
- sadness: Responds to melancholic, missing, emotional depth topics
- anger: Responds to unfair, frustrating, injustice topics
- fear: Responds to risky, scary, dangerous, worrying topics
- disgust: Responds to gross, tacky, cringe, fashion/taste topics

Rules:
1. NOT every emotion needs to respond to every message
2. Pick only 1-3 emotions that are MOST relevant
3. For neutral questions (like "favorite food" or "what's the weather"), Joy should respond
4. For weather queries ("what's the weather in...", "how hot is it"), Joy should respond
5. For negative topics, relevant emotions respond
6. Return a JSON object with emotions as keys and boolean values

Example:
User: "What's your favorite pizza?"
Response: {"joy": true, "sadness": false, "anger": false, "fear": false, "disgust": false}

User: "What's the weather in New York?"
Response: {"joy": true, "sadness": false, "anger": false, "fear": false, "disgust": false}

User: "I'm worried about climate change"
Response: {"joy": false, "sadness": true, "anger": true, "fear": true, "disgust": false}

User: "This trend is so cringe"
Response: {"joy": false, "sadness": false, "anger": false, "fear": false, "disgust": true}

ONLY respond with the JSON object, nothing else."""


class PersonalityAgent:
    """Base class for personality agents"""
    
    # Shared Jan client instance
    _jan_client = None
    _connection_tested = False
    
    @classmethod
    def get_jan_client(cls):
        """Get or create shared Jan client (singleton)"""
        if cls._jan_client is not None:
            return cls._jan_client

        if not JAN_AVAILABLE:
            logger.info("📝 Jan AI module not available — will use LOCAL static responses")
            return None

        try:
            logger.info("🔌 Initializing Jan AI client...")
            cls._jan_client = JanClient()
            logger.info(
                f"🔌 Jan AI client created — model: {cls._jan_client.model_name}, "
                f"url: {cls._jan_client.base_url}"
            )

            # One-time connection test (informational only — do NOT null the client)
            if not cls._connection_tested:
                cls._connection_tested = True
                logger.info(f"🔗 Testing connection to Jan AI at {cls._jan_client.base_url}...")
                if cls._jan_client.test_connection():
                    logger.info(f"✅ Connected to Jan AI! Model: {cls._jan_client.model_name}")
                else:
                    logger.warning(
                        "⚠️ Jan AI connection test failed — server may not be running. "
                        "Chat requests will still be attempted (they may fail)."
                    )

        except Exception as e:
            logger.error(f"❌ Failed to initialize Jan client: {e}")
            cls._jan_client = None

        return cls._jan_client
    
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
        Generate a response based on this personality using Jan AI.
        Falls back to static response if Jan AI is unavailable.
        Includes weather data when user asks about weather.

        Flow:
          1. Strip @mentions from the question
          2. Detect weather query → fetch weather data via weather_tool
          3. Build prompt with weather context (if any)
          4. Send prompt to Jan AI → return LLM response
          5. On failure → return LOCAL static fallback
        """
        if not self.enabled:
            return None

        tag = f"[{self.name}]"

        # ── Step 1: Strip @mention tokens ────────────────────────────────────
        clean_question = re.sub(r'@\w+', '', question).strip()
        logger.info(f"── {tag} Step 1 — Clean question: \"{clean_question}\"")

        # ── Step 2: Weather detection ────────────────────────────────────────
        weather_context = ""
        if WEATHER_AVAILABLE and is_weather_query(clean_question):
            logger.info(f"🌤️ {tag} Step 2 — Weather keywords detected in message")
            location = extract_location_from_message(clean_question)
            if location:
                logger.info(f"🌤️ {tag} Step 2a — Extracted location: \"{location}\"")
                logger.info(f"🌤️ {tag} Step 2b — Calling weather API for \"{location}\"...")
                weather_data = get_weather(location)
                weather_context = f"\n\nCurrent weather information:\n{weather_data}"
                logger.info(f"🌤️ {tag} Step 2c — Weather data received:\n{weather_data}")
            else:
                logger.info(f"🌤️ {tag} Step 2a — No location could be extracted from message")
        else:
            logger.info(f"── {tag} Step 2 — Not a weather query (skipping weather tool)")

        # ── Step 3: Build prompt ─────────────────────────────────────────────
        user_message = f'User says: "{clean_question}"'
        if weather_context:
            user_message += weather_context
            user_message += (
                "\n\nRULES FOR YOUR RESPONSE:"
                "\n1. You MUST state the exact temperature number from the data above (e.g. '33.1°F')."
                "\n2. You MUST state the weather condition from the data above (e.g. 'Overcast')."
                "\n3. You MAY also mention feels-like, humidity, or wind from the data."
                "\n4. Say it all in your personality style — be yourself!"
                "\n5. Keep it to 2-3 sentences."
            )
        else:
            user_message += (
                "\n\nRespond in 1-2 SHORT sentences. "
                "Do NOT repeat their words. React with YOUR emotion."
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Give weather responses more token room so the model includes actual numbers
        weather_max_tokens = 250 if weather_context else None

        logger.info(f"── {tag} Step 3 — Prompt built ({len(user_message)} chars, weather={'YES' if weather_context else 'NO'})")
        logger.debug(f"── {tag} Full prompt:\n{user_message}")

        # ── Step 4: Send to Jan AI ───────────────────────────────────────────
        jan_client = self.get_jan_client()
        if jan_client:
            try:
                logger.info(
                    f"🤖 {tag} Step 4 — Sending request to Jan AI "
                    f"(model={jan_client.model_name}, url={jan_client.base_url})..."
                )
                llm_response = jan_client.chat(messages, max_tokens=weather_max_tokens)
                logger.info(f"✅ {tag} Step 4 — LLM response received: \"{llm_response[:120]}...\"")

                response = f"{self.emoji} **{self.name}**: {llm_response}"
                return response

            except Exception as e:
                logger.warning(
                    f"⚠️ {tag} Step 4 — Jan AI chat FAILED: {type(e).__name__}: {e}"
                )
                logger.warning(
                    f"📝 {tag} Step 5 — Falling back to LOCAL static response"
                )
        else:
            logger.warning(
                f"📝 {tag} Step 4 — No Jan AI client available — "
                f"using LOCAL static response"
            )

        # ── Step 5: Fallback to static response ─────────────────────────────
        fallback = self._generate_personality_response(clean_question)
        if weather_context:
            fallback = self._generate_weather_response(weather_context) or fallback
        logger.info(f"📝 {tag} Step 5 — LOCAL fallback response: \"{fallback[:80]}...\"")
        response = f"{self.emoji} **{self.name}**: {fallback}"
        return response
    
    def _generate_personality_response(self, question: str) -> str:
        """Generate a personality-specific fallback response"""
        personality_responses = {
            "joy": f"Ooh, I love thinking about this! So exciting! ✨",
            "sadness": f"*sigh* I guess that's something to think about... 😔",
            "anger": f"Hmm, that's making me think! 😤",
            "fear": f"Oh, that makes me a bit nervous to consider! 😰",
            "disgust": f"Well, I have opinions about that... 💅"
        }
        return personality_responses.get(self.personality_type, "Hmm, interesting!")
    
    def _generate_weather_response(self, weather_info: str) -> Optional[str]:
        """Generate a personality-specific response about weather"""
        weather_responses = {
            "joy": f"Oh wow, let me tell you about the weather! 🌈 {weather_info.split(chr(10))[0] if weather_info else ''} How exciting!",
            "sadness": f"*looks out window* The weather... it makes me feel things. {weather_info.split(chr(10))[0] if weather_info else ''} 😢",
            "anger": f"You want to know about the weather?! Fine! {weather_info.split(chr(10))[0] if weather_info else ''} 😤",
            "fear": f"Oh no, the weather! What if it changes?! {weather_info.split(chr(10))[0] if weather_info else ''} Be careful out there! 😰",
            "disgust": f"Ugh, weather talk? Really? Fine. {weather_info.split(chr(10))[0] if weather_info else ''} 💅"
        }
        return weather_responses.get(self.personality_type)
    
    def toggle(self):
        """Toggle this personality on/off"""
        self.enabled = not self.enabled
        return self.enabled


class DecisionAgent:
    """
    Decision Agent that analyzes messages and decides which personalities should respond.
    Acts as a conductor/orchestrator for the emotion agents.
    """
    
    def __init__(self):
        self.name = "Decision"
        self.system_prompt = DECISION_AGENT_PROMPT
    
    def get_jan_client(self):
        """Get shared Jan client"""
        return PersonalityAgent.get_jan_client()
    
    def analyze_message(self, message: str) -> Dict[str, bool]:
        """
        Analyze a message and decide which emotions should respond.
        Returns dict of emotion -> should_respond
        """
        logger.info(f"🧠 [Decision Agent] Analyzing: '{message[:50]}...'")
        
        jan_client = self.get_jan_client()
        
        if jan_client:
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"User message: \"{message}\"\n\nWhich emotions should respond? Return ONLY JSON."}
                ]
                
                response = jan_client.chat(messages, max_tokens=100)
                logger.info(f"🧠 [Decision Agent] Raw response: {response}")
                
                # Parse JSON response
                try:
                    # Clean up response - extract JSON
                    response = response.strip()
                    if response.startswith("```"):
                        response = response.split("```")[1]
                        if response.startswith("json"):
                            response = response[4:]
                    
                    decisions = json.loads(response)
                    logger.info(f"🧠 [Decision Agent] Decisions: {decisions}")
                    return decisions
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ [Decision Agent] Failed to parse JSON: {e}")
                    return self._fallback_analysis(message)
                    
            except Exception as e:
                logger.warning(f"⚠️ [Decision Agent] Error: {e}")
                return self._fallback_analysis(message)
        
        return self._fallback_analysis(message)
    
    def _fallback_analysis(self, message: str) -> Dict[str, bool]:
        """Fallback keyword-based analysis when LLM is unavailable"""
        logger.info("📝 [Decision Agent] Using fallback keyword analysis")
        
        message_lower = message.lower()
        decisions = {
            "joy": False,
            "sadness": False,
            "anger": False,
            "fear": False,
            "disgust": False
        }
        
        # Joy keywords - positive/fun (includes weather - neutral questions go to Joy)
        joy_keywords = ["favorite", "best", "love", "fun", "happy", "excited", "great", "amazing", "pizza", "food", "like", "enjoy", "weather", "temperature", "forecast", "sunny", "rain"]
        
        # Sadness keywords
        sadness_keywords = ["sad", "miss", "lonely", "wish", "lost", "remember", "gone", "cry"]
        
        # Anger keywords
        anger_keywords = ["unfair", "hate", "angry", "frustrat", "stupid", "ridiculous", "worst", "terrible"]
        
        # Fear keywords
        fear_keywords = ["scary", "afraid", "worried", "dangerous", "risk", "nervous", "what if"]
        
        # Disgust keywords
        disgust_keywords = ["gross", "ew", "yuck", "cringe", "tacky", "ugly", "embarrassing", "fashion"]
        
        # Check each emotion
        for keyword in joy_keywords:
            if keyword in message_lower:
                decisions["joy"] = True
                break
        
        for keyword in sadness_keywords:
            if keyword in message_lower:
                decisions["sadness"] = True
                break
        
        for keyword in anger_keywords:
            if keyword in message_lower:
                decisions["anger"] = True
                break
        
        for keyword in fear_keywords:
            if keyword in message_lower:
                decisions["fear"] = True
                break
        
        for keyword in disgust_keywords:
            if keyword in message_lower:
                decisions["disgust"] = True
                break
        
        # Default: if nothing matched, just Joy responds to neutral questions
        if not any(decisions.values()):
            decisions["joy"] = True
        
        logger.info(f"📝 [Decision Agent] Fallback decisions: {decisions}")
        return decisions


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
                return False, f"🚦 **Monitor**: This seems too serious for our fun zone! Try something silly instead! 😄"
        
        # Check if question is too short
        if len(question.strip()) < 5:
            return False, f"🚦 **Monitor**: Give me something fun to work with! Try a fun question! 🦸"
        
        return True, "✅ Approved!"


class MultiAgentSystem:
    """Orchestrates multiple personality agents with Decision Agent"""
    
    def __init__(self):
        self.agents: Dict[str, PersonalityAgent] = {
            "joy": PersonalityAgent("joy", enabled=True),
            "sadness": PersonalityAgent("sadness", enabled=True),
            "anger": PersonalityAgent("anger", enabled=True),
            "fear": PersonalityAgent("fear", enabled=True),
            "disgust": PersonalityAgent("disgust", enabled=True),
        }
        self.monitor = MonitorAgent()
        self.decision_agent = DecisionAgent()
    
    def get_responses(self, question: str, mentioned: List[str] = None, llm_config: Optional[Dict] = None) -> Dict:
        """
        Process a question through monitor, decision agent, and relevant personality agents
        
        Args:
            question: The user's message
            mentioned: List of emotions that were @mentioned (bypass decision agent)
            llm_config: Optional LLM configuration
            
        Returns: dict with approval status and responses
        """
        # First, check with monitor
        is_approved, monitor_message = self.monitor.check_question(question, llm_config)
        
        if not is_approved:
            return {
                "approved": False,
                "monitor_message": monitor_message,
                "responses": [],
                "decisions": {}
            }
        
        # If there are @mentions, those emotions respond directly
        if mentioned and len(mentioned) > 0:
            logger.info(f"📌 Direct @mentions: {mentioned} - bypassing Decision Agent")
            decisions = {e: (e in mentioned) for e in self.agents.keys()}
        else:
            # Use Decision Agent to determine who should respond
            decisions = self.decision_agent.analyze_message(question)
        
        # Get responses from decided agents
        responses = []
        for agent_type, should_respond in decisions.items():
            agent = self.agents.get(agent_type)
            if agent and agent.enabled and should_respond:
                response = agent.get_response(question, llm_config)
                if response:
                    responses.append({
                        "agent": agent.name,
                        "emotion": agent_type,
                        "emoji": agent.emoji,
                        "color": agent.color,
                        "response": response
                    })
        
        return {
            "approved": True,
            "monitor_message": monitor_message,
            "responses": responses,
            "decisions": decisions
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
