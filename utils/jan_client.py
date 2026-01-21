"""
Jan.ai API Client Wrapper
Provides a reusable client for connecting to Jan.ai local LLM server
"""
import os
import logging
import time
from typing import Dict, Optional, Any, List
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JanClientError(Exception):
    """Custom exception for Jan.ai client errors"""
    pass


class JanClient:
    """
    Jan.ai API Client for making LLM requests

    This client wraps the Jan.ai local server API and provides
    methods for chat completions with retry logic and error handling.
    """

    def __init__(self):
        """Initialize the Jan.ai client with configuration from environment"""
        load_dotenv()

        self.base_url = os.getenv("JAN_BASE_URL", "http://localhost:1337/v1")
        self.api_key = os.getenv("JAN_API_KEY", "")
        self.model_name = os.getenv("JAN_MODEL_NAME", "llama-3.1-8b-instruct")
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
        for attempt in range(max_retries):
            try:
                logger.debug(f"Making request to {url}, attempt {attempt + 1}/{max_retries}")
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(
                    f"Connection error on attempt {attempt + 1}: {e}. "
                    f"Is Jan.ai running at {self.base_url}?"
                )
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Request timeout on attempt {attempt + 1}: {e}")
            except requests.exceptions.HTTPError as e:
                last_error = e
                logger.error(f"HTTP error: {e}")
                # Don't retry on client errors (4xx)
                if response.status_code < 500:
                    raise JanClientError(f"API error: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))

        raise JanClientError(
            f"Failed to connect to Jan.ai after {max_retries} attempts. "
            f"Last error: {last_error}. "
            f"Please ensure Jan.ai is running at {self.base_url}"
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send a chat completion request and return the response content

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            The assistant's response content as a string
        """
        response = self._make_request(messages, temperature, max_tokens)

        try:
            content = response["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected response format: {response}")
            raise JanClientError(f"Unexpected response format: {e}")

    def test_connection(self) -> bool:
        """
        Test the connection to Jan.ai server

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/models",
                timeout=5
            )
            response.raise_for_status()
            logger.info("Successfully connected to Jan.ai")
            return True
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
    model_name = os.getenv("JAN_MODEL_NAME", "llama-3.1-8b-instruct")
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

