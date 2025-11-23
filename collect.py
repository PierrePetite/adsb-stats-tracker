#!/usr/bin/env python3
"""
ADSB Aircraft Collector
Collects aircraft data from readsb's aircraft.json every minute
and stores in SQLite database for statistics.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import os
import sys

# Try to import config, fall back to defaults if not found
try:
    from config import (
        TIMEZONE, DB_PATH, AIRCRAFT_JSON_PATH,
        MIN_ALTITUDE, MAX_RANGE_KM, RECEIVER_LAT, RECEIVER_LON
    )
except ImportError:
    print("⚠️  config.py not found! Using default configuration.")
    print("   Copy config.py.example to config.py and adjust settings.")
    TIMEZONE = "Europe/Berlin"
    DB_PATH = "/home/YOUR_USER/adsb-stats/adsb.db"
    AIRCRAFT_JSON_PATH = "/run/readsb/aircraft.json"
    MIN_ALTITUDE = None
    MAX_RANGE_KM = None
    RECEIVER_LAT = None
    RECEIVER_LON = None

# Set timezone
os.environ['TZ'] = TIMEZONE

# Backwards compatibility aliases
DB_FILE = DB_PATH
AIRCRAFT_JSON = AIRCRAFT_JSON_PATH

def get_airline_from_callsign(callsign):
    """
    Extract airline code from callsign (first 3 characters).
    Examples: DLH123 -> DLH, UAL456 -> UAL
    """
    if not callsign or len(callsign) < 3:
        return None
    return callsign[:3].strip()

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points in nautical miles using Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2

    # Earth radius in nautical miles
    R = 3440.065

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def collect_data():
    """
    Main collection function:
    1. Read aircraft.json from readsb
    2. Filter for aircraft with position and callsign
    3. Store in database using INSERT ON CONFLICT UPDATE
    4. Check for alerts
    """
    try:
        # Read aircraft.json
        with open(AIRCRAFT_JSON, 'r') as f:
            data = json.load(f)

        aircraft_list = data.get('aircraft', [])

        # Check alerts for all aircraft
        try:
            from alerts import check_alerts_for_aircraft_list
            check_alerts_for_aircraft_list(aircraft_list)
        except Exception as e:
            print(f"Alert check failed: {e}")

        # Fetch routes for unique callsigns (async to avoid blocking)
        try:
            from route_lookup import get_route
            unique_callsigns = set()
            for aircraft in aircraft_list:
                callsign = aircraft.get('flight', '').strip()
                if callsign and callsign not in unique_callsigns:
                    unique_callsigns.add(callsign)
                    # This will fetch from API only if cache is stale (>7 days)
                    get_route(callsign)
        except Exception as e:
            print(f"Route lookup failed: {e}")

        # Connect to database
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        collected = 0

        for aircraft in aircraft_list:
            # Only process aircraft with position and callsign
            if not aircraft.get('lat') or not aircraft.get('lon'):
                continue

            callsign = aircraft.get('flight', '').strip()
            if not callsign:
                continue

            icao_hex = aircraft.get('hex', '')
            airline = get_airline_from_callsign(callsign)
            aircraft_type = aircraft.get('t', '')  # From readsb aircraft database
            altitude = aircraft.get('alt_baro', None)
            squawk = aircraft.get('squawk', None)

            # Calculate distance from receiver (if receiver coords available)
            distance_nm = None
            if RECEIVER_LAT and RECEIVER_LON:
                ac_lat = aircraft.get('lat')
                ac_lon = aircraft.get('lon')
                if ac_lat and ac_lon:
                    distance_nm = calculate_distance_nm(RECEIVER_LAT, RECEIVER_LON, ac_lat, ac_lon)

            # Insert or update
            # If callsign+date already exists, update last_seen, altitude, distance, and squawk
            cur.execute("""
                INSERT INTO aircraft_sightings
                (date, icao_hex, callsign, airline, aircraft_type, first_seen, last_seen, min_altitude, max_altitude, distance_nm, squawk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(callsign, date) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    min_altitude = MIN(min_altitude, excluded.min_altitude),
                    max_altitude = MAX(max_altitude, excluded.max_altitude),
                    distance_nm = MAX(distance_nm, excluded.distance_nm),
                    squawk = excluded.squawk
            """, (today, icao_hex, callsign, airline, aircraft_type, now, now, altitude, altitude, distance_nm, squawk))

            collected += 1

        conn.commit()
        conn.close()

        print(f"{now} - Collected {collected} aircraft")

    except FileNotFoundError:
        print(f"ERROR: {AIRCRAFT_JSON} not found. Is readsb running?")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    collect_data()
