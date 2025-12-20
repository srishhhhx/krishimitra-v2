"""
Weather Tool - MCP Integration

Provides real-time weather data via MCP server for agricultural intelligence.
Supports caching, error handling, and both local and remote MCP servers.

MCP Server: weather-mcp (OpenWeatherMap integration)
Tools: get_weather(lat, lon), get_forecast(lat, lon, days)
"""
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from langchain.tools import tool
from fastmcp.client import Client
import httpx
from core.logging import get_logger
from core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


# ============================================================================
# Weather Data Cache
# ============================================================================

class WeatherCache:
    """Simple in-memory cache for weather data with TTL"""

    def __init__(self, ttl_minutes: int = 15):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_minutes = ttl_minutes

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached weather data if not expired"""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        expiry = entry["expiry"]

        if datetime.now() > expiry:
            # Cache expired
            del self.cache[key]
            return None

        return entry["data"]

    def set(self, key: str, data: Dict[str, Any]):
        """Store weather data with expiry timestamp"""
        self.cache[key] = {
            "data": data,
            "expiry": datetime.now() + timedelta(minutes=self.ttl_minutes)
        }

    def clear(self):
        """Clear all cached data"""
        self.cache.clear()


# Global cache instance
weather_cache = WeatherCache(ttl_minutes=settings.weather_cache_ttl)


# ============================================================================
# MCP Client Helpers
# ============================================================================

async def get_mcp_client_path() -> Optional[str]:
    """
    Get MCP server path from environment.

    Priority:
    1. MCP_WEATHER_PATH (local development)
    2. MCP_WEATHER_URL (production - future)

    Returns:
        MCP server path/URL or None if not configured
    """
    # Check for local path (development)
    local_path = settings.mcp_weather_path
    if local_path and os.path.exists(local_path):
        return local_path

    # Check for remote URL (production - future)
    remote_url = settings.mcp_weather_url
    if remote_url:
        logger.info(f"Using remote MCP server: {remote_url}")
        return remote_url

    logger.warning("No MCP server configured (MCP_WEATHER_PATH or MCP_WEATHER_URL)")
    return None


async def call_mcp_weather_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    timeout_seconds: int = 10,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Call MCP weather tool with error handling, timeout, and exponential backoff retry.
    Supports both local (fastmcp) and remote (HTTP) MCP servers.

    BUG FIX #10: Added exponential backoff retry logic for timeout resilience.

    Args:
        tool_name: Name of MCP tool (get_weather, get_forecast, health_check)
        arguments: Tool arguments (lat, lon, days, etc.)
        timeout_seconds: Maximum time to wait for response per attempt
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Tool result as dictionary

    Raises:
        Exception: If MCP server not configured or all retries exhausted
    """
    mcp_path = await get_mcp_client_path()

    if not mcp_path:
        raise Exception(
            "Weather MCP server not configured. "
            "Set MCP_WEATHER_PATH or MCP_WEATHER_URL in .env"
        )

    # Retry with exponential backoff
    last_exception = None

    for attempt in range(max_retries):
        try:
            # Check if remote (HTTP) or local (file path)
            is_remote = mcp_path.startswith("http://") or mcp_path.startswith("https://")

            if is_remote:
                # Remote MCP server - use HTTP REST API
                async with asyncio.timeout(timeout_seconds):
                    async with httpx.AsyncClient() as client:
                        # Map tool names to HTTP endpoints
                        if tool_name == "get_weather":
                            # POST /weather with {lat, lon}
                            endpoint = f"{mcp_path}/weather"
                            response = await client.post(
                                endpoint,
                                json={"lat": arguments["lat"], "lon": arguments["lon"]},
                                timeout=timeout_seconds
                            )
                        elif tool_name == "get_forecast":
                            # POST /forecast with {lat, lon, days}
                            endpoint = f"{mcp_path}/forecast"
                            response = await client.post(
                                endpoint,
                                json={
                                    "lat": arguments["lat"],
                                    "lon": arguments["lon"],
                                    "days": arguments.get("days", 5)
                                },
                                timeout=timeout_seconds
                            )
                        elif tool_name == "health_check":
                            # GET /health
                            endpoint = f"{mcp_path}/health"
                            response = await client.get(endpoint, timeout=timeout_seconds)
                        else:
                            raise Exception(f"Unknown tool name: {tool_name}")

                        response.raise_for_status()
                        return response.json()
            else:
                # Local MCP server - use fastmcp Client
                async with asyncio.timeout(timeout_seconds):
                    async with Client(mcp_path) as client:
                        result = await client.call_tool(tool_name, arguments)

                        # Parse JSON response
                        response_text = result.content[0].text
                        return json.loads(response_text)

        except asyncio.TimeoutError as e:
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                backoff_seconds = 2 ** attempt
                logger.warning(
                    f"MCP tool {tool_name} timed out (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {backoff_seconds}s..."
                )
                await asyncio.sleep(backoff_seconds)
            else:
                logger.error(f"MCP tool {tool_name} timed out after {max_retries} attempts")
                raise Exception(f"Weather request timed out after {max_retries} attempts (>{timeout_seconds}s each)")

        except httpx.HTTPStatusError as e:
            # Don't retry on HTTP errors (4xx, 5xx) - they won't succeed on retry
            logger.error(f"MCP HTTP error for {tool_name}: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Weather service error: {e.response.status_code}")

        except Exception as e:
            # Log and re-raise unexpected errors
            logger.error(f"MCP tool {tool_name} failed: {e}", exc_info=True)
            raise

    # Should never reach here, but handle gracefully
    if last_exception:
        raise Exception(f"Weather request failed after {max_retries} attempts") from last_exception
    else:
        raise Exception(f"Weather request failed for unknown reason")


