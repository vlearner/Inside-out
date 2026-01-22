"""
Tools package for Inside Out Multi-Agent System
Provides external tools that agents can use during conversations
"""
from .weather_tool import (
    get_weather,
    get_forecast,
    is_weather_query,
    extract_location_from_message,
    get_weather_forecast,
    WEATHER_TOOL_SCHEMA
)

__all__ = [
    'get_weather',
    'get_forecast',
    'is_weather_query',
    'extract_location_from_message',
    'get_weather_forecast',
    'WEATHER_TOOL_SCHEMA'
]
