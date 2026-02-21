# 🧠 Inside Out Multi-Agent System — Agent Documentation

A comprehensive reference for every agent class, supporting module, and configuration option in the **Inside Out Multi-Agent System**.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Monitor Agent](#2-monitor-agent)
3. [Decision Agent](#3-decision-agent)
4. [Personality Agents (×5)](#4-personality-agents-5)
   - [Joy 😄](#joy-)
   - [Sadness 😢](#sadness-)
   - [Anger 😡](#anger-)
   - [Fear 😰](#fear-)
   - [Disgust 🤢](#disgust-)
5. [LLM Backend — Jan AI Client](#5-llm-backend--jan-ai-client)
6. [Weather Tool Integration](#6-weather-tool-integration)
7. [Multi-Agent Orchestration](#7-multi-agent-orchestration)
8. [File Map](#8-file-map)
9. [Adding a New Agent](#9-adding-a-new-agent)

---

## 1. Architecture Overview

```
User Message
     │
     ▼
┌─────────────────────┐
│    Monitor Agent    │  ← Gate-keeper: keyword blocklist + length check
└──────────┬──────────┘
           │ Approved?
           │  No  ──► Rejection message returned to user
           │  Yes
           ▼
┌─────────────────────┐
│   Decision Agent    │  ← Conductor: LLM analysis → {joy, sadness, ...}
│   (or @mention      │     falls back to keyword heuristic when LLM
│    override)        │     is unavailable
└──────────┬──────────┘
           │ emotions[] selected (1–3)
           │
     ┌─────┴──────────────────────────────────┐
     │  Personality Agents (parallel queries) │
     ├─────────────────────────────────────────┤
     │  😄 Joy  😢 Sadness  😡 Anger           │
     │  😰 Fear  🤢 Disgust                    │
     └──────────────────┬──────────────────────┘
                        │ each agent:
                        │  1. Strip @mentions
                        │  2. Detect weather → fetch data
                        │  3. Build prompt
                        │  4. POST to Jan AI (LLM)  ◄──► Jan AI Server
                        │  5. Fallback → static response
                        ▼
              Formatted Response List
              {approved, monitor_message,
               responses[], decisions{}}
```

---

## 2. Monitor Agent

**Class:** `MonitorAgent` — `agents/personality_agents.py`

### Purpose

The Monitor Agent is the **gate-keeper** that sits at the very front of the pipeline. It inspects every incoming user message and rejects anything that is too serious, inappropriate, or too short for the fun Inside Out chat zone.

### Keyword Blocklist

The `check_question()` method rejects any message containing one of the following keywords (case-insensitive):

| Category | Keywords |
|---|---|
| Mental health | `depressed`, `suicide` |
| Harm | `kill`, `die`, `death` |
| Geopolitics | `war`, `politics`, `election` |
| Medical | `medical`, `doctor`, `sick`, `disease` |
| Legal | `legal`, `lawyer`, `court`, `sue` |
| Work / business | `business`, `stock`, `investment`, `work problem` |
| Help-seeking | `help me`, `advice on`, `how do i fix`, `technical support` |

### Minimum Length Check

Messages shorter than **5 characters** (after stripping whitespace) are also rejected.

### Behaviour Examples

```python
monitor = MonitorAgent()

# ✅ Approved
monitor.check_question("What's your favourite pizza?")
# → (True, "✅ Approved!")

# ❌ Rejected — serious keyword
monitor.check_question("I feel depressed today")
# → (False, "🚦 **Monitor**: This seems too serious for our fun zone! Try something silly instead! 😄")

# ❌ Rejected — too short
monitor.check_question("hi")
# → (False, "🚦 **Monitor**: Give me something fun to work with! Try a fun question! 🦸")
```

### System Prompt (`config/personalities.py`)

```
You are the Monitor Agent for a fun Inside Out personality chat.

ALLOW: Fun, silly, lighthearted questions
REJECT: Serious topics (politics, medical, legal, work problems, mental health)

If NOT fun: "REJECT: This is a fun zone! Try something silly instead."
If fun: "APPROVE"
```

> **Note:** The current implementation uses the keyword blocklist only (no LLM call in `check_question`). The system prompt is stored for reference but is not sent to the LLM at runtime.

---

## 3. Decision Agent

**Class:** `DecisionAgent` — `agents/personality_agents.py`

### Purpose

The Decision Agent acts as the **conductor/orchestrator**. After the Monitor Agent approves a message, the Decision Agent determines which 1–3 emotions should respond to it.

### LLM-Based Analysis

When Jan AI is available, `analyze_message()` sends the user's message to the LLM with the `DECISION_AGENT_PROMPT` and expects a JSON response such as:

```json
{"joy": true, "sadness": false, "anger": false, "fear": false, "disgust": false}
```

The prompt instructs the model to:
- Pick only **1–3** most-relevant emotions
- Route neutral/informational queries (weather, facts) to **Joy**
- Route negative topics to relevant emotions

Any markdown code fences (` ```json `) are stripped before JSON parsing. If parsing fails, the agent falls back to keyword heuristics.

### Fallback Keyword Heuristic

Used when the LLM is unavailable or returns invalid JSON:

| Emotion | Keywords |
|---|---|
| 😄 **Joy** | `favorite`, `best`, `love`, `fun`, `happy`, `excited`, `great`, `amazing`, `pizza`, `food`, `like`, `enjoy`, `weather`, `temperature`, `forecast`, `sunny`, `rain` |
| 😢 **Sadness** | `sad`, `miss`, `lonely`, `wish`, `lost`, `remember`, `gone`, `cry` |
| 😡 **Anger** | `unfair`, `hate`, `angry`, `frustrat`, `stupid`, `ridiculous`, `worst`, `terrible` |
| 😰 **Fear** | `scary`, `afraid`, `worried`, `dangerous`, `risk`, `nervous`, `what if` |
| 🤢 **Disgust** | `gross`, `ew`, `yuck`, `cringe`, `tacky`, `ugly`, `embarrassing`, `fashion` |

If **no keyword matches**, Joy responds by default (neutral questions always get a response).

### @Mention Override

Users can prefix a message with `@emotionname` to bypass the Decision Agent entirely and target one or more emotions directly:

```
@joy What's the best ice cream flavour?
@anger @disgust This pizza topping is so wrong
```

When mentions are detected, `MultiAgentSystem.get_responses()` sets:

```python
decisions = {e: (e in mentioned) for e in self.agents.keys()}
```

The Decision Agent is **not called** in this path.

---

## 4. Personality Agents (×5)

**Class:** `PersonalityAgent` — `agents/personality_agents.py`  
**Config:** `config/personalities.py`

All five agents share the same `PersonalityAgent` base class and the same 5-step response flow.

### Common 5-Step Response Flow

```
get_response(question)
  │
  ├─ Step 1: Strip @mention tokens  (re.sub r'@\w+', '', question)
  ├─ Step 2: Detect weather query   (is_weather_query → extract_location → get_weather)
  ├─ Step 3: Build prompt           (system_prompt + user_message ± weather context)
  ├─ Step 4: Send to Jan AI         (jan_client.chat(messages, max_tokens=…))
  └─ Step 5: Fallback               (_generate_personality_response / _generate_weather_response)
```

Weather responses receive an extra **250 tokens** (`weather_max_tokens = 250`) so the model has enough room to include the actual numbers from the weather data.

---

### Joy 😄

| Property | Value |
|---|---|
| Emoji | 😄 |
| Color | yellow |
| Tone | Optimistic, enthusiastic, energetic |
| Topics | Positive/fun topics, neutral informational queries, weather |

**System Prompt Rules (from `config/personalities.py`):**
- Keep responses SHORT (1–2 sentences max)
- Do **not** repeat or echo what the user said
- React with YOUR feelings, don't describe theirs
- Be positive and energetic
- Use 1–2 exclamation marks max

**Static fallback response:**
> "Ooh, I love thinking about this! So exciting! ✨"

---

### Sadness 😢

| Property | Value |
|---|---|
| Emoji | 😢 |
| Color | blue |
| Tone | Melancholic, sweet, gloomy-but-cute |
| Topics | Loss, longing, emotional depth, memories |

**System Prompt Rules:**
- Keep responses SHORT (1–2 sentences max)
- Do **not** repeat what the user said
- Share YOUR sad perspective, don't describe theirs
- Be gloomy in a cute way
- Use phrases like `"I guess..."` or `"*sigh*"`

**Static fallback response:**
> "*sigh* I guess that's something to think about... 😔"

---

### Anger 😡

| Property | Value |
|---|---|
| Emoji | 😡 |
| Color | red |
| Tone | Passionate, fired-up, funny-angry (not mean) |
| Topics | Injustice, frustration, unfair situations |

**System Prompt Rules:**
- Keep responses SHORT (1–2 sentences max)
- Do **not** repeat or echo what the user said
- React with YOUR frustration about something RELATED
- Use occasional CAPS but don't overdo it
- Be funny-angry, not mean

**Static fallback response:**
> "Hmm, that's making me think! 😤"

---

### Fear 😰

| Property | Value |
|---|---|
| Emoji | 😰 |
| Color | purple |
| Tone | Nervous, cautious, adorably paranoid |
| Topics | Risk, danger, scary scenarios, "what if" situations |

**System Prompt Rules:**
- Keep responses SHORT (1–2 sentences max)
- Do **not** repeat what the user said
- Express YOUR worry about a related risk
- Be adorably paranoid
- Use `"what if"` or `"but wait"`

**Static fallback response:**
> "Oh, that makes me a bit nervous to consider! 😰"

---

### Disgust 🤢

| Property | Value |
|---|---|
| Emoji | 🤢 |
| Color | green |
| Tone | Sassy, high standards, witty and judgmental (fun way) |
| Topics | Fashion, taste, cringe-worthy things, tacky trends |

**System Prompt Rules:**
- Keep responses SHORT (1–2 sentences max)
- Do **not** repeat what the user said
- Give YOUR sassy opinion on something related
- Be witty and judgmental (in a fun way)
- Use `"ugh"` or eye-roll vibes

**Static fallback response:**
> "Well, I have opinions about that... 💅"

---

## 5. LLM Backend — Jan AI Client

**Class:** `JanClient` — `utils/jan_client.py`

### Singleton Pattern

All agents share a **single** `JanClient` instance via the class-level variable on `PersonalityAgent`:

```python
class PersonalityAgent:
    _jan_client = None          # shared across all instances
    _connection_tested = False  # one-time connection test flag

    @classmethod
    def get_jan_client(cls):
        if cls._jan_client is not None:
            return cls._jan_client
        # … initialise once, store in cls._jan_client …
```

`DecisionAgent` also calls `PersonalityAgent.get_jan_client()`, so the entire system uses the same client object.

### Configuration

All values are read from the environment (`.env` file), with constructor arguments taking priority:

| Env Variable | Default | Description |
|---|---|---|
| `JAN_BASE_URL` | `http://127.0.0.1:1337/v1` | Jan AI server URL |
| `JAN_API_KEY` | *(empty)* | API key (optional for local server) |
| `JAN_MODEL_NAME` | `Meta-Llama-3_1-8B-Instruct_Q4_K_M` | Model to use |
| `TEMPERATURE` | `0.8` | Sampling temperature |
| `MAX_TOKENS` | `500` | Max tokens per response |

Priority order for each value: **constructor argument → env var → class default**.

### Retry Logic

`_make_request()` retries up to **3 times** with **exponential back-off**:

```
attempt 1 → failure → sleep 1 s
attempt 2 → failure → sleep 2 s
attempt 3 → failure → raise JanClientError
```

- `ConnectionError` and `Timeout` are retried
- HTTP **4xx** errors are **not** retried (raised immediately)
- HTTP **5xx** errors are retried

### Graceful Degradation

If the Jan AI server is unreachable or returns an error after all retries:
1. `PersonalityAgent.get_jan_client()` catches the exception and sets `_jan_client = None`
2. `get_response()` detects the `None` client and skips to **Step 5**
3. Step 5 returns a static hardcoded fallback string

The system **never crashes** due to a missing LLM — it always returns something.

### Connection Test

On first use, the client calls `GET /models` to verify connectivity. This is **informational only** — even if it fails, the client is kept and chat requests are still attempted:

```python
if cls._jan_client.test_connection():
    logger.info("✅ Connected to Jan AI!")
else:
    logger.warning("⚠️ Jan AI connection test failed — will still attempt requests")
```

---

## 6. Weather Tool Integration

**File:** `tools/weather_tool.py`

### Functions

| Function | Signature | Description |
|---|---|---|
| `is_weather_query` | `(message: str) → bool` | Returns `True` if the message contains weather keywords |
| `extract_location_from_message` | `(message: str) → Optional[str]` | Extracts a location string from the message |
| `get_weather` | `(location: str) → str` | Fetches current weather and returns a formatted string |

### `is_weather_query()` Keywords

```python
["weather", "temperature", "forecast", "rain", "sunny", "cloudy", "snow",
 "storm", "wind", "humid", "cold", "hot", "warm", "freezing",
 "celsius", "fahrenheit", "degrees", "outside",
 "tomorrow weather", "today weather"]
```

### `extract_location_from_message()` Patterns

The function tries a prioritised list of string patterns (most-specific first):

```
"current weather at "  →  "what is the weather in "  →  "weather in "
"weather at "          →  "weather for "             →  "temperature in "
"forecast for "        →  ...
```

If no pattern matches, a **regex fallback** looks for a capitalised word or two-letter US state abbreviation following a weather keyword:

```python
# Full pattern (abbreviated weather keywords shown as "…" for readability):
r'\b(?:weather|temperature|forecast|rain|snow|sunny|cold|hot|warm)\b.{0,20}?\b([A-Z][a-zA-Z]+(?:\s+[A-Z]{2})?)'
```

### Integration with Personality Agents

Inside `PersonalityAgent.get_response()` (Steps 2–3):

```python
if WEATHER_AVAILABLE and is_weather_query(clean_question):
    location = extract_location_from_message(clean_question)
    if location:
        weather_data = get_weather(location)
        weather_context = f"\n\nCurrent weather information:\n{weather_data}"
```

The weather context is appended to the user message, along with mandatory rules that instruct the LLM to state the exact temperature number and condition:

```
RULES FOR YOUR RESPONSE:
1. You MUST state the exact temperature number from the data above (e.g. '33.1°F').
2. You MUST state the weather condition from the data above (e.g. 'Overcast').
3. You MAY also mention feels-like, humidity, or wind from the data.
4. Say it all in your personality style — be yourself!
5. Keep it to 2-3 sentences.
```

### Extra Token Budget

Weather responses receive **250 extra tokens** to ensure the model includes the actual numbers. When `max_tokens` is `None` (non-weather), `chat()` falls back to the client's configured `MAX_TOKENS` default (500):

```python
weather_max_tokens = 250 if weather_context else None   # None → uses default MAX_TOKENS
llm_response = jan_client.chat(messages, max_tokens=weather_max_tokens)
```

---

## 7. Multi-Agent Orchestration

**Class:** `MultiAgentSystem` — `agents/personality_agents.py`

### Initialisation

```python
system = MultiAgentSystem()
# Creates: 5 × PersonalityAgent (all enabled by default)
#          1 × MonitorAgent
#          1 × DecisionAgent
```

### Full Pipeline

```python
result = system.get_responses(question, mentioned=["joy"], llm_config=None)
```

| Step | Component | Action |
|---|---|---|
| 1 | `MonitorAgent.check_question()` | Reject or approve |
| 2 | `@mention` check | If present, set decisions directly (bypass step 3) |
| 3 | `DecisionAgent.analyze_message()` | LLM → JSON decisions (or keyword fallback) |
| 4 | `PersonalityAgent.get_response()` | Run for each `True` emotion that is enabled |

### Response Format

```python
{
    "approved": True,          # False if Monitor rejected
    "monitor_message": "✅ Approved!",
    "responses": [
        {
            "agent": "Joy",
            "emotion": "joy",
            "emoji": "😄",
            "color": "yellow",
            "response": "😄 **Joy**: Ooh, I love that! ✨"
        },
        # … one entry per responding emotion
    ],
    "decisions": {
        "joy": True,
        "sadness": False,
        "anger": False,
        "fear": False,
        "disgust": False
    }
}
```

When rejected by the Monitor, only `approved` and `monitor_message` are meaningful:

```python
{
    "approved": False,
    "monitor_message": "🚦 **Monitor**: This seems too serious ...",
    "responses": [],
    "decisions": {}
}
```

### Runtime Controls

| Method | Signature | Description |
|---|---|---|
| `toggle_agent` | `(agent_type: str) → bool` | Flip an agent on/off; returns new state |
| `get_agent_status` | `() → Dict[str, bool]` | Dict of `{emotion: enabled}` for all agents |
| `get_agent_info` | `() → List[Dict]` | Full info list (type, name, emoji, color, enabled) |

```python
system.toggle_agent("anger")      # disable/enable Anger
system.get_agent_status()
# → {"joy": True, "sadness": True, "anger": False, "fear": True, "disgust": True}

system.get_agent_info()
# → [{"type": "joy", "name": "Joy", "emoji": "😄", "color": "yellow", "enabled": True}, ...]
```

---

## 8. File Map

```
Inside-out/
├── agents/
│   └── personality_agents.py   # PersonalityAgent, DecisionAgent,
│                               #   MonitorAgent, MultiAgentSystem
├── config/
│   ├── personalities.py        # PERSONALITY_PROMPTS, MONITOR_PROMPT
│   └── agents.py               # (legacy config helpers)
├── tools/
│   └── weather_tool.py         # is_weather_query, extract_location_from_message,
│                               #   get_weather, get_forecast
├── utils/
│   ├── jan_client.py           # JanClient, JanClientError, get_llm_config,
│   │                           #   validate_environment
│   └── weather_client.py       # WeatherClient (raw API wrapper)
├── ui/                         # Gradio / Streamlit front-end
├── tests/                      # Unit and integration tests
├── main.py                     # Entry point
├── demo.py                     # Demo script
├── .env.example                # Environment variable template
└── requirements.txt
```

---

## 9. Adding a New Agent

Follow these steps to add a new emotion (e.g., **Surprise 😲**):

### Step 1 — Define the personality in `config/personalities.py`

```python
PERSONALITY_PROMPTS = {
    # … existing entries …
    "surprise": {
        "name": "Surprise",
        "color": "orange",
        "emoji": "😲",
        "system_prompt": """You are Surprise from Inside Out — caught off guard!

RULES:
- Keep responses SHORT (1-2 sentences max)
- DO NOT repeat what the user said
- React with YOUR astonishment
- Use "Wait, what?!" or "I did NOT see that coming!"
"""
    }
}
```

### Step 2 — Register the agent in `MultiAgentSystem.__init__()`

```python
# agents/personality_agents.py
self.agents: Dict[str, PersonalityAgent] = {
    "joy":      PersonalityAgent("joy",      enabled=True),
    "sadness":  PersonalityAgent("sadness",  enabled=True),
    "anger":    PersonalityAgent("anger",    enabled=True),
    "fear":     PersonalityAgent("fear",     enabled=True),
    "disgust":  PersonalityAgent("disgust",  enabled=True),
    "surprise": PersonalityAgent("surprise", enabled=True),  # ← add here
}
```

### Step 3 — Update the fallback keyword list in `DecisionAgent._fallback_analysis()`

```python
# agents/personality_agents.py — inside _fallback_analysis()
surprise_keywords = ["unexpected", "suddenly", "wow", "whoa", "surprise",
                     "unbelievable", "shocking", "never expected"]

decisions["surprise"] = False
for keyword in surprise_keywords:
    if keyword in message_lower:
        decisions["surprise"] = True
        break
```

### Step 4 — Update `DECISION_AGENT_PROMPT`

Add the new emotion to the "Available emotions" list and the rules:

```python
DECISION_AGENT_PROMPT = """...
Available emotions:
- joy: ...
- surprise: Responds to shocking, unexpected, or jaw-dropping topics
...
"""
```

### Step 5 — Update UI toggles

If the UI renders agent toggles dynamically from `get_agent_info()`, no changes are needed — the new agent will appear automatically. If toggles are hard-coded in `ui/`, add a toggle for `"surprise"`.

### Step 6 — Add a static fallback to `_generate_personality_response()`

```python
# agents/personality_agents.py
personality_responses = {
    # … existing …
    "surprise": "Wait — I did NOT see that coming! 😲",
}
```
