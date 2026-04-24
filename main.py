"""
Main entry point for Inside Out Multi-Agent System
"""
import sys
import os
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import MultiAgentSystem
from utils.llm_client import LLMClient, LLMClientError

# Configure logging so the user sees timestamps and levels in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("INSIDE-OUT")


def check_llm_connection() -> bool:
    """
    Attempt to reach the LLM backend server.
    Logs a clear warning when unavailable so the user knows
    all responses will be local / static fallbacks.

    Returns:
        True if LLM backend is reachable, False otherwise.
    """
    try:
        client = LLMClient()
        connected = client.test_connection()
        if connected:
            logger.info(
                f"✅ LLM backend connected — model: {client.model_name}  url: {client.base_url}"
            )
        else:
            logger.warning(
                "⚠️  LLM backend server is NOT reachable at %s. "
                "All responses will use LOCAL static fallbacks (no LLM).",
                client.base_url,
            )
        return connected
    except LLMClientError as exc:
        logger.warning(
            "⚠️  LLM backend client error: %s. "
            "All responses will use LOCAL static fallbacks (no LLM).",
            exc,
        )
        return False
    except Exception as exc:
        logger.warning(
            "⚠️  Unexpected error checking LLM backend: %s. "
            "All responses will use LOCAL static fallbacks (no LLM).",
            exc,
        )
        return False


def print_banner():
    """Print a fun banner"""
    print("\n" + "="*60)
    print("🎭  INSIDE OUT - MULTI-AGENT PERSONALITY CHAT  🎭")
    print("="*60)
    print("\nAsk fun questions and see how different emotions respond!")
    print("\nActive Personalities:")
    print("  😄 Joy - Optimistic & Excited")
    print("  😢 Sadness - Melancholic & Thoughtful")
    print("  😡 Anger - Passionate & Intense")
    print("  😰 Fear - Cautious & Worried")
    print("  🤢 Disgust - Sassy & Particular")
    print("\n" + "="*60)
    print("Commands:")
    print("  'quit' or 'exit' - Exit the program")
    print("  'toggle <personality>' - Toggle a personality on/off")
    print("  'status' - Show which personalities are active")
    print("="*60 + "\n")


def print_status(agent_system):
    """Print the status of all agents"""
    print("\n📊 Personality Status:")
    for agent_type, agent in agent_system.agents.items():
        status = "✅ ON" if agent.enabled else "❌ OFF"
        print(f"  {agent.emoji} {agent.name}: {status}")
    print()


def main():
    """Main CLI interface"""
    print_banner()

    # ── Connection check ────────────────────────────────────────────────────
    llm_online = check_llm_connection()
    if not llm_online:
        print(
            "\n⚠️  LLM backend is OFFLINE — responses are LOCAL static fallbacks.\n"
            "   Start the LLM backend server and restart this script for LLM replies.\n"
        )
    # ────────────────────────────────────────────────────────────────────────

    agent_system = MultiAgentSystem()
    
    while True:
        try:
            question = input("\n💭 Ask your fun question (or type a command): ").strip()
            
            if not question:
                continue

            # Handle commands
            if question.lower() in ['quit', 'exit']:
                print("\n👋 Thanks for chatting with the Inside Out crew! Goodbye! 🎬\n")
                break
            
            if question.lower() == 'status':
                print_status(agent_system)
                continue
            
            if question.lower().startswith('toggle '):
                personality = question[7:].strip().lower()
                if personality in agent_system.agents:
                    new_status = agent_system.toggle_agent(personality)
                    status_text = "ON ✅" if new_status else "OFF ❌"
                    agent_name = agent_system.agents[personality].name
                    print(f"\n🔄 {agent_name} is now {status_text}")
                else:
                    print(f"\n❌ Unknown personality: {personality}")
                    print("Available: joy, sadness, anger, fear, disgust")
                continue
            
            # Process the question
            result = agent_system.get_responses(question)
            
            if not result["approved"]:
                print(f"\n{result['monitor_message']}")
                continue
            
            if not result["responses"]:
                print("\n⚠️  No personalities are active! Use 'toggle <personality>' to enable some.")
                continue
            
            # Display responses
            print(f"\n" + "─"*60)
            print(f"Question: {question}")
            print("─"*60)
            
            for response in result["responses"]:
                print(f"\n{response['response']}")
            
            print("\n" + "─"*60)
            
        except KeyboardInterrupt:
            print("\n\n👋 Thanks for chatting with the Inside Out crew! Goodbye! 🎬\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


if __name__ == "__main__":
    main()
