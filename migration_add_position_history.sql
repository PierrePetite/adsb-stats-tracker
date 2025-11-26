-- Migration: Add position_history table for tracking aircraft positions
-- Purpose: Store position updates for drawing flight tracks in tvOS/iOS apps
-- Retention: Last 2 hours of data (auto-cleaned)

CREATE TABLE IF NOT EXISTS position_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    callsign TEXT NOT NULL,
    icao_hex TEXT NOT NULL,
    lat REAL,
    lon REAL,
    altitude INTEGER,
    track INTEGER,
    ground_speed INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_callsign_time ON position_history(callsign, timestamp);
CREATE INDEX IF NOT EXISTS idx_timestamp ON position_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_icao_time ON position_history(icao_hex, timestamp);
