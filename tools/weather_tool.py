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


# ============================================================================
# AG2 (AutoGen 2) Tool Definitions
# ============================================================================

def get_weather_forecast(city: str, date: str = "today") -> Dict[str, Any]:
    """
    Get weather forecast for a city on a specific date.
    
    This function is designed to be used as an AG2 tool for autonomous
    weather lookups by agents. The agent decides when to call this tool
    based on user intent.
    
    Args:
        city: The name of the city to get weather for (e.g., "Minneapolis", "New York")
        date: The date for the forecast. Can be:
            - "today" for current weather
            - "tomorrow" for next day forecast  
            - A specific date string (e.g., "2026-01-22")
    
    Returns:
        A structured dictionary containing:
        - city: The queried city name
        - date: The date requested
        - summary: A brief description of weather conditions
        - temperature: Temperature details (current, high, low, feels_like)
        - wind: Wind speed and direction
        - humidity: Humidity percentage
        - conditions: Weather condition text
        - alerts: Any weather alerts (empty list if none)
        - success: Boolean indicating if the lookup succeeded
        - error: Error message if lookup failed, None otherwise
    """
    logger.info(f"🌤️ AG2 Tool: get_weather_forecast called for city='{city}', date='{date}'")
    
    result = {
        "city": city,
        "date": date,
        "summary": "",
        "temperature": {},
        "wind": {},
        "humidity": None,
        "conditions": "",
        "alerts": [],
        "success": False,
        "error": None
    }
    
    try:
        client = _get_client()
        
        # Determine which API call to make based on date
        date_lower = date.lower().strip()
        
        if date_lower == "today":
            # Get current weather
            weather_data = client.get_current_weather(city)
            current = weather_data.get("current", {})
            location = weather_data.get("location", {})
            condition = current.get("condition", {})
            
            result["city"] = location.get("name", city)
            result["date"] = location.get("localtime", "today")
            result["summary"] = f"{condition.get('text', 'Unknown')} in {result['city']}"
            result["temperature"] = {
                "current_f": current.get("temp_f"),
                "current_c": current.get("temp_c"),
                "feels_like_f": current.get("feelslike_f"),
                "feels_like_c": current.get("feelslike_c")
            }
            result["wind"] = {
                "speed_mph": current.get("wind_mph"),
                "speed_kph": current.get("wind_kph"),
                "direction": current.get("wind_dir", "")
            }
            result["humidity"] = current.get("humidity")
            result["conditions"] = condition.get("text", "Unknown")
            result["success"] = True
            
        else:
            # Get forecast for a specific day
            # For "tomorrow" or specific dates, we need to fetch forecast
            forecast_data = client.get_forecast(city, days=7)
            location = forecast_data.get("location", {})
            forecast_days = forecast_data.get("forecast", {}).get("forecastday", [])
            
            result["city"] = location.get("name", city)
            
            # Find the matching day in the forecast
            target_day = None
            
            if date_lower == "tomorrow":
                # Get the second day in the forecast (index 1)
                if len(forecast_days) > 1:
                    target_day = forecast_days[1]
            else:
                # Try to find specific date
                for day_data in forecast_days:
                    if day_data.get("date", "") == date:
                        target_day = day_data
                        break
                
                # If exact match not found, try partial match or use first available
                if target_day is None and forecast_days:
                    # Default to first forecast day if date not found
                    target_day = forecast_days[0]
            
            if target_day:
                day = target_day.get("day", {})
                condition = day.get("condition", {})
                
                result["date"] = target_day.get("date", date)
                result["summary"] = f"{condition.get('text', 'Unknown')} expected in {result['city']}"
                result["temperature"] = {
                    "high_f": day.get("maxtemp_f"),
                    "high_c": day.get("maxtemp_c"),
                    "low_f": day.get("mintemp_f"),
                    "low_c": day.get("mintemp_c"),
                    "avg_f": day.get("avgtemp_f"),
                    "avg_c": day.get("avgtemp_c")
                }
                result["wind"] = {
                    "max_speed_mph": day.get("maxwind_mph"),
                    "max_speed_kph": day.get("maxwind_kph")
                }
                result["humidity"] = day.get("avghumidity")
                result["conditions"] = condition.get("text", "Unknown")
                result["alerts"] = []
                
                # Check for rain/snow chances
                rain_chance = day.get("daily_chance_of_rain", 0)
                snow_chance = day.get("daily_chance_of_snow", 0)
                if rain_chance > 30:
                    result["alerts"].append(f"{rain_chance}% chance of rain")
                if snow_chance > 30:
                    result["alerts"].append(f"{snow_chance}% chance of snow")
                
                result["success"] = True
            else:
                result["error"] = f"No forecast data available for {date}"
                
        logger.info(f"🌤️ AG2 Tool: Weather lookup successful for {result['city']}")
        
    except WeatherClientError as e:
        error_msg = str(e)
        logger.warning(f"🌤️ AG2 Tool: Weather lookup failed - {error_msg}")
        result["error"] = error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"🌤️ AG2 Tool: {error_msg}")
        result["error"] = error_msg
    
    return result


# OpenAI-style function schema for AG2 tool registration
WEATHER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather_forecast",
        "description": (
            "Get weather forecast information for a specific city and date. "
            "Use this tool whenever the user asks about weather, temperature, "
            "forecast, storms, climate conditions, or any weather-related questions. "
            "The tool returns structured weather data including temperature, wind, "
            "humidity, and any weather alerts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        "The name of the city to get weather for. "
                        "Examples: 'Minneapolis', 'New York', 'London', 'Tokyo'"
                    )
                },
                "date": {
                    "type": "string",
                    "description": (
                        "The date for the weather forecast. Can be 'today', "
                        "'tomorrow', or a specific date in YYYY-MM-DD format "
                        "(e.g., '2026-01-22'). Defaults to 'today' if not specified."
                    )
                }
            },
            "required": ["city"]
        }
    }
}
