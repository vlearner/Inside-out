"""
Tests for Weather Client and Weather Tool
Uses mocking to test without actual API calls
"""
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
from unittest.mock import patch, MagicMock
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.weather_client import WeatherClient, WeatherClientError, validate_weather_config
from tools.weather_tool import (
    get_weather,
    get_forecast,
    format_weather_response,
    format_forecast_response,
    is_weather_query,
    extract_location_from_message
)


# ============================================================================
# Test Data
# ============================================================================

MOCK_CURRENT_WEATHER = {
    "location": {
        "name": "New York",
        "region": "New York",
        "country": "USA",
        "lat": 40.71,
        "lon": -74.01,
        "tz_id": "America/New_York",
        "localtime": "2024-01-15 14:30"
    },
    "current": {
        "temp_c": 5.0,
        "temp_f": 41.0,
        "condition": {
            "text": "Partly cloudy",
            "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"
        },
        "humidity": 65,
        "wind_mph": 10.5,
        "wind_kph": 16.9,
        "feelslike_f": 36.5,
        "feelslike_c": 2.5
    }
}

MOCK_FORECAST = {
    "location": {
        "name": "London",
        "region": "City of London",
        "country": "United Kingdom"
    },
    "current": MOCK_CURRENT_WEATHER["current"],
    "forecast": {
        "forecastday": [
            {
                "date": "2024-01-15",
                "day": {
                    "maxtemp_f": 45.0,
                    "mintemp_f": 35.0,
                    "condition": {"text": "Cloudy"},
                    "daily_chance_of_rain": 20
                }
            },
            {
                "date": "2024-01-16",
                "day": {
                    "maxtemp_f": 48.0,
                    "mintemp_f": 38.0,
                    "condition": {"text": "Sunny"},
                    "daily_chance_of_rain": 5
                }
            },
            {
                "date": "2024-01-17",
                "day": {
                    "maxtemp_f": 50.0,
                    "mintemp_f": 40.0,
                    "condition": {"text": "Rainy"},
                    "daily_chance_of_rain": 80
                }
            }
        ]
    }
}


# ============================================================================
# WeatherClient Tests
# ============================================================================

