"""
Weather Tool for Agents
Provides agent-compatible functions for weather lookups
"""
import logging
import re
from typing import Dict, Any, Optional

from utils.weather_client import WeatherClient, WeatherClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WEATHER-TOOL")

# Singleton client instance
_weather_client: Optional[WeatherClient] = None


def _get_client() -> WeatherClient:
    """Get or create the weather client singleton"""
    global _weather_client
    if _weather_client is None:
        _weather_client = WeatherClient()
    return _weather_client


def format_weather_response(weather_data: Dict[str, Any]) -> str:
    """
    Format weather data into a human-readable string

    Args:
        weather_data: Raw weather data from the API

    Returns:
        Formatted weather string for agent use
    """
    try:
        location = weather_data.get("location", {})
        current = weather_data.get("current", {})
        condition = current.get("condition", {})

        location_name = location.get("name", "Unknown")
        region = location.get("region", "")
        country = location.get("country", "")

        # Build location string
        location_parts = [location_name]
        if region and region != location_name:
            location_parts.append(region)
        if country:
            location_parts.append(country)
        location_str = ", ".join(location_parts)

        temp_f = current.get("temp_f", "N/A")
        temp_c = current.get("temp_c", "N/A")
        condition_text = condition.get("text", "Unknown")
        humidity = current.get("humidity", "N/A")
        wind_mph = current.get("wind_mph", "N/A")
        feels_like_f = current.get("feelslike_f", "N/A")

        formatted = (
            f"Weather in {location_str}:\n"
            f"• Condition: {condition_text}\n"
            f"• Temperature: {temp_f}°F ({temp_c}°C)\n"
            f"• Feels like: {feels_like_f}°F\n"
            f"• Humidity: {humidity}%\n"
            f"• Wind: {wind_mph} mph"
        )

        logger.debug(f"Formatted weather response for {location_name}")
        return formatted

    except Exception as e:
        logger.error(f"Error formatting weather data: {e}")
        return "Weather data available but could not be formatted."


def format_forecast_response(
    forecast_data: Dict[str, Any],
    days: int = 3
) -> str:
    """
    Format forecast data into a human-readable string

    Args:
        forecast_data: Raw forecast data from the API
        days: Number of days to include in the response

    Returns:
        Formatted forecast string for agent use
    """
    try:
        location = forecast_data.get("location", {})
        forecast = forecast_data.get("forecast", {})
        forecast_days = forecast.get("forecastday", [])

        location_name = location.get("name", "Unknown")
        country = location.get("country", "")

        lines = [f"Weather forecast for {location_name}, {country}:"]

        for day_data in forecast_days[:days]:
            date = day_data.get("date", "Unknown date")
            day = day_data.get("day", {})
            condition = day.get("condition", {})

            max_temp_f = day.get("maxtemp_f", "N/A")
            min_temp_f = day.get("mintemp_f", "N/A")
            condition_text = condition.get("text", "Unknown")
            chance_of_rain = day.get("daily_chance_of_rain", 0)

            lines.append(
                f"\n📅 {date}:\n"
                f"  • {condition_text}\n"
                f"  • High: {max_temp_f}°F, Low: {min_temp_f}°F\n"
                f"  • Chance of rain: {chance_of_rain}%"
            )

        logger.debug(f"Formatted forecast response for {location_name}")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting forecast data: {e}")
        return "Forecast data available but could not be formatted."


def get_weather(location: str) -> str:
    """
    Get current weather for a location - main function for agents.

    Args:
        location: City name, coordinates, or postal code

    Returns:
        Formatted weather string on success, or error message on failure
    """
    logger.info(f"┌── get_weather(\"{location}\") called")

    try:
        logger.info(f"│  Initializing weather client...")
        client = _get_client()
        logger.info(f"│  Client ready — API key configured: {'YES' if client.api_key else 'NO'}")

        logger.info(f"│  Calling WeatherAPI for \"{location}\"...")
        weather_data = client.get_current_weather(location)
        logger.info(f"│  Raw API response received (keys: {list(weather_data.keys())})")

        formatted = format_weather_response(weather_data)
        logger.info(f"│  Formatted response:\n│    {formatted.replace(chr(10), chr(10) + '│    ')}")
        logger.info(f"└── get_weather(\"{location}\") ✅ SUCCESS")
        return formatted

    except WeatherClientError as e:
        error_msg = f"Could not get weather for '{location}': {str(e)}"
        logger.warning(f"│  ❌ WeatherClientError: {e}")
        logger.warning(f"└── get_weather(\"{location}\") FAILED")
        return error_msg

    except Exception as e:
        logger.error(f"│  ❌ Unexpected error: {type(e).__name__}: {e}")
        logger.error(f"└── get_weather(\"{location}\") FAILED")
        return "Sorry, I couldn't retrieve the weather information right now."


