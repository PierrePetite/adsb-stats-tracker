#!/usr/bin/env python3
"""
Route Lookup Module for ADSB Stats Tracker
Fetches flight routes from adsbdb.com API and caches them locally
Routes are refreshed every 7 days
"""

import sqlite3
import requests
from datetime import datetime, timedelta

# Try to import config
try:
    from config import DB_PATH, TIMEZONE
except ImportError:
    DB_PATH = "/home/pi/adsb-stats/adsb.db"
    TIMEZONE = "Europe/Berlin"

import os
os.environ['TZ'] = TIMEZONE

ADSBDB_API_URL = "https://api.adsbdb.com/v0/callsign/{}"
ROUTE_REFRESH_DAYS = 7

def needs_update(callsign, db_path=None):
    """
    Check if route needs to be updated (older than 7 days or not in cache)

    Returns:
        bool: True if route needs update, False otherwise
    """
    if not db_path:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = cur.execute("""
        SELECT last_updated FROM route_cache WHERE callsign = ?
    """, (callsign,)).fetchone()

    conn.close()

    if not result:
        return True  # Not in cache, needs update

    last_updated = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
    age_days = (datetime.now() - last_updated).days

    return age_days >= ROUTE_REFRESH_DAYS

def fetch_route_from_api(callsign):
    """
    Fetch route information from adsbdb.com API

    Args:
        callsign: Aircraft callsign (e.g., 'DLH400')

    Returns:
        dict: Route information or None if not found/error
    """
    try:
        url = ADSBDB_API_URL.format(callsign)
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            # Check if response contains route data
            if 'response' in data and 'flightroute' in data['response']:
                route = data['response']['flightroute']

                # Extract origin and destination
                origin = route.get('origin', {})
                destination = route.get('destination', {})

                return {
                    'origin_iata': origin.get('iata_code'),
                    'origin_icao': origin.get('icao_code'),
                    'origin_name': origin.get('name'),
                    'origin_country': origin.get('country_iso_name'),
                    'origin_lat': origin.get('latitude'),
                    'origin_lon': origin.get('longitude'),
                    'destination_iata': destination.get('iata_code'),
                    'destination_icao': destination.get('icao_code'),
                    'destination_name': destination.get('name'),
                    'destination_country': destination.get('country_iso_name'),
                    'destination_lat': destination.get('latitude'),
                    'destination_lon': destination.get('longitude'),
                    'api_success': 1
                }

        return None

    except Exception as e:
        print(f"Error fetching route for {callsign}: {e}")
        return None

def cache_route(callsign, route_data, db_path=None):
    """
    Cache route information in database

    Args:
        callsign: Aircraft callsign
        route_data: Route information dict (or None if not found)
        db_path: Database path (optional)
    """
    if not db_path:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if route_data:
        cur.execute("""
            INSERT OR REPLACE INTO route_cache
            (callsign, origin_iata, origin_icao, origin_name, origin_country, origin_lat, origin_lon,
             destination_iata, destination_icao, destination_name, destination_country, destination_lat, destination_lon,
             last_updated, api_success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            callsign,
            route_data.get('origin_iata'),
            route_data.get('origin_icao'),
            route_data.get('origin_name'),
            route_data.get('origin_country'),
            route_data.get('origin_lat'),
            route_data.get('origin_lon'),
            route_data.get('destination_iata'),
            route_data.get('destination_icao'),
            route_data.get('destination_name'),
            route_data.get('destination_country'),
            route_data.get('destination_lat'),
            route_data.get('destination_lon'),
            now,
            route_data.get('api_success', 1)
        ))
    else:
        # Cache as "not found" to avoid repeated API calls
        cur.execute("""
            INSERT OR REPLACE INTO route_cache
            (callsign, last_updated, api_success)
            VALUES (?, ?, ?)
        """, (callsign, now, 0))

    conn.commit()
    conn.close()

def get_route(callsign, db_path=None):
    """
    Get route for callsign (from cache or API)

    Args:
        callsign: Aircraft callsign
        db_path: Database path (optional)

    Returns:
        dict: Route information or None
    """
    if not db_path:
        db_path = DB_PATH

    # Check if we need to update
    if needs_update(callsign, db_path):
        # Fetch from API
        route_data = fetch_route_from_api(callsign)

        # Cache the result (even if None)
        cache_route(callsign, route_data, db_path)

        return route_data

    # Get from cache
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = cur.execute("""
        SELECT origin_iata, origin_icao, origin_name, origin_country, origin_lat, origin_lon,
               destination_iata, destination_icao, destination_name, destination_country, destination_lat, destination_lon,
               api_success
        FROM route_cache WHERE callsign = ?
    """, (callsign,)).fetchone()

    conn.close()

    if not result or result[12] == 0:  # api_success is 0
        return None

    return {
        'origin_iata': result[0],
        'origin_icao': result[1],
        'origin_name': result[2],
        'origin_country': result[3],
        'origin_lat': result[4],
        'origin_lon': result[5],
        'destination_iata': result[6],
        'destination_icao': result[7],
        'destination_name': result[8],
        'destination_country': result[9],
        'destination_lat': result[10],
        'destination_lon': result[11]
    }

if __name__ == "__main__":
    # Test the route lookup
    test_callsigns = ['DLH400', 'DLH413', 'UAL123']

    for callsign in test_callsigns:
        print(f"\nTesting route lookup for {callsign}...")
        route = get_route(callsign)

        if route:
            print(f"  ✅ Route found:")
            print(f"     {route['origin_iata']} ({route['origin_name']}) →")
            print(f"     {route['destination_iata']} ({route['destination_name']})")
        else:
            print(f"  ❌ No route found")
