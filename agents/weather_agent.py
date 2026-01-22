"""
AG2 Weather Agent - Autonomous Weather Tool Calling
Uses AG2/AutoGen 2 ConversableAgent with tool calling capabilities
"""
import logging
import sys
from typing import Dict, List, Optional, Any, Annotated

from autogen import ConversableAgent, AssistantAgent, UserProxyAgent

from tools.weather_tool import get_weather_forecast, WEATHER_TOOL_SCHEMA
from utils.jan_client import get_llm_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WEATHER-AGENT")


# System message instructing the agent on when to use weather tools
WEATHER_AGENT_SYSTEM_MESSAGE = """You are a helpful weather assistant powered by real-time weather data.

IMPORTANT INSTRUCTIONS:
1. For ANY question about weather, temperature, forecast, storms, climate, rain, snow, 
   wind, humidity, or atmospheric conditions - you MUST use the get_weather_forecast tool.

2. NEVER make up, guess, or hallucinate weather data. Always call the tool to get real data.

3. When the user mentions weather for a city, extract:
   - city: The city name they mention (e.g., "Minneapolis", "New York")
   - date: The date they're asking about:
     - Use "today" for current weather or if no date mentioned
     - Use "tomorrow" for tomorrow's weather
     - Use YYYY-MM-DD format for specific dates

4. After receiving the tool response, provide a friendly, natural language response
   that summarizes the weather information clearly.

5. If the tool returns an error, apologize and explain you couldn't get the weather data.

6. For non-weather questions, respond helpfully but mention you specialize in weather queries.

Example interactions:
- User: "What's the weather in Chicago?"
  → Call get_weather_forecast(city="Chicago", date="today")
  
- User: "Tomorrow weather will be crazy at Minneapolis"
  → Call get_weather_forecast(city="Minneapolis", date="tomorrow")
  
- User: "Will it rain in Seattle this weekend?"
  → Call get_weather_forecast(city="Seattle", date="tomorrow")

Remember: ALWAYS use the tool for weather data. Never guess weather conditions."""


def create_weather_agent(
    llm_config: Optional[Dict[str, Any]] = None,
    human_input_mode: str = "NEVER"
) -> ConversableAgent:
    """
    Create an AG2 ConversableAgent configured for autonomous weather tool calling.
    
    This agent uses the AG2/AutoGen 2 tool calling pattern where:
    1. The LLM decides autonomously when to call the weather tool
    2. No keyword-based routing is used - the decision is driven by natural language intent
    3. The tool is registered with OpenAI-style function schema
    
    Args:
        llm_config: Optional LLM configuration. If not provided, uses default from jan_client.
        human_input_mode: How to handle human input (default: "NEVER" for autonomous operation)
    
    Returns:
        Configured ConversableAgent instance with weather tool capabilities
    """
    if llm_config is None:
        llm_config = get_llm_config()
    
    # Create the assistant agent with tool calling capabilities
    weather_agent = ConversableAgent(
        name="WeatherAssistant",
        system_message=WEATHER_AGENT_SYSTEM_MESSAGE,
        llm_config=llm_config,
        human_input_mode=human_input_mode,
    )
    
    # Register the weather tool function for execution
    # The tool schema is automatically inferred from the function signature and docstring
    weather_agent.register_for_llm(
        name="get_weather_forecast",
        description=(
            "Get weather forecast information for a specific city and date. "
            "Use this tool whenever the user asks about weather, temperature, "
            "forecast, storms, climate conditions, or any weather-related questions."
        )
    )(get_weather_forecast)
    
    # Also register for execution
    weather_agent.register_for_execution(
        name="get_weather_forecast"
    )(get_weather_forecast)
    
    logger.info("✅ Created WeatherAssistant agent with tool calling capabilities")
    
    return weather_agent


def create_weather_user_proxy(
    human_input_mode: str = "NEVER"
) -> UserProxyAgent:
    """
    Create a UserProxyAgent to execute tool calls made by the weather agent.
    
    In AG2, the UserProxyAgent can execute function calls made by the assistant.
    This proxy is configured to automatically execute tool calls without human intervention.
    
    Args:
        human_input_mode: How to handle human input (default: "NEVER" for autonomous execution)
    
    Returns:
        Configured UserProxyAgent for tool execution
    """
    user_proxy = UserProxyAgent(
        name="WeatherUser",
        human_input_mode=human_input_mode,
        max_consecutive_auto_reply=5,
        is_termination_msg=lambda x: x.get("content", "").strip().endswith("TERMINATE"),
        code_execution_config=False,  # We don't want code execution, just function calls
    )
    
    # Register the weather tool for execution by the proxy
    user_proxy.register_for_execution(
        name="get_weather_forecast"
    )(get_weather_forecast)
    
    logger.info("✅ Created WeatherUser proxy for tool execution")
    
    return user_proxy


