#!/usr/bin/env python3
"""
Setup script for Alert System
Run this once to initialize the alert system in your database
"""

import sqlite3
import sys

def setup_alerts(db_path):
    """Initialize alert system tables"""
    conn = sqlite3.connect(db_path)

    with open('alerts_schema.sql', 'r') as f:
        schema = f.read()

    conn.executescript(schema)
    conn.commit()
    conn.close()

    print("✅ Alert system initialized!")
    print("\nNext steps:")
    print("1. Add your Pushover credentials:")
    print("   python3 -c \"import sqlite3; conn = sqlite3.connect('{}'); conn.execute('UPDATE settings SET value=\\\"YOUR_USER_KEY\\\" WHERE key=\\\"pushover_user_key\\\"'); conn.execute('UPDATE settings SET value=\\\"YOUR_API_TOKEN\\\" WHERE key=\\\"pushover_api_token\\\"'); conn.commit()\"".format(db_path))
    print("\n2. Test alerts:")
    print("   python3 alerts.py")
    print("\n3. Add custom alert rules:")
    print("   - For A380:")
    print("     sqlite3 {} \"INSERT INTO alert_rules (name, type, value) VALUES ('A380 Spotted', 'aircraft_type', 'A388')\"".format(db_path))
    print("   - For specific flight:")
    print("     sqlite3 {} \"INSERT INTO alert_rules (name, type, value) VALUES ('My Flight', 'callsign', 'DLH400')\"".format(db_path))

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/home/pi/adsb-stats/adsb.db"
    setup_alerts(db_path)
