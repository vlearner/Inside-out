"""
Gradio UI for Inside Out Multi-Agent System
"""
import gradio as gr
from agents import MultiAgentSystem


# Initialize the multi-agent system
agent_system = MultiAgentSystem()

# Color scheme based on Inside Out characters
COLORS = {
    "joy": "#FFD700",      # Gold/Yellow
    "sadness": "#4169E1",  # Royal Blue
    "anger": "#DC143C",    # Crimson Red
    "fear": "#9370DB",     # Medium Purple
    "disgust": "#32CD32",  # Lime Green
}


def process_question(question: str, joy_enabled: bool, sadness_enabled: bool, 
                     anger_enabled: bool, fear_enabled: bool, disgust_enabled: bool):
    """Process a question with the enabled personalities"""
    
    # Update agent statuses based on UI toggles
    agent_system.agents["joy"].enabled = joy_enabled
    agent_system.agents["sadness"].enabled = sadness_enabled
    agent_system.agents["anger"].enabled = anger_enabled
    agent_system.agents["fear"].enabled = fear_enabled
    agent_system.agents["disgust"].enabled = disgust_enabled
    
    if not question.strip():
        return "Please ask a fun question! 😊"
    
    # Get responses from the system
    result = agent_system.get_responses(question)
    
    if not result["approved"]:
        return result["monitor_message"]
    
    # Check if any agents are enabled
    if not result["responses"]:
        return "⚠️ Oops! No personalities are turned on! Please enable at least one emotion to get a response! 🎭"
    
    # Format the responses
    output = f"### Question: {question}\n\n"
    output += "---\n\n"
    
    for response in result["responses"]:
        output += f"{response['response']}\n\n"
    
    return output


def create_ui():
    """Create and configure the Gradio interface"""
    
    with gr.Blocks(
        title="Inside Out - Multi-Agent Personality Chat"
    ) as app:
        
        gr.Markdown(
            """
            # 🎭 Inside Out - Multi-Agent Personality Chat
            ### Ask fun questions and watch different emotions respond!
            
            Each personality from Inside Out will give you their unique take on your question.
            Toggle personalities on/off to customize who responds!
            
            **Remember:** This is a FUN zone only! Keep questions lighthearted and silly! 🎉
            """
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 🎨 Personality Controls")
                gr.Markdown("*Toggle emotions on/off:*")
                
                joy_toggle = gr.Checkbox(
                    label="😄 Joy (Optimistic & Excited)",
                    value=True,
                    elem_classes=["personality-toggle"]
                )
                
                sadness_toggle = gr.Checkbox(
                    label="😢 Sadness (Melancholic & Thoughtful)",
                    value=True,
                    elem_classes=["personality-toggle"]
                )
                
                anger_toggle = gr.Checkbox(
                    label="😡 Anger (Passionate & Intense)",
                    value=True,
                    elem_classes=["personality-toggle"]
                )
                
                fear_toggle = gr.Checkbox(
                    label="😰 Fear (Cautious & Worried)",
                    value=True,
                    elem_classes=["personality-toggle"]
                )
                
                disgust_toggle = gr.Checkbox(
                    label="🤢 Disgust (Sassy & Particular)",
                    value=True,
                    elem_classes=["personality-toggle"]
                )
                
                gr.Markdown(
                    """
                    ---
                    ### 💡 Fun Question Ideas:
                    - What's the best pizza topping?
                    - If you could only eat one color of food, what color?
                    - Would you rather have spaghetti for hair or sweat maple syrup?
                    - What's the worst superpower?
                    """
                )
            
            with gr.Column(scale=2):
                gr.Markdown("## 💬 Ask Your Question")
                
                question_input = gr.Textbox(
                    label="Your Fun Question",
                    placeholder="Ask something fun and lighthearted! Like: 'What would happen if cats ruled the world?'",
                    lines=3
                )
                
                submit_btn = gr.Button("🎪 Get Responses!", variant="primary", size="lg")
                
                output = gr.Markdown(
                    label="Responses",
                    elem_classes=["output-box"]
                )
                
                gr.Markdown(
                    """
                    ---
                    ### 🎬 About Inside Out
                    This project is inspired by Pixar's Inside Out, featuring five core emotions:
                    **Joy**, **Sadness**, **Anger**, **Fear**, and **Disgust**. Each personality agent
                    responds with their unique emotional perspective!
                    """
                )
        
        # Connect the button to the processing function
        submit_btn.click(
            fn=process_question,
            inputs=[
                question_input,
                joy_toggle,
                sadness_toggle,
                anger_toggle,
                fear_toggle,
                disgust_toggle
            ],
            outputs=output
        )
        
        # Also allow Enter key to submit
        question_input.submit(
            fn=process_question,
            inputs=[
                question_input,
                joy_toggle,
                sadness_toggle,
                anger_toggle,
                fear_toggle,
                disgust_toggle
            ],
            outputs=output
        )
    
    return app


if __name__ == "__main__":
    app = create_ui()
    app.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="amber",
            secondary_hue="blue",
        ),
        css="""
        .personality-toggle {
            font-size: 16px;
            font-weight: bold;
        }
        .output-box {
            font-size: 16px;
            line-height: 1.6;
        }
        """
    )
