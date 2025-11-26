#!/usr/bin/env python3
"""
ADSB Aircraft Collector - Remote Support
Collects aircraft data from readsb (local file or remote HTTP)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import os
import sys
import requests

# Try to import config
try:
    from config import (
        TIMEZONE, DB_PATH,
        READSB_MODE, READSB_URL, AIRCRAFT_JSON_PATH,
        MIN_ALTITUDE, MAX_RANGE_KM, RECEIVER_LAT, RECEIVER_LON
    )
except ImportError:
    print("⚠️  config.py not found! Using default configuration.")
    TIMEZONE = "Europe/Berlin"
    DB_PATH = "/home/claude/adsb-stats/adsb.db"
    READSB_MODE = "local"
    READSB_URL = None
    AIRCRAFT_JSON_PATH = "/run/readsb/aircraft.json"
    MIN_ALTITUDE = None
    MAX_RANGE_KM = None
    RECEIVER_LAT = None
    RECEIVER_LON = None

# Set timezone
os.environ['TZ'] = TIMEZONE

def get_airline_from_callsign(callsign):
    """Extract airline code from callsign (first 3 characters)."""
    if not callsign or len(callsign) < 3:
        return None
    return callsign[:3].strip()

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in nautical miles."""
    from math import radians, sin, cos, sqrt, atan2
    R = 3440.065  # Earth radius in nautical miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def fetch_aircraft_data():
    """Fetch aircraft data from local file or remote URL."""
    if READSB_MODE == "remote":
        # Fetch via HTTP
        try:
            response = requests.get(READSB_URL, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"ERROR: Cannot fetch from {READSB_URL}: {e}")
            return None
    else:
        # Read from local file
        try:
            with open(AIRCRAFT_JSON_PATH, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"ERROR: {AIRCRAFT_JSON_PATH} not found. Is readsb running?")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
            return None

def collect_data():
    """Main collection function."""
    data = fetch_aircraft_data()
    if not data:
        return

    aircraft_list = data.get('aircraft', [])

    # Check alerts
    try:
        from alerts import check_alerts_for_aircraft_list
        check_alerts_for_aircraft_list(aircraft_list)
    except Exception as e:
        print(f"Alert check failed: {e}")

    # Fetch routes
    try:
        from route_lookup import get_route
        unique_callsigns = set()
        for aircraft in aircraft_list:
            callsign = aircraft.get('flight', '').strip()
            if callsign and callsign not in unique_callsigns:
                unique_callsigns.add(callsign)
                get_route(callsign)
    except Exception as e:
        print(f"Route lookup failed: {e}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
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
        aircraft_type = aircraft.get('t', '')
        altitude = aircraft.get('alt_baro', None)
        squawk = aircraft.get('squawk', None)

        # Calculate distance from receiver
        distance_nm = None
        if RECEIVER_LAT and RECEIVER_LON:
            ac_lat = aircraft.get('lat')
            ac_lon = aircraft.get('lon')
            if ac_lat and ac_lon:
                distance_nm = calculate_distance_nm(RECEIVER_LAT, RECEIVER_LON, ac_lat, ac_lon)

        # Insert or update
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

        # Store position history for track visualization
        cur.execute("""
            INSERT INTO position_history
            (callsign, icao_hex, lat, lon, altitude, track, ground_speed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            callsign,
            icao_hex,
            aircraft.get('lat'),
            aircraft.get('lon'),
            altitude,
            aircraft.get('track'),
            aircraft.get('gs')
        ))

        collected += 1

    # Cleanup old position history (keep only last 2 hours)
    cur.execute("""
        DELETE FROM position_history
        WHERE timestamp < datetime('now', '-2 hours')
    """)

    conn.commit()
    conn.close()

    print(f"{now} - Collected {collected} aircraft (Mode: {READSB_MODE})")

if __name__ == "__main__":
    collect_data()
