-- Route Cache Table
-- Stores flight routes fetched from adsbdb.com API
-- Updated every 7 days to keep data fresh

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
    api_success INTEGER DEFAULT 1  -- 1 if route found, 0 if not found
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_route_callsign ON route_cache(callsign);
CREATE INDEX IF NOT EXISTS idx_route_updated ON route_cache(last_updated);
