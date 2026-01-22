"""
Weather Tool for Agents
Provides agent-compatible functions for weather lookups
"""
import logging
from typing import Dict, Any, Optional, Union

from utils.weather_client import WeatherClient, WeatherClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    Get current weather for a location - main function for agents

    This is the primary function that agents should call when
    they need weather information.

    Args:
        location: City name, coordinates, or postal code
            Examples: "New York", "London, UK", "90210"

    Returns:
        Formatted weather string on success, or error message on failure
    """
    logger.info(f"Agent requesting weather for: {location}")

    try:
        client = _get_client()
        weather_data = client.get_current_weather(location)
        formatted = format_weather_response(weather_data)
        logger.info(f"Successfully retrieved weather for: {location}")
        return formatted

    except WeatherClientError as e:
        error_msg = f"Could not get weather for '{location}': {str(e)}"
        logger.warning(error_msg)
        return error_msg

    except Exception as e:
        error_msg = f"Unexpected error getting weather: {str(e)}"
        logger.error(error_msg)
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
            logger.debug(f"Weather query detected: keyword '{keyword}' found")
            return True

    return False


def extract_location_from_message(message: str) -> Optional[str]:
    """
    Try to extract a location from a weather-related message

    Args:
        message: User message that may contain a location

    Returns:
        Extracted location or None if not found
    """
    # Common patterns for weather questions
    patterns = [
        "weather in ",
        "weather for ",
        "weather at ",
        "forecast for ",
        "forecast in ",
        "temperature in ",
        "how's the weather in ",
        "what's the weather in ",
        "what is the weather in ",
    ]

    message_lower = message.lower()

    for pattern in patterns:
        if pattern in message_lower:
            # Extract text after the pattern
            start_idx = message_lower.index(pattern) + len(pattern)
            location = message[start_idx:].strip()

            # Clean up the location - remove trailing punctuation
            location = location.rstrip("?!.,")

            # Take only the first few words (location names are usually short)
            words = location.split()[:4]
            location = " ".join(words)

            if location:
                logger.debug(f"Extracted location: '{location}'")
                return location

    return None
