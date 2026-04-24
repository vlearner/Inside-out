"""
OpenAI-compatible API client wrapper.
Supports both local LLM backend and Groq Cloud backends.
"""
import os
import logging
import time
import json
from typing import Dict, Optional, Any, List
import requests
from utils.config import get_secret

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLM-CLIENT")


class LLMClientError(Exception):
    """Custom exception for LLM backend client errors"""
    pass


class LLMError(LLMClientError):
    """Structured LLM error with a classified error_type.

    Extends LLMClientError for backwards compatibility — existing code that
    catches LLMClientError will still work unchanged.

    error_type values:
      - ``"connection_refused"`` — LLM backend server is not running.
      - ``"timeout"``            — LLM backend is running but too slow / overloaded.
      - ``"server_error"``       — 5xx HTTP response from LLM backend.
      - ``"client_error"``       — 4xx HTTP response (bad request / config).
    """

    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type  # one of the four values above

    def __str__(self) -> str:
        return f"[{self.error_type}] {super().__str__()}"


class LLMClient:
    """
    OpenAI-compatible API client for making LLM requests.

    This client supports LLM backend (local) and Groq (cloud) and provides
    methods for chat completions with retry logic and error handling.
    """

    # Default fallback values — override via env vars or constructor kwargs
    # NOTE: API keys are intentionally empty by default.
    #       Set JAN_API_KEY / GROQ_API_KEY in .streamlit/secrets.toml (see secrets.example.toml).
    DEFAULT_PROVIDER = "jan"
    SUPPORTED_PROVIDERS = {"jan", "groq"}
    DEFAULT_BASE_URL = "http://127.0.0.1:1337/v1"
    DEFAULT_API_KEY = ""          # no key hardcoded — must come from .env
    DEFAULT_MODEL = "Meta-Llama-3_1-8B-Instruct_Q4_K_M"
    DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize the LLM backend client.

        Priority order for each value:
          1. Explicit constructor argument
          2. Environment variable (LLM_PROVIDER + provider-specific vars)
          3. Class-level default constant

        This means you can override any value in tests or scripts without
        touching environment variables:

            client = LLMClient(api_key="my-key", model_name="mistral-7b")
        """
        self.provider = (
            provider
            if provider is not None
            else get_secret("llm", "provider", "LLM_PROVIDER", self.DEFAULT_PROVIDER)
        ).strip().lower()

        if self.provider not in self.SUPPORTED_PROVIDERS:
            raise LLMClientError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. "
                f"Supported values: {', '.join(sorted(self.SUPPORTED_PROVIDERS))}."
            )

        if self.provider == "groq":
            env_base_url = get_secret("groq", "base_url", "GROQ_BASE_URL", self.DEFAULT_GROQ_BASE_URL)
            env_api_key = get_secret("groq", "api_key", "GROQ_API_KEY", self.DEFAULT_API_KEY)
            env_model = get_secret("groq", "model_name", "GROQ_MODEL_NAME", self.DEFAULT_GROQ_MODEL)
        else:
            env_base_url = get_secret("jan", "base_url", "JAN_BASE_URL", self.DEFAULT_BASE_URL)
            env_api_key = get_secret("jan", "api_key", "JAN_API_KEY", self.DEFAULT_API_KEY)
            env_model = get_secret("jan", "model_name", "JAN_MODEL_NAME", self.DEFAULT_MODEL)

        self.base_url = (
            base_url
            if base_url is not None
            else env_base_url
        )
        self.api_key = (
            api_key
            if api_key is not None
            else env_api_key
        )
        self.model_name = (
            model_name
            if model_name is not None
            else env_model
        )
        self.temperature = float(get_secret("llm", "temperature", "TEMPERATURE", "0.8"))
        self.max_tokens = int(get_secret("llm", "max_tokens", "MAX_TOKENS", "500"))

        self._validate_config()
        logger.info(
            f"LLMClient initialized with provider={self.provider}, "
            f"base URL={self.base_url}, model={self.model_name}"
        )

    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        if not self.base_url:
            raise LLMClientError(
                "LLM base URL not set. Please configure .streamlit/secrets.toml."
            )
        if self.provider == "groq" and not self.api_key:
            raise LLMClientError(
                "groq.api_key not set while provider=groq. "
                "Please configure .streamlit/secrets.toml."
            )
        logger.debug("Configuration validated successfully")

    def _make_request(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Make a chat completion request to LLM backend with retry logic

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            max_retries: Number of retries on failure
            retry_delay: Delay between retries in seconds

        Returns:
            Response dictionary from the API

        Raises:
            LLMClientError: If request fails after all retries
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False
        }

        last_error = None
        last_error_type = "connection_refused"
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"│  POST {url} (attempt {attempt + 1}/{max_retries}, "
                    f"model={payload['model']})"
                )
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                logger.info(f"│  HTTP {response.status_code} received")
                response.raise_for_status()
                data = response.json()
                logger.info(f"│  Response OK — keys: {list(data.keys())}")
                return data

            except requests.exceptions.ConnectionError as e:
                last_error = e
                last_error_type = "connection_refused"
                logger.error(
                    f"Connection refused on attempt {attempt + 1}: {e}. "
                    f"Is the LLM server running at {self.base_url}?"
                )
            except requests.exceptions.Timeout as e:
                last_error = e
                last_error_type = "timeout"
                logger.warning(f"Request timeout on attempt {attempt + 1}: {e}")
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if e.response is not None else 500
                if status_code < 500:
                    # 4xx — bad request or config; do NOT retry; log full payload
                    logger.critical(
                        f"Client error HTTP {status_code} (not retrying). "
                        f"Full request payload: {json.dumps(payload)}"
                    )
                    raise LLMError(
                        f"Client error HTTP {status_code}: {e}",
                        error_type="client_error",
                    )
                # 5xx — server crash; retry
                last_error_type = "server_error"
                logger.warning(f"Server error HTTP {status_code} on attempt {attempt + 1}: {e}")
            except Exception as e:
                last_error = e
                last_error_type = "connection_refused"
                logger.error(f"Unexpected error: {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))

        raise LLMError(
            f"Failed to connect to LLM backend after {max_retries} attempts. "
            f"Last error: {last_error}. "
            f"Please ensure your configured LLM backend is reachable at {self.base_url}",
            error_type=last_error_type,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send a chat completion request and return the response content.
        """
        logger.info(
            f"┌── chat() called — model={self.model_name}, "
            f"messages={len(messages)}, temp={temperature or self.temperature}, "
            f"max_tokens={max_tokens or self.max_tokens}"
        )
        response = self._make_request(messages, temperature, max_tokens)

        try:
            content = response["choices"][0]["message"]["content"]
            logger.info(f"└── chat() ✅ response content ({len(content)} chars)")
            return content.strip()
        except (KeyError, IndexError) as e:
            logger.error(f"└── chat() ❌ Unexpected response format: {response}")
            raise LLMClientError(f"Unexpected response format: {e}")

    def test_connection(self) -> bool:
        """
        Test connection to the configured LLM server by calling GET /models.
        Sends the configured api_key so the server does not reject with 401.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()
            logger.info("Successfully connected to configured LLM backend")
            return True
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            logger.warning(
                f"Could not connect to configured LLM backend: {e} "
                f"(HTTP {status} — check your provider API key / config)"
            )
            return False
        except Exception as e:
            logger.warning(f"Could not connect to configured LLM backend: {e}")
            return False


def get_llm_config(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get the LLM configuration for AutoGen agents

    This function returns a configuration dictionary compatible with
    AutoGen's llm_config parameter.

    Args:
        temperature: Override default temperature
        max_tokens: Override default max tokens

    Returns:
        Configuration dictionary for AutoGen agents
    """
    provider = get_secret("llm", "provider", "LLM_PROVIDER", LLMClient.DEFAULT_PROVIDER).strip().lower()

    if provider == "groq":
        base_url = get_secret("groq", "base_url", "GROQ_BASE_URL", LLMClient.DEFAULT_GROQ_BASE_URL)
        api_key = get_secret("groq", "api_key", "GROQ_API_KEY", "")
        model_name = get_secret("groq", "model_name", "GROQ_MODEL_NAME", LLMClient.DEFAULT_GROQ_MODEL)
    else:
        base_url = get_secret("jan", "base_url", "JAN_BASE_URL", LLMClient.DEFAULT_BASE_URL)
        api_key = get_secret("jan", "api_key", "JAN_API_KEY", LLMClient.DEFAULT_API_KEY)
        model_name = get_secret("jan", "model_name", "JAN_MODEL_NAME", LLMClient.DEFAULT_MODEL)
    default_temp = float(get_secret("llm", "temperature", "TEMPERATURE", "0.8"))
    default_max_tokens = int(get_secret("llm", "max_tokens", "MAX_TOKENS", "500"))

    config = {
        "config_list": [
            {
                "model": model_name,
                "base_url": base_url,
                "api_key": api_key if api_key else "not-needed",
                "api_type": "openai"
            }
        ],
        "temperature": temperature if temperature is not None else default_temp,
        "max_tokens": max_tokens if max_tokens is not None else default_max_tokens,
        "timeout": 120,
        "cache_seed": None  # Disable caching for more varied responses
    }

    return config


