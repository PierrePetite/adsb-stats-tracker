-- Alert System Schema
-- Add to existing database

-- Alert configurations
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'squawk', 'callsign', 'aircraft_type'
    value TEXT NOT NULL, -- '7700', 'DLH400', 'A388'
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Alert history (triggered alerts)
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER,
    icao_hex TEXT,
    callsign TEXT,
    aircraft_type TEXT,
    squawk TEXT,
    altitude INTEGER,
    lat REAL,
    lon REAL,
    triggered_at TEXT DEFAULT (datetime('now', 'localtime')),
    sent_push INTEGER DEFAULT 0,
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Insert default settings
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('pushover_user_key', ''),
    ('pushover_api_token', ''),
    ('alerts_enabled', '1');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_alert_rules_type ON alert_rules(type);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at);

-- Insert default alert rule for Squawk 7700
INSERT OR IGNORE INTO alert_rules (name, type, value, enabled)
VALUES ('Emergency - Squawk 7700', 'squawk', '7700', 1);
