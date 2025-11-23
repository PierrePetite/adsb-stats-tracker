-- Migration: Add squawk field to aircraft_sightings table
-- Run this on existing databases to add squawk tracking

-- Add squawk column
ALTER TABLE aircraft_sightings ADD COLUMN squawk TEXT;

-- Create index for faster squawk-based queries
CREATE INDEX IF NOT EXISTS idx_aircraft_squawk ON aircraft_sightings(squawk);