def validate_environment() -> tuple[bool, str]:
    """
    Validate that all required environment variables are set

    Returns:
        Tuple of (is_valid, message)
    """
    provider = get_secret("llm", "provider", "LLM_PROVIDER", LLMClient.DEFAULT_PROVIDER).strip().lower()
    if provider not in LLMClient.SUPPORTED_PROVIDERS:
        return (
            False,
            "Invalid LLM_PROVIDER. Supported values: jan, groq",
        )

    if provider == "groq":
        required_keys = [("groq", "base_url", "GROQ_BASE_URL"), ("groq", "api_key", "GROQ_API_KEY")]
        optional_keys = [("groq", "model_name", "GROQ_MODEL_NAME"), ("llm", "temperature", "TEMPERATURE"), ("llm", "max_tokens", "MAX_TOKENS")]
    else:
        required_keys = [("jan", "base_url", "JAN_BASE_URL")]
        optional_keys = [("jan", "api_key", "JAN_API_KEY"), ("jan", "model_name", "JAN_MODEL_NAME"), ("llm", "temperature", "TEMPERATURE"), ("llm", "max_tokens", "MAX_TOKENS")]

    missing = []
    for section, key, env_var in required_keys:
        if not get_secret(section, key, env_var):
            missing.append(env_var)

    if missing:
        return False, f"Missing required configuration: {', '.join(missing)}"

    # Check for optional keys and provide info
    warnings = []
    for section, key, env_var in optional_keys:
        if not get_secret(section, key, env_var):
            warnings.append(env_var)

    if warnings:
        return True, f"Using defaults for: {', '.join(warnings)}"

    return True, "All configuration values set"
