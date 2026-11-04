########################################
# API Connection
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import json
import time
import logging
import datetime as dt
from typing import Optional

# External Dependencies
import httpx

# Internal project imports
from utils.eusst.config import *
from utils.tracss.config import *
from utils.ap_logs import *


#---------------------------------------
# Authorization
#---------------------------------------


def get_token(service: str):
    """
    Retrieves a cached token or fetches a new one based on the service name.
    Supported services: 'tracss', 'eusst'
    """
    service = service.lower()
    if service not in ['tracss', 'eusst']:
        raise ValueError(
            f"Unknown service: {service}. Choose 'tracss' or 'eusst'."
        )

    # 1. Check for valid cached token
    cache_paths = {
        "tracss": TRACSS_TOKEN_CACHE,
        "eusst": EUSST_TOKEN_CACHE
    }
    cache_path = cache_paths[service]

    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            expiry = dt.datetime.strptime(
                data['expires_at'], '%Y-%m-%d %H:%M:%S.%f'
            )
            # Buffer of 60 seconds to avoid edge-case failures
            if dt.datetime.now() < (expiry - dt.timedelta(seconds=60)):
                return data['access_token']
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # 2. Router: Map the service string to its specific fetch function
    fetch_functions = {
        "tracss": _fetch_tracss_token,
        "eusst": _fetch_eusst_token
    }

    return fetch_functions[service]()


def _fetch_tracss_token():
    with httpx.Client() as client:
        # Since OAUTH_URL has the params, we just need Auth and Header
        resp = client.post(
            TRACSS_OAUTH_URL,
            auth=(TRACSS_CLIENT_ID, TRACSS_SECRET_KEY),
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        resp.raise_for_status()
        data = resp.json()

    token = data['access_token']
    # Calculate expiry based on 'expires_in' (usually 3600 seconds)
    expiry_time = dt.datetime.now() + dt.timedelta(
        seconds=data.get('expires_in', 3600)
    )

    # 3. Save to cache
    with open(TRACSS_TOKEN_CACHE, 'w') as f:
        json.dump({
            'access_token': token,
            'expires_at': str(expiry_time)
        }, f)

    return token


def _fetch_eusst_token():
    """Fetches a new OAuth2 password grant token from EU EUSST."""

    # Define params using variables mapped from your TOML config
    params = {
        "grant_type": "password",
        "scope": "sstservices",
        "response_type": "token",
        "client_id": EUSST_CLIENT_ID,
        "client_secret": EUSST_SECRET_KEY,
        "username": EUSST_USERNAME,
        "password": EUSST_PASSWORD
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    with httpx.Client() as client:
        # Send data as form-encoded params using the 'data' parameter
        resp = client.post(EUSST_OAUTH_URL, headers=headers, data=params)
        resp.raise_for_status()
        data = resp.json()

    token = data['access_token']

    # Calculate expiry based on 'expires_in' (defaults to 3600 seconds / 1 hour if missing)
    expiry_time = dt.datetime.now() + dt.timedelta(
        seconds=data.get('expires_in', 3600)
    )

    # 3. Save to cache
    with open(EUSST_TOKEN_CACHE, 'w') as f:
        json.dump({
            'access_token': token,
            'expires_at': str(expiry_time)
        }, f)

    return token


#---------------------------------------
# API calls
#---------------------------------------


def api_call(
    service_name: str,
    url: str,
    query_params: Optional[dict] = None,
    max_retries: int = 3
) -> str | None:
    """
    Generic core network worker for both EU SST and TRACSS endpoints.
    Handles authentication dynamically, handles OData and standard network retries,
    and returns the raw string payload or None.
    """
    # 1. Dynamically retrieve the token based on the specified service
    token = get_token(service_name)
    params = query_params if query_params is not None else {}

    with httpx.Client(timeout=60.0, http2=True) as client:
        for attempt in range(max_retries):
            try:
                resp = client.get(
                    url,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )

                # 2. Handle HTTP 204 No Content
                if resp.status_code == 204:
                    logger.info(
                        f"[{service_name.upper()}] Received 204 No Content."
                    )
                    return None

                # 3. Handle legitimate 4xx/5xx errors
                resp.raise_for_status()
                return resp.text

            except httpx.HTTPError as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"[{service_name.upper()}] Final network attempt failed: {e}"
                    )
                    return None
                logger.warning(
                    f"[{service_name.upper()}] Attempt {attempt + 1} failed: {e}. Retrying in 2 seconds..."
                )
                time.sleep(2)

    return None