class TestWeatherClient:
    """Tests for WeatherClient class"""

    def test_client_initialization_without_api_key(self):
        """Test that client initializes with warning when no API key"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": ""}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                assert client.api_key == ""

    def test_client_initialization_with_api_key(self):
        """Test that client initializes correctly with API key"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test_key"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                assert client.api_key == "test_key"

    def test_sanitize_location_valid(self):
        """Test location sanitization with valid inputs"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                
                assert client._sanitize_location("New York") == "New York"
                assert client._sanitize_location("London, UK") == "London, UK"
                assert client._sanitize_location("  Paris  ") == "Paris"
                assert client._sanitize_location("90210") == "90210"

    def test_sanitize_location_removes_dangerous_chars(self):
        """Test that dangerous characters are removed"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                
                # Script injection attempt should be sanitized
                result = client._sanitize_location("<script>alert('xss')</script>")
                assert "<" not in result
                assert ">" not in result

    def test_sanitize_location_empty_raises_error(self):
        """Test that empty location raises error"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                
                with pytest.raises(WeatherClientError):
                    client._sanitize_location("")
                
                with pytest.raises(WeatherClientError):
                    client._sanitize_location("   ")

    @patch('requests.get')
    def test_get_current_weather_success(self, mock_get):
        """Test successful current weather retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CURRENT_WEATHER
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"WEATHER_API_KEY": "test_key"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                result = client.get_current_weather("New York")
                
                assert result == MOCK_CURRENT_WEATHER
                assert "location" in result
                assert "current" in result

    @patch('requests.get')
    def test_get_current_weather_no_api_key(self, mock_get):
        """Test that request fails without API key"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": ""}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                
                with pytest.raises(WeatherClientError) as exc_info:
                    client.get_current_weather("New York")
                
                assert "WEATHER_API_KEY" in str(exc_info.value)

    @patch('requests.get')
    def test_get_forecast_success(self, mock_get):
        """Test successful forecast retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_FORECAST
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"WEATHER_API_KEY": "test_key"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                result = client.get_forecast("London", days=3)
                
                assert "forecast" in result
                assert len(result["forecast"]["forecastday"]) == 3

    def test_get_forecast_invalid_days(self):
        """Test that invalid days parameter raises error"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test_key"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                client = WeatherClient()
                
                with pytest.raises(WeatherClientError):
                    client.get_forecast("London", days=0)
                
                with pytest.raises(WeatherClientError):
                    client.get_forecast("London", days=15)


# ============================================================================
# Weather Tool Tests
# ============================================================================

class TestWeatherTool:
    """Tests for weather tool functions"""

    def test_format_weather_response(self):
        """Test weather response formatting"""
        formatted = format_weather_response(MOCK_CURRENT_WEATHER)
        
        assert "New York" in formatted
        assert "41" in formatted  # temp_f
        assert "Partly cloudy" in formatted
        assert "65" in formatted  # humidity

    def test_format_forecast_response(self):
        """Test forecast response formatting"""
        formatted = format_forecast_response(MOCK_FORECAST, days=3)
        
        assert "London" in formatted
        assert "2024-01-15" in formatted
        assert "Cloudy" in formatted
        assert "20%" in formatted  # chance of rain

    def test_is_weather_query_positive(self):
        """Test weather query detection with weather-related messages"""
        assert is_weather_query("What's the weather in New York?") is True
        assert is_weather_query("Is it going to rain tomorrow?") is True
        assert is_weather_query("How hot is it outside?") is True
        assert is_weather_query("What's the temperature?") is True
        assert is_weather_query("Will it be sunny today?") is True

    def test_is_weather_query_negative(self):
        """Test weather query detection with non-weather messages"""
        assert is_weather_query("What's your favorite color?") is False
        assert is_weather_query("Tell me a joke") is False
        assert is_weather_query("How do I cook pasta?") is False

    def test_extract_location_from_message(self):
        """Test location extraction from messages"""
        assert extract_location_from_message("What's the weather in New York?") == "New York"
        assert extract_location_from_message("Weather in London, UK") == "London, UK"
        assert extract_location_from_message("How's the weather in Paris?") == "Paris"

    def test_extract_location_no_match(self):
        """Test location extraction when no location is specified"""
        assert extract_location_from_message("What's the weather?") is None
        assert extract_location_from_message("Is it cold?") is None

    @patch('tools.weather_tool._get_client')
    def test_get_weather_success(self, mock_get_client):
        """Test get_weather function with mocked client"""
        mock_client = MagicMock()
        mock_client.get_current_weather.return_value = MOCK_CURRENT_WEATHER
        mock_get_client.return_value = mock_client

        result = get_weather("New York")
        
        assert "New York" in result
        assert "41" in result  # temp_f

    @patch('tools.weather_tool._get_client')
    def test_get_weather_error(self, mock_get_client):
        """Test get_weather function handles errors gracefully"""
        mock_client = MagicMock()
        mock_client.get_current_weather.side_effect = WeatherClientError("API Error")
        mock_get_client.return_value = mock_client

        result = get_weather("InvalidLocation")
        
        assert "Could not get weather" in result

    @patch('tools.weather_tool._get_client')
    def test_get_forecast_success(self, mock_get_client):
        """Test get_forecast function with mocked client"""
        mock_client = MagicMock()
        mock_client.get_forecast.return_value = MOCK_FORECAST
        mock_get_client.return_value = mock_client

        result = get_forecast("London", days=3)
        
        assert "London" in result
        assert "forecast" in result.lower()


# ============================================================================
# Configuration Tests
# ============================================================================

class TestWeatherConfig:
    """Tests for weather configuration validation"""

    def test_validate_config_with_key(self):
        """Test configuration validation with API key set"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": "test_key"}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                is_valid, message = validate_weather_config()
                assert is_valid is True
                assert "configured" in message.lower()

    def test_validate_config_without_key(self):
        """Test configuration validation without API key"""
        with patch.dict(os.environ, {"WEATHER_API_KEY": ""}, clear=False):
            with patch('utils.weather_client.load_dotenv'):
                is_valid, message = validate_weather_config()
                assert is_valid is False
                assert "not set" in message.lower()


# ============================================================================
# AG2 Weather Agent Tests
# ============================================================================

from tools.weather_tool import get_weather_forecast, WEATHER_TOOL_SCHEMA