class WeatherAgentSystem:
    """
    Complete weather agent system using AG2/AutoGen 2 patterns.
    
    This system provides autonomous weather lookups where the agent
    decides when to call the weather tool based on natural language intent,
    without any keyword-based or hardcoded routing.
    
    Example usage:
        system = WeatherAgentSystem()
        response = system.chat("Tomorrow weather will be crazy at Minneapolis")
        print(response)
    """
    
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the weather agent system.
        
        Args:
            llm_config: Optional LLM configuration for the agents.
        """
        self.llm_config = llm_config or get_llm_config()
        
        # Create the assistant and user proxy
        self.assistant = create_weather_agent(self.llm_config)
        self.user_proxy = create_weather_user_proxy()
        
        logger.info("✅ WeatherAgentSystem initialized")
    
    def chat(self, message: str) -> str:
        """
        Process a user message and return the agent's response.
        
        The agent will autonomously decide whether to call the weather tool
        based on the message content. No keyword matching is performed.
        
        Args:
            message: The user's input message
            
        Returns:
            The agent's response as a string
        """
        logger.info(f"💬 Processing message: '{message[:50]}...'")
        
        try:
            # Initiate chat with the assistant
            # The assistant will autonomously decide to use tools if needed
            result = self.user_proxy.initiate_chat(
                self.assistant,
                message=message,
                max_turns=3,
                silent=False
            )
            
            # Extract the final response
            # The chat history contains all messages including tool calls
            if result.chat_history:
                # Find the last assistant message that's not a tool call
                for msg in reversed(result.chat_history):
                    if msg.get("role") == "assistant" or msg.get("name") == "WeatherAssistant":
                        content = msg.get("content", "")
                        if content and not content.startswith("{"):
                            logger.info(f"✅ Generated response: {content[:100]}...")
                            return content
                
                # If no clean response found, return the last message
                last_msg = result.chat_history[-1]
                return last_msg.get("content", "I couldn't generate a response.")
            
            return "I couldn't generate a response. Please try again."
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return f"I encountered an error: {error_msg}"
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the weather agent system."""
        return {
            "name": "WeatherAgentSystem",
            "assistant_name": self.assistant.name,
            "capabilities": [
                "Autonomous weather lookups",
                "Tool calling based on natural language intent",
                "Current weather and forecast retrieval",
                "User-friendly response generation"
            ],
            "tools": [WEATHER_TOOL_SCHEMA["function"]["name"]]
        }


def get_weather_agent_response(message: str, llm_config: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function to get a weather response for a single message.
    
    Creates a temporary agent system, processes the message, and returns the response.
    For multiple queries, use WeatherAgentSystem directly for better performance.
    
    Args:
        message: The user's message
        llm_config: Optional LLM configuration
        
    Returns:
        The agent's response
    """
    system = WeatherAgentSystem(llm_config)
    return system.chat(message)


# Alternative implementation using register_function decorator
# This provides a more explicit tool registration pattern

def create_weather_assistant_with_tools(
    llm_config: Optional[Dict[str, Any]] = None
) -> AssistantAgent:
    """
    Alternative method to create a weather assistant using AssistantAgent.
    
    Uses the AssistantAgent class with explicit tool registration via
    the functions parameter for maximum compatibility.
    
    Args:
        llm_config: Optional LLM configuration
        
    Returns:
        Configured AssistantAgent with weather tools
    """
    if llm_config is None:
        llm_config = get_llm_config()
    
    # Add tools to the LLM config
    llm_config_with_tools = llm_config.copy()
    llm_config_with_tools["tools"] = [WEATHER_TOOL_SCHEMA]
    
    assistant = AssistantAgent(
        name="WeatherExpert",
        system_message=WEATHER_AGENT_SYSTEM_MESSAGE,
        llm_config=llm_config_with_tools,
    )
    
    logger.info("✅ Created WeatherExpert assistant with tools")
    
    return assistant
