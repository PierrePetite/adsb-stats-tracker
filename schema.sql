-- ADSB Statistics Database Schema
-- SQLite3 database for tracking aircraft sightings

CREATE TABLE IF NOT EXISTS aircraft_sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    icao_hex TEXT NOT NULL,
    callsign TEXT NOT NULL,
    airline TEXT,
    aircraft_type TEXT,
    first_seen TEXT DEFAULT (datetime('now', 'localtime')),
    last_seen TEXT DEFAULT (datetime('now', 'localtime')),
    min_altitude INTEGER,
    max_altitude INTEGER,
    distance_nm REAL,
    squawk TEXT,
    UNIQUE(callsign, date)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_date ON aircraft_sightings(date);
CREATE INDEX IF NOT EXISTS idx_airline ON aircraft_sightings(airline);
CREATE INDEX IF NOT EXISTS idx_aircraft_type ON aircraft_sightings(aircraft_type);
CREATE INDEX IF NOT EXISTS idx_first_seen ON aircraft_sightings(first_seen);
CREATE INDEX IF NOT EXISTS idx_distance ON aircraft_sightings(distance_nm);
CREATE INDEX IF NOT EXISTS idx_squawk ON aircraft_sightings(squawk);
