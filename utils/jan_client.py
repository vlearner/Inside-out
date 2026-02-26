"""
Jan.ai API Client Wrapper
Provides a reusable client for connecting to Jan.ai local LLM server
"""
import os
import logging
import time
import json
from typing import Dict, Optional, Any, List
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JAN-CLIENT")


class JanClientError(Exception):
    """Custom exception for Jan.ai client errors"""
    pass


class LLMError(JanClientError):
    """Structured LLM error with a classified error_type.

    Extends JanClientError for backwards compatibility — existing code that
    catches JanClientError will still work unchanged.

    error_type values:
      - ``"connection_refused"`` — Jan AI server is not running.
      - ``"timeout"``            — Jan AI is running but too slow / overloaded.
      - ``"server_error"``       — 5xx HTTP response from Jan AI.
      - ``"client_error"``       — 4xx HTTP response (bad request / config).
    """

    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type  # one of the four values above

    def __str__(self) -> str:
        return f"[{self.error_type}] {super().__str__()}"


class JanClient:
    """
    Jan.ai API Client for making LLM requests

    This client wraps the Jan.ai local server API and provides
    methods for chat completions with retry logic and error handling.
    """

    # Default fallback values — override via env vars or constructor kwargs
    # NOTE: DEFAULT_API_KEY is intentionally empty.
    #       Set JAN_API_KEY in your .env file (see .env.example).
    DEFAULT_BASE_URL = "http://127.0.0.1:1337/v1"
    DEFAULT_API_KEY = ""          # no key hardcoded — must come from .env
    DEFAULT_MODEL = "Meta-Llama-3_1-8B-Instruct_Q4_K_M"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize the Jan.ai client.

        Priority order for each value:
          1. Explicit constructor argument
          2. Environment variable  (JAN_BASE_URL / JAN_API_KEY / JAN_MODEL_NAME)
          3. Class-level default constant

        This means you can override any value in tests or scripts without
        touching environment variables:

            client = JanClient(api_key="my-key", model_name="mistral-7b")
        """
        load_dotenv()

        self.base_url = (
            base_url
            if base_url is not None
            else os.getenv("JAN_BASE_URL", self.DEFAULT_BASE_URL)
        )
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("JAN_API_KEY", self.DEFAULT_API_KEY)
        )
        self.model_name = (
            model_name
            if model_name is not None
            else os.getenv("JAN_MODEL_NAME", self.DEFAULT_MODEL)
        )
        self.temperature = float(os.getenv("TEMPERATURE", "0.8"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "500"))

        self._validate_config()
        logger.info(f"JanClient initialized with base URL: {self.base_url}")

    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        if not self.base_url:
            raise JanClientError(
                "JAN_BASE_URL not set. Please configure your .env file."
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
        Make a chat completion request to Jan.ai with retry logic

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            max_retries: Number of retries on failure
            retry_delay: Delay between retries in seconds

        Returns:
            Response dictionary from the API

        Raises:
            JanClientError: If request fails after all retries
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
                    f"Is Jan.ai running at {self.base_url}?"
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
            f"Failed to connect to Jan.ai after {max_retries} attempts. "
            f"Last error: {last_error}. "
            f"Please ensure Jan.ai is running at {self.base_url}",
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
            raise JanClientError(f"Unexpected response format: {e}")

    def test_connection(self) -> bool:
        """
        Test the connection to Jan.ai server by calling GET /models.
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
            logger.info("Successfully connected to Jan.ai")
            return True
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            logger.warning(
                f"Could not connect to Jan.ai: {e} "
                f"(HTTP {status} — check your JAN_API_KEY / api_key)"
            )
            return False
        except Exception as e:
            logger.warning(f"Could not connect to Jan.ai: {e}")
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
    load_dotenv()

    base_url = os.getenv("JAN_BASE_URL", "http://localhost:1337/v1")
    api_key = os.getenv("JAN_API_KEY", "")
    model_name = os.getenv("JAN_MODEL_NAME", "Meta-Llama-3_1-8B-Instruct_Q4_K_M")
    default_temp = float(os.getenv("TEMPERATURE", "0.8"))
    default_max_tokens = int(os.getenv("MAX_TOKENS", "500"))

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
    load_dotenv()

    required_vars = ["JAN_BASE_URL"]
    optional_vars = ["JAN_API_KEY", "JAN_MODEL_NAME", "TEMPERATURE", "MAX_TOKENS"]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        return False, f"Missing required environment variables: {', '.join(missing)}"

    # Check for optional variables and provide info
    warnings = []
    for var in optional_vars:
        if not os.getenv(var):
            warnings.append(var)

    if warnings:
        return True, f"Using defaults for: {', '.join(warnings)}"

    return True, "All environment variables configured"

