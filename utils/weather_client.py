"""
Weather API Client Wrapper
Provides a reusable client for connecting to WeatherAPI.com
https://www.weatherapi.com/docs/
"""
import os
import logging
import re
import time
from typing import Dict, Optional, Any
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherClientError(Exception):
    """Custom exception for Weather API client errors"""
    pass


class WeatherClient:
    """
    Weather API Client for fetching weather data

    This client wraps the WeatherAPI.com API and provides
    methods for current weather and forecasts with retry logic
    and error handling.
    """

    BASE_URL = "http://api.weatherapi.com/v1"

    def __init__(self):
        """Initialize the Weather client with configuration from environment"""
        load_dotenv()

        self.api_key = os.getenv("WEATHER_API_KEY", "")
        self.timeout = int(os.getenv("WEATHER_API_TIMEOUT", "10"))
        self.max_retries = int(os.getenv("WEATHER_API_MAX_RETRIES", "3"))

        self._validate_config()
        logger.info("WeatherClient initialized")

    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        if not self.api_key:
            logger.warning(
                "WEATHER_API_KEY not set. Weather lookups will fail. "
                "Please add your API key to the .env file."
            )

    def _sanitize_location(self, location: str) -> str:
        """
        Sanitize location input to prevent injection attacks

        Args:
            location: Raw location string from user

        Returns:
            Sanitized location string

        Raises:
            WeatherClientError: If location is invalid
        """
        if not location or not isinstance(location, str):
            raise WeatherClientError("Location must be a non-empty string")

        # Strip whitespace and limit length
        sanitized = location.strip()[:100]

        # Remove potentially dangerous characters, allow only safe ones
        # Allow: letters, numbers, spaces, commas, periods, hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9\s,.\-]', '', sanitized)

        if not sanitized:
            raise WeatherClientError("Location contains no valid characters")

        logger.debug(f"Sanitized location: '{location}' -> '{sanitized}'")
        return sanitized

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Make a request to WeatherAPI.com with retry logic

        Args:
            endpoint: API endpoint (e.g., 'current.json', 'forecast.json')
            params: Query parameters
            retry_delay: Delay between retries in seconds

        Returns:
            Response dictionary from the API

        Raises:
            WeatherClientError: If request fails after all retries
        """
        if not self.api_key:
            raise WeatherClientError(
                "WEATHER_API_KEY not configured. "
                "Please add your API key to the .env file."
            )

        url = f"{self.BASE_URL}/{endpoint}"
        params["key"] = self.api_key

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Weather API request to {endpoint}, "
                    f"attempt {attempt + 1}/{self.max_retries}"
                )
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )

                # Check for API-level errors
                if response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", "Bad request"
                    )
                    raise WeatherClientError(f"Invalid request: {error_msg}")

                if response.status_code == 401:
                    raise WeatherClientError(
                        "Invalid API key. Please check your WEATHER_API_KEY."
                    )

                if response.status_code == 403:
                    raise WeatherClientError(
                        "API key quota exceeded or access denied."
                    )

                response.raise_for_status()
                logger.debug("Weather API request successful")
                return response.json()

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(
                    f"Connection error on attempt {attempt + 1}: {e}"
                )
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    f"Request timeout on attempt {attempt + 1}: {e}"
                )
            except requests.exceptions.HTTPError as e:
                last_error = e
                logger.error(f"HTTP error: {e}")
                # Don't retry on client errors (4xx)
                if response.status_code < 500:
                    raise WeatherClientError(f"API error: {e}")
            except WeatherClientError:
                # Re-raise our custom errors immediately
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}")

            if attempt < self.max_retries - 1:
                sleep_time = retry_delay * (attempt + 1)
                logger.debug(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        raise WeatherClientError(
            f"Failed to connect to Weather API after {self.max_retries} "
            f"attempts. Last error: {last_error}"
        )

    def get_current_weather(self, location: str) -> Dict[str, Any]:
        """
        Get current weather for a location

        Args:
            location: City name, coordinates, or postal code
                Examples: "New York", "48.8567,2.3508", "10001"

        Returns:
            Dictionary containing location and current weather data:
            {
                "location": {...},
                "current": {
                    "temp_c": float,
                    "temp_f": float,
                    "condition": {"text": str, "icon": str},
                    "humidity": int,
                    "wind_mph": float,
                    "wind_kph": float,
                    ...
                }
            }

        Raises:
            WeatherClientError: If request fails or location is invalid
        """
        sanitized_location = self._sanitize_location(location)
        logger.info(f"Fetching current weather for: {sanitized_location}")

        return self._make_request(
            endpoint="current.json",
            params={"q": sanitized_location, "aqi": "no"}
        )

    def get_forecast(
        self,
        location: str,
        days: int = 3
    ) -> Dict[str, Any]:
        """
        Get weather forecast for a location

        Args:
            location: City name, coordinates, or postal code
            days: Number of days to forecast (1-14, default 3)

        Returns:
            Dictionary containing location, current, and forecast data

        Raises:
            WeatherClientError: If request fails or parameters are invalid
        """
        sanitized_location = self._sanitize_location(location)

        # Validate days parameter
        if not isinstance(days, int) or days < 1 or days > 14:
            raise WeatherClientError("Days must be an integer between 1 and 14")

        logger.info(
            f"Fetching {days}-day forecast for: {sanitized_location}"
        )

        return self._make_request(
            endpoint="forecast.json",
            params={"q": sanitized_location, "days": days, "aqi": "no"}
        )

    def test_connection(self) -> bool:
        """
        Test the connection to Weather API

        Returns:
            True if connection is successful, False otherwise
        """
        if not self.api_key:
            logger.warning("Cannot test connection: API key not configured")
            return False

        try:
            # Use a known location to test
            self.get_current_weather("London")
            logger.info("Successfully connected to Weather API")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to Weather API: {e}")
            return False


def get_weather_client() -> WeatherClient:
    """
    Factory function to get a WeatherClient instance

    Returns:
        Configured WeatherClient instance
    """
    return WeatherClient()


def validate_weather_config() -> tuple[bool, str]:
    """
    Validate that weather API configuration is present

    Returns:
        Tuple of (is_valid, message)
    """
    load_dotenv()

    api_key = os.getenv("WEATHER_API_KEY", "")

    if not api_key:
        return False, "WEATHER_API_KEY not set in environment"

    return True, "Weather API configured"
