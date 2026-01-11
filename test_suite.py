"""
Comprehensive test suite for Inside Out Multi-Agent System
"""
import sys
sys.path.insert(0, '/home/runner/work/Inside-out/Inside-out')

from agents import MultiAgentSystem, PersonalityAgent, MonitorAgent
from config import PERSONALITY_PROMPTS


def test_personality_prompts():
    """Test that all personality prompts are defined"""
    print("Testing personality prompts...")
    required_personalities = ["joy", "sadness", "anger", "fear", "disgust"]
    
    for personality in required_personalities:
        assert personality in PERSONALITY_PROMPTS, f"Missing personality: {personality}"
        config = PERSONALITY_PROMPTS[personality]
        assert "name" in config, f"Missing name for {personality}"
        assert "emoji" in config, f"Missing emoji for {personality}"
        assert "system_prompt" in config, f"Missing system_prompt for {personality}"
    
    print("✅ All personality prompts defined correctly")


def test_personality_agents():
    """Test individual personality agents"""
    print("\nTesting personality agents...")
    
    for personality in ["joy", "sadness", "anger", "fear", "disgust"]:
        agent = PersonalityAgent(personality)
        assert agent.name is not None
        assert agent.emoji is not None
        assert agent.enabled == True
        
        # Test toggle
        agent.toggle()
        assert agent.enabled == False
        agent.toggle()
        assert agent.enabled == True
    
    print("✅ All personality agents work correctly")


def test_monitor_agent():
    """Test monitor agent"""
    print("\nTesting monitor agent...")
    
    monitor = MonitorAgent()
    
    # Test approval of fun questions
    fun_questions = [
        "What's the best pizza topping?",
        "Would you rather have wings or super speed?",
        "If animals could talk, which would be the rudest?"
    ]
    
    for question in fun_questions:
        approved, message = monitor.check_question(question)
        assert approved == True, f"Should approve: {question}"
    
    # Test rejection of serious questions
    serious_questions = [
        "How do I fix my computer?",
        "I'm feeling depressed about work",
        "What stocks should I invest in?"
    ]
    
    for question in serious_questions:
        approved, message = monitor.check_question(question)
        assert approved == False, f"Should reject: {question}"
    
    print("✅ Monitor agent works correctly")


def test_multi_agent_system():
    """Test the complete multi-agent system"""
    print("\nTesting multi-agent system...")
    
    system = MultiAgentSystem()
    
    # Test with all agents enabled
    result = system.get_responses("What's the best ice cream flavor?")
    assert result["approved"] == True
    assert len(result["responses"]) == 5  # All 5 personalities
    
    # Test with some agents disabled
    system.toggle_agent("joy")
    system.toggle_agent("sadness")
    result = system.get_responses("What's your favorite color?")
    assert result["approved"] == True
    assert len(result["responses"]) == 3  # Only 3 active
    
    # Re-enable agents
    system.toggle_agent("joy")
    system.toggle_agent("sadness")
    
    # Test monitor rejection
    result = system.get_responses("How do I fix my computer?")
    assert result["approved"] == False
    assert "monitor_message" in result
    
    # Test agent status
    status = system.get_agent_status()
    assert len(status) == 5
    assert all(enabled for enabled in status.values())
    
    print("✅ Multi-agent system works correctly")


def test_response_format():
    """Test that responses are formatted correctly"""
    print("\nTesting response format...")
    
    system = MultiAgentSystem()
    result = system.get_responses("What's the best pizza topping?")
    
    assert "approved" in result
    assert "monitor_message" in result
    assert "responses" in result
    
    for response in result["responses"]:
        assert "agent" in response
        assert "emoji" in response
        assert "color" in response
        assert "response" in response
    
    print("✅ Response format is correct")


def run_all_tests():
    """Run all tests"""
    print("="*70)
    print("RUNNING COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    try:
        test_personality_prompts()
        test_personality_agents()
        test_monitor_agent()
        test_multi_agent_system()
        test_response_format()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
