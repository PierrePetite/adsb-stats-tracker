-- Migration: Add route cache table
-- Run this on existing databases to add route tracking

-- Create route_cache table
CREATE TABLE IF NOT EXISTS route_cache (
    callsign TEXT PRIMARY KEY,
    origin_iata TEXT,
    origin_icao TEXT,
    origin_name TEXT,
    origin_country TEXT,
    origin_lat REAL,
    origin_lon REAL,
    destination_iata TEXT,
    destination_icao TEXT,
    destination_name TEXT,
    destination_country TEXT,
    destination_lat REAL,
    destination_lon REAL,
    last_updated TEXT DEFAULT (datetime('now', 'localtime')),
    api_success INTEGER DEFAULT 1
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_route_callsign ON route_cache(callsign);
CREATE INDEX IF NOT EXISTS idx_route_updated ON route_cache(last_updated);