# ============================================================================
# LangChain Tool Wrapper
# ============================================================================

@tool
async def get_weather_data(
    latitude: float,
    longitude: float,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get current weather data for a location using MCP weather server.

    This tool fetches real-time weather data from OpenWeatherMap via the
    MCP weather server. Results are cached for 15 minutes to reduce API calls.

    Args:
        latitude: Location latitude (e.g., 12.9716 for Bangalore)
        longitude: Location longitude (e.g., 77.5946 for Bangalore)
        use_cache: Whether to use cached data (default: True)

    Returns:
        Dictionary containing:
        - temperature: Temperature in Celsius
        - humidity: Relative humidity percentage (0-100)
        - wind_speed: Wind speed in km/h
        - feels_like: Feels like temperature in Celsius
        - pressure: Atmospheric pressure in hPa
        - visibility: Visibility in meters
        - description: Weather description (e.g., "clear sky")
        - location_name: City/location name
        - timestamp: Data fetch timestamp (UTC)
        - source: Data source ("OpenWeatherMap via MCP")

    Example:
        >>> result = await get_weather_data(latitude=12.9716, longitude=77.5946)
        >>> print(result['temperature'])
        25.3
        >>> print(result['description'])
        'clear sky'
    """
    try:
        # Create cache key
        cache_key = f"weather_{latitude:.4f}_{longitude:.4f}"

        # Check cache first
        if use_cache:
            cached_data = weather_cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Weather cache HIT for {latitude:.4f}, {longitude:.4f} "
                    f"(age: {cached_data.get('cache_age_minutes', 'unknown')}m)"
                )
                return cached_data

        # Cache miss - fetch from MCP server
        logger.info(f"Fetching weather data for {latitude:.4f}, {longitude:.4f} from MCP")

        # Call MCP get_weather tool
        raw_data = await call_mcp_weather_tool(
            tool_name="get_weather",
            arguments={"lat": latitude, "lon": longitude}
        )

        # Normalize and enrich response
        weather_data = {
            "temperature": raw_data.get("temperature", 0.0),
            "humidity": raw_data.get("humidity", 0),
            "wind_speed": raw_data.get("wind_speed", 0.0),
            "feels_like": raw_data.get("feels_like", raw_data.get("temperature", 0.0)),
            "pressure": raw_data.get("pressure", 1013),
            "visibility": raw_data.get("visibility", 10000),
            "description": raw_data.get("description", "clear"),
            "location_name": raw_data.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "OpenWeatherMap via MCP",
            "latitude": latitude,
            "longitude": longitude,
            "cache_age_minutes": 0,  # Fresh data
        }

        # Store in cache
        if use_cache:
            weather_cache.set(cache_key, weather_data)
            logger.info(f"Weather data cached for {latitude:.4f}, {longitude:.4f}")

        logger.info(
            f"Weather retrieved: {weather_data['temperature']}°C, "
            f"{weather_data['humidity']}% humidity at {weather_data['location_name']}"
        )

        return weather_data

    except Exception as e:
        logger.error(f"Failed to get weather data: {e}", exc_info=True)
        return {
            "error": f"Failed to retrieve weather data: {str(e)}",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "latitude": latitude,
            "longitude": longitude,
        }


@tool
async def get_weather_forecast(
    latitude: float,
    longitude: float,
    days: int = 3,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get weather forecast for a location (3-7 days).

    Args:
        latitude: Location latitude
        longitude: Location longitude
        days: Number of forecast days (default: 3, max: 7)
        use_cache: Whether to use cached data (default: True)

    Returns:
        Dictionary containing:
        - forecast: List of daily forecasts
        - location_name: City/location name
        - timestamp: Forecast generation time
        - source: Data source

    Example:
        >>> result = await get_weather_forecast(12.9716, 77.5946, days=3)
        >>> print(len(result['forecast']))
        3
    """
    try:
        # Limit days to 1-7 range
        days = max(1, min(7, days))

        # Create cache key
        cache_key = f"forecast_{latitude:.4f}_{longitude:.4f}_{days}d"

        # Check cache
        if use_cache:
            cached_data = weather_cache.get(cache_key)
            if cached_data:
                logger.info(f"Forecast cache HIT for {latitude:.4f}, {longitude:.4f}")
                return cached_data

        # Fetch from MCP server
        logger.info(f"Fetching {days}-day forecast for {latitude:.4f}, {longitude:.4f}")

        raw_data = await call_mcp_weather_tool(
            tool_name="get_forecast",
            arguments={"lat": latitude, "lon": longitude, "days": days}
        )

        # Normalize response
        forecast_data = {
            "forecast": raw_data.get("forecast", []),
            "location_name": raw_data.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "OpenWeatherMap via MCP",
            "latitude": latitude,
            "longitude": longitude,
            "days": days,
        }

        # Store in cache
        if use_cache:
            weather_cache.set(cache_key, forecast_data)

        logger.info(f"Forecast retrieved: {len(forecast_data['forecast'])} days")
        return forecast_data

    except Exception as e:
        logger.error(f"Failed to get weather forecast: {e}", exc_info=True)
        return {
            "error": f"Failed to retrieve weather forecast: {str(e)}",
            "forecast": [],
            "latitude": latitude,
            "longitude": longitude,
        }


# ============================================================================
# Utility Functions
# ============================================================================

def clear_weather_cache():
    """Clear all cached weather data"""
    weather_cache.clear()
    logger.info("Weather cache cleared")


async def health_check_mcp_server() -> Dict[str, Any]:
    """
    Check health of MCP weather server

    Returns:
        Health status dictionary
    """
    try:
        mcp_path = await get_mcp_client_path()

        if not mcp_path:
            return {
                "status": "unavailable",
                "message": "MCP server not configured"
            }

        # Call health_check tool if available
        try:
            result = await call_mcp_weather_tool(
                tool_name="health_check",
                arguments={},
                timeout_seconds=5
            )
            return {
                "status": "healthy",
                "mcp_server": mcp_path,
                "server_health": result
            }
        except:
            # Try get_weather as fallback health check
            test_result = await call_mcp_weather_tool(
                tool_name="get_weather",
                arguments={"lat": 12.9716, "lon": 77.5946},
                timeout_seconds=5
            )
            return {
                "status": "healthy",
                "mcp_server": mcp_path,
                "test_successful": True
            }

    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
