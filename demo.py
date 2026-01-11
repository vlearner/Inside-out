"""
Example demonstrating the Inside Out Multi-Agent System
Run this to see how the personalities respond to different questions
"""
import sys
sys.path.insert(0, '/home/runner/work/Inside-out/Inside-out')

from agents import MultiAgentSystem


def print_divider():
    print("\n" + "="*70 + "\n")


def demo_question(agent_system, question, title):
    """Demo a single question"""
    print(f"### {title}")
    print(f"Question: \"{question}\"\n")
    
    result = agent_system.get_responses(question)
    
    if not result["approved"]:
        print(result["monitor_message"])
    else:
        for response in result["responses"]:
            print(response["response"])
            print()
    
    print_divider()


def main():
    print_divider()
    print("🎭 INSIDE OUT - MULTI-AGENT PERSONALITY DEMO 🎭")
    print_divider()
    
    # Initialize the system
    agent_system = MultiAgentSystem()
    
    # Demo 1: Fun question with all personalities
    demo_question(
        agent_system,
        "What would happen if cats ruled the world?",
        "Example 1: All Personalities Responding"
    )
    
    # Demo 2: Toggle off some personalities
    print("### Example 2: Toggle Off Sadness and Fear")
    print("Disabling Sadness and Fear...\n")
    agent_system.toggle_agent("sadness")
    agent_system.toggle_agent("fear")
    
    demo_question(
        agent_system,
        "What's the best ice cream flavor?",
        "Question with Joy, Anger, and Disgust Only"
    )
    
    # Demo 3: Monitor rejection
    agent_system.toggle_agent("sadness")  # Re-enable
    agent_system.toggle_agent("fear")     # Re-enable
    
    demo_question(
        agent_system,
        "How do I fix my computer?",
        "Example 3: Monitor Agent Rejecting Serious Question"
    )
    
    # Demo 4: Another fun question
    demo_question(
        agent_system,
        "Would you rather fight one horse-sized duck or 100 duck-sized horses?",
        "Example 4: Classic Fun Question"
    )
    
    print("✅ Demo complete! Try running the full UI with: python -m ui.gradio_app")
    print_divider()


if __name__ == "__main__":
    main()
