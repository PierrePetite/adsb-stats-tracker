# Migration Guide: Adding Squawk Support

This migration adds squawk code tracking to your ADSB statistics database.

## What's New

- Squawk codes are now collected and stored
- Required for alert system (Squawk 7700, 7600, 7500 alerts)
- New database column: `squawk TEXT`
- New index for faster squawk-based queries

## Migration Steps

### On Raspberry Pi

```bash
ssh pi@192.168.1.100
cd /home/pi/adsb-stats

# 1. Backup your database (just in case)
cp adsb.db adsb.db.backup

# 2. Run the migration
sqlite3 adsb.db < migration_add_squawk.sql

# 3. Verify the migration
sqlite3 adsb.db "PRAGMA table_info(aircraft_sightings);"
# You should see 'squawk' in the column list

# 4. Update collect.py and alerts.py
# (Copy the updated files from the repo)
```

### What This Fixes

Before this migration, the alert system couldn't detect:
- Emergency squawks (7700)
- Radio failure (7600)
- Hijack alerts (7500)

After migration, squawk codes are collected every minute and the alert system can trigger on these codes.

## No Data Loss

This migration only adds a new column. All existing data remains intact. The squawk field will be populated starting from the next data collection run.

## Rollback (if needed)

```bash
# Restore from backup
cp adsb.db.backup adsb.db
```

---

Created: 2025-11-22
