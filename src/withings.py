import time
from typing import Dict, Any, Optional, List
import httpx
from upstash_redis import Redis
from datetime import datetime
from .models import BodyMeasurement
from .metrics import add_moving_average
from .config import (
    WBSAPI_URL,
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
    WITHINGS_CLIENT_ID,
    WITHINGS_CLIENT_SECRET,
    CLIENT_ID,
    CUSTOMER_SECRET,
)

redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)

async def refresh_access_token() -> Optional[str]:
    """
    Refresh the Withings access token using the refresh token stored in Redis.
    
    Returns:
        Optional[str]: New access token if refresh was successful, None otherwise
        
    Raises:
        ValueError: If refresh token is not found in Redis
    """
    refresh_token = redis.get("withings_refresh_token")
    if not refresh_token:
        raise ValueError("No Withings refresh token found in Redis")
        
    payload = {
        'action': 'requesttoken',
        'client_id': WITHINGS_CLIENT_ID,
        'client_secret': WITHINGS_CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f'{WBSAPI_URL}/v2/oauth2', data=payload)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 0:  # Withings API success status
                body = data.get('body', {})
                new_access_token = body.get('access_token')
                new_refresh_token = body.get('refresh_token')
                
                # Store new tokens
                redis.set("withings_access_token", new_access_token)
                redis.set("withings_refresh_token", new_refresh_token)
                return new_access_token
    return None

async def get_measurements(days: int = 7) -> List[BodyMeasurement]:
    """
    Fetch measurements from Withings API for the last n days.
    Uses access token stored in Redis and attempts to refresh if needed.
    
    Args:
        days (int): Number of days to fetch measurements for. Defaults to 7.
    
    Returns:
        List[BodyMeasurement]: List of body measurements from the Withings API
        
    Raises:
        ValueError: If both access token and refresh token are not found in Redis
        RuntimeError: If unable to get valid authentication
    """
    access_token = redis.get("withings_access_token")
    if not access_token:
        access_token = await refresh_access_token()
        if not access_token:
            raise ValueError("No valid access token available and refresh failed")

    # Calculate time range for last n days
    startdate = int(time.time()) - (days * 24 * 60 * 60)  # n days ago
    enddate = int(time.time())  # current time

    payload = {
        'action': 'getmeas',
        'startdate': startdate,
        'enddate': enddate
    }
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f'{WBSAPI_URL}/v2/measure',
            headers=headers,
            params=payload
        )
    
    # If we get an unauthorized response, try refreshing the token once
    if response.status_code == 401:
        new_access_token = await refresh_access_token()
        if new_access_token:
            headers = {'Authorization': f'Bearer {new_access_token}'}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{WBSAPI_URL}/v2/measure',
                    headers=headers,
                    params=payload
                )
        else:
            raise RuntimeError("Failed to refresh authentication token")
    
    data = response.json()
    if data.get('status') != 0:
        raise RuntimeError(f"Withings API error: {data.get('error')}")
        
    measurements: List[BodyMeasurement] = []
    measuregroups = data.get('body', {}).get('measuregrps', [])
    
    for group in measuregroups:
        measurement_time = datetime.fromtimestamp(group.get('date', 0))
        measures = {
            m['type']: m['value'] * (10 ** m['unit'])
            for m in group.get('measures', [])
        }

        # Map Withings measurement types to our model fields
        # Reference: https://developer.withings.com/api-reference/#operation/measure-getmeas
        measurements.append(
            BodyMeasurement(
                measurement_time=measurement_time,
                weight_kg=measures.get(1, 0),  # Weight (kg)
                fat_mass_kg=measures.get(8, 0),  # Fat Mass (kg)
                muscle_mass_kg=measures.get(76, 0),  # Muscle Mass (kg)
                bone_mass_kg=measures.get(88, 0),  # Bone Mass (kg)
                hydration_kg=measures.get(77, 0),  # Hydration (kg)
                fat_free_mass_kg=measures.get(5, 0),  # Fat Free Mass (kg)
                body_fat_percent=measures.get(6, 0),  # Body Fat Percentage
                device_name=group.get('device', 'Withings Device')
            )
        )

    return add_moving_average(measurements)