def get_forecast(location: str, days: int = 3) -> str:
    """
    Get weather forecast for a location - function for agents

    Args:
        location: City name, coordinates, or postal code
        days: Number of days to forecast (1-14, default 3)

    Returns:
        Formatted forecast string on success, or error message on failure
    """
    logger.info(f"Agent requesting {days}-day forecast for: {location}")

    try:
        client = _get_client()
        forecast_data = client.get_forecast(location, days)
        formatted = format_forecast_response(forecast_data, days)
        logger.info(f"Successfully retrieved forecast for: {location}")
        return formatted

    except WeatherClientError as e:
        error_msg = f"Could not get forecast for '{location}': {str(e)}"
        logger.warning(error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Unexpected error getting forecast: {str(e)}"
        logger.error(error_msg)
        return "Sorry, I couldn't retrieve the forecast information right now."


def is_weather_query(message: str) -> bool:
    """
    Determine if a message is asking about weather

    Args:
        message: User message to analyze

    Returns:
        True if the message appears to be weather-related
    """
    weather_keywords = [
        "weather", "temperature", "forecast", "rain", "sunny",
        "cloudy", "snow", "storm", "wind", "humid", "cold", "hot",
        "warm", "freezing", "celsius", "fahrenheit", "degrees",
        "outside", "tomorrow weather", "today weather"
    ]

    message_lower = message.lower()

    for keyword in weather_keywords:
        if keyword in message_lower:
            logger.info(f"is_weather_query → TRUE (matched keyword \"{keyword}\" in \"{message_lower[:60]}\")")
            return True

    logger.info(f"is_weather_query → FALSE (no weather keywords in \"{message_lower[:60]}\")")
    return False


def extract_location_from_message(message: str) -> Optional[str]:
    """
    Try to extract a location from a weather-related message.

    Handles patterns like:
      "what is current weather at Minneapolis MN?"
      "weather in London, UK"
      "what's the temperature in Paris?"

    Args:
        message: User message that may contain a location

    Returns:
        Extracted location string, or None if not found
    """
    logger.info(f"extract_location — input: \"{message}\"")

    # Ordered from most-specific to least-specific so the first match wins
    patterns = [
        "current weather at ",
        "current weather in ",
        "current weather for ",
        "what is the weather at ",
        "what is the weather in ",
        "what's the weather at ",
        "what's the weather in ",
        "how's the weather in ",
        "how's the weather at ",
        "weather at ",
        "weather in ",
        "weather for ",
        "forecast for ",
        "forecast in ",
        "temperature at ",
        "temperature in ",
    ]

    message_lower = message.lower()

    for pattern in patterns:
        if pattern in message_lower:
            start_idx = message_lower.index(pattern) + len(pattern)
            location = message[start_idx:].strip()

            # Remove trailing punctuation
            location = location.rstrip("?!.,")

            # Take only the first 4 words (location names are usually short)
            words = location.split()[:4]
            location = " ".join(words)

            if location:
                logger.info(f"extract_location — MATCHED pattern \"{pattern}\" → location: \"{location}\"")
                return location

    # --- Fallback: look for a capitalised word/phrase after a weather keyword ---
    fallback_match = re.search(
        r'\b(?:weather|temperature|forecast|rain|snow|sunny|cold|hot|warm)\b'
        r'.{0,20}?\b([A-Z][a-zA-Z]+(?:\s+[A-Z]{2})?)',
        message,
    )
    if fallback_match:
        location = fallback_match.group(1).strip()
        logger.info(f"extract_location — FALLBACK regex matched → location: \"{location}\"")
        return location

    logger.warning(f"extract_location — NO location found in: \"{message}\"")
    return None
