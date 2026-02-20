# 🎭 Inside Out - Multi-Agent Personality Chat

A fun multi-agent system inspired by Pixar's **Inside Out** movie, built with AutoGen (AG2.ai). Different personality agents (Joy, Sadness, Anger, Fear, and Disgust) respond to your questions with their unique emotional perspectives!

## ✨ Features

- 🎨 **5 Unique Personality Agents** - Each emotion has its own distinct personality and response style
- 🎮 **Interactive UI** - Toggle personalities on/off in real-time
- 🚦 **Monitor Agent** - Ensures only fun, lighthearted questions are processed
- 💬 **Multiple Interfaces** - CLI and web UIs (Streamlit/Gradio)
- 🎬 **Inside Out Inspired** - Authentic personality traits from the beloved Pixar characters

## 🎭 The Personalities

| Emotion | Personality | Response Style |
|---------|-------------|----------------|
| 😄 **Joy** | Optimistic & Excited | Enthusiastic, positive, always sees the bright side |
| 😢 **Sadness** | Melancholic & Thoughtful | Gloomy but sweet, empathetic and caring |
| 😡 **Anger** | Passionate & Intense | Hot-headed, uses emphasis, comically frustrated |
| 😰 **Fear** | Cautious & Worried | Anxious, sees risks everywhere, adorably paranoid |
| 🤢 **Disgust** | Sassy & Particular | High standards, sarcastic, hilariously judgmental |

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/vlearner/Inside-out.git
   cd Inside-out
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Configure API keys**
   
   If you want to use actual LLM responses (future enhancement), copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

### Running the Application

#### Option 1: Quick Demo 🎬

```bash
python demo.py
```

This runs a quick demonstration showing all features without needing a browser!

#### Option 2: Run Tests 🧪

```bash
python test_suite.py
```

Runs comprehensive tests to verify all components work correctly.

#### Option 3: Streamlit UI (requires Jan AI server)

Start your local Jan AI server first (download from https://jan.ai). Jan AI provides the local
LLM backend for responses and defaults to `http://127.0.0.1:1337/v1`
(see `.env.example` for overrides).

```bash
streamlit run ui/streamlit_app.py
```

Then open your browser to `http://localhost:8501`. Streamlit is the primary chat UI;
Gradio below is a lightweight alternative.

#### Option 4: Web UI (Gradio)

```bash
python -m ui.gradio_app
```

Then open your browser to `http://localhost:7860`.

#### Option 5: Command Line Interface (requires Jan AI server)

Start your local Jan AI server (see `.env.example` for the default `JAN_BASE_URL`), then run:

```bash
python main.py
```

## 🎮 How to Use

### Web UI

1. **Ask a Fun Question** - Type your lighthearted question in the text box
2. **Toggle Personalities** - Use the checkboxes to turn emotions on/off
3. **Get Responses** - Click "Get Responses!" to see how each active emotion reacts!

### CLI

1. **Ask Questions** - Simply type your question and press Enter
2. **Toggle Personalities** - Use command: `toggle joy`, `toggle sadness`, etc.
3. **Check Status** - Type `status` to see which personalities are active
4. **Exit** - Type `quit` or `exit` to close the program

## 💡 Example Questions

Here are some fun questions to try:

- "What's the best pizza topping?"
- "If you could only eat one color of food forever, what color would you choose?"
- "Would you rather fight one horse-sized duck or 100 duck-sized horses?"
- "What would happen if cats ruled the world?"
- "What's the most useless superpower?"
- "If animals could talk, which would be the rudest?"

## 🚦 Monitor Agent

The Monitor Agent ensures this stays a **fun zone**! It will reject:

- ❌ Serious political questions
- ❌ Heavy emotional issues
- ❌ Technical support requests
- ❌ Medical/legal/financial advice
- ❌ Any serious real-world problems

Keep it fun and lighthearted! 🎉

## 📁 Project Structure

```
Inside-out/
├── agents/
│   ├── __init__.py
│   └── personality_agents.py    # Agent implementations
├── config/
│   ├── __init__.py
│   └── personalities.py         # Personality prompts and configs
├── ui/
│   ├── gradio_app.py           # Web UI using Gradio
│   └── streamlit_app.py        # Streamlit chat UI (Jan AI)
├── main.py                      # CLI entry point
├── demo.py                      # Quick demo script
├── test_suite.py               # Comprehensive test suite
├── requirements.txt             # Python dependencies
├── .env.example                # Example environment configuration
└── README.md                    # This file!
```

## 🔧 Technical Details

### Built With

- **AutoGen (AG2)** - Multi-agent framework
- **Gradio** - Web UI framework
- **Streamlit** - Chat UI framework
- **Python 3.8+** - Core language

### Architecture

The system consists of:

1. **Personality Agents** - Five emotion-based agents with unique prompts
2. **Monitor Agent** - Filters questions to ensure appropriateness
3. **Multi-Agent System** - Orchestrates agent interactions
4. **UI Layer** - Gradio web interface and CLI

## 🎯 Future Enhancements

- [ ] Integrate actual AutoGen LLM agents for dynamic responses
- [ ] Add conversation history
- [ ] Support for custom personalities
- [ ] Voice input/output
- [ ] More complex agent interactions
- [ ] Export conversation transcripts

## 🤝 Contributing

This is a fun project! Feel free to fork and experiment. Contributions are welcome!

## 📝 License

This project is for educational and entertainment purposes.

## 🎬 Credits

Inspired by Pixar's **Inside Out** movie. All character personalities and emotions are based on the beloved film characters.

---

**Remember: Keep it fun! Keep it lighthearted! Keep it silly!** 🎉😄
