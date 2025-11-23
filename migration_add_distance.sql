-- Migration: Add distance tracking
-- Run this on existing databases to add distance column

-- Add distance column to track max distance per sighting
ALTER TABLE aircraft_sightings ADD COLUMN distance_nm REAL;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_distance ON aircraft_sightings(distance_nm);