class TestWeatherForecastTool:
    """Tests for the AG2-compatible get_weather_forecast tool"""

    @patch('tools.weather_tool._get_client')
    def test_get_weather_forecast_today(self, mock_get_client):
        """Test get_weather_forecast for today's weather"""
        mock_client = MagicMock()
        mock_client.get_current_weather.return_value = MOCK_CURRENT_WEATHER
        mock_get_client.return_value = mock_client

        result = get_weather_forecast(city="New York", date="today")
        
        assert result["success"] is True
        assert result["city"] == "New York"
        assert result["error"] is None
        assert "temperature" in result
        assert result["temperature"]["current_f"] == 41.0
        assert result["conditions"] == "Partly cloudy"

    @patch('tools.weather_tool._get_client')
    def test_get_weather_forecast_tomorrow(self, mock_get_client):
        """Test get_weather_forecast for tomorrow's weather"""
        mock_client = MagicMock()
        mock_client.get_forecast.return_value = MOCK_FORECAST
        mock_get_client.return_value = mock_client

        result = get_weather_forecast(city="London", date="tomorrow")
        
        assert result["success"] is True
        assert result["error"] is None
        assert "temperature" in result
        # Tomorrow is the second day in forecast
        assert result["temperature"]["high_f"] == 48.0

    @patch('tools.weather_tool._get_client')
    def test_get_weather_forecast_error_handling(self, mock_get_client):
        """Test that errors are handled gracefully"""
        mock_client = MagicMock()
        mock_client.get_current_weather.side_effect = WeatherClientError("API Error")
        mock_get_client.return_value = mock_client

        result = get_weather_forecast(city="InvalidCity", date="today")
        
        assert result["success"] is False
        assert result["error"] is not None
        assert "API Error" in result["error"]

    def test_weather_tool_schema_structure(self):
        """Test that the tool schema has correct structure for AG2"""
        assert WEATHER_TOOL_SCHEMA["type"] == "function"
        assert "function" in WEATHER_TOOL_SCHEMA
        
        func_schema = WEATHER_TOOL_SCHEMA["function"]
        assert func_schema["name"] == "get_weather_forecast"
        assert "description" in func_schema
        assert "parameters" in func_schema
        
        params = func_schema["parameters"]
        assert params["type"] == "object"
        assert "city" in params["properties"]
        assert "date" in params["properties"]
        assert "city" in params["required"]

    def test_weather_tool_schema_descriptions(self):
        """Test that schema has helpful descriptions for LLM"""
        func_schema = WEATHER_TOOL_SCHEMA["function"]
        
        # Description should mention key weather terms
        description = func_schema["description"].lower()
        assert "weather" in description
        assert "forecast" in description
        assert "temperature" in description
        
        # City parameter should have description
        city_prop = func_schema["parameters"]["properties"]["city"]
        assert "description" in city_prop
        assert "city" in city_prop["description"].lower()


class TestWeatherAgentImports:
    """Test that weather agent module can be imported"""

    def test_weather_agent_imports(self):
        """Test that weather agent components can be imported"""
        try:
            from agents.weather_agent import (
                WeatherAgentSystem,
                create_weather_agent,
                create_weather_user_proxy,
                WEATHER_AGENT_SYSTEM_MESSAGE
            )
            assert WeatherAgentSystem is not None
            assert create_weather_agent is not None
            assert create_weather_user_proxy is not None
            assert WEATHER_AGENT_SYSTEM_MESSAGE is not None
        except ImportError as e:
            pytest.fail(f"Failed to import weather agent: {e}")

    def test_weather_agent_system_message_content(self):
        """Test that system message has proper instructions"""
        from agents.weather_agent import WEATHER_AGENT_SYSTEM_MESSAGE
        
        msg_lower = WEATHER_AGENT_SYSTEM_MESSAGE.lower()
        
        # Should instruct to use tool for weather queries
        assert "get_weather_forecast" in msg_lower
        
        # Should instruct not to hallucinate
        assert "never" in msg_lower or "must" in msg_lower
        
        # Should mention weather-related terms
        assert "weather" in msg_lower
        assert "temperature" in msg_lower


# ============================================================================
# Run Tests
# ============================================================================

def run_weather_tests():
    """Run all weather tests"""
    print("=" * 70)
    print("RUNNING WEATHER API TESTS")
    print("=" * 70)

    # Test weather query detection
    print("\nTesting is_weather_query...")
    assert is_weather_query("What's the weather?") is True
    assert is_weather_query("Tell me a joke") is False
    print("✅ Weather query detection works")

    # Test location extraction
    print("\nTesting extract_location_from_message...")
    assert extract_location_from_message("Weather in NYC") == "NYC"
    print("✅ Location extraction works")

    # Test formatting
    print("\nTesting format_weather_response...")
    formatted = format_weather_response(MOCK_CURRENT_WEATHER)
    assert "New York" in formatted
    print("✅ Weather formatting works")

    print("\nTesting format_forecast_response...")
    formatted = format_forecast_response(MOCK_FORECAST)
    assert "London" in formatted
    print("✅ Forecast formatting works")

    print("\n" + "=" * 70)
    print("✅ ALL WEATHER TESTS PASSED!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    # Run quick tests without pytest
    success = run_weather_tests()
    sys.exit(0 if success else 1)
