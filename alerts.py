#!/usr/bin/env python3
"""
Alert System for ADSB Stats Tracker
Monitors aircraft for specific conditions and sends push notifications
"""

import sqlite3
import requests
from datetime import datetime, timedelta

# Try to import config
try:
    from config import DB_PATH, TIMEZONE
except ImportError:
    DB_PATH = "/home/pi/adsb-stats/adsb.db"
    TIMEZONE = "Europe/Berlin"

import os
os.environ['TZ'] = TIMEZONE

class AlertManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def get_active_rules(self):
        """Get all enabled alert rules"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        rules = cur.execute("""
            SELECT id, name, type, value
            FROM alert_rules
            WHERE enabled = 1
        """).fetchall()
        conn.close()
        return rules

    def get_pushover_settings(self):
        """Get Pushover credentials from settings"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        user_key = cur.execute("SELECT value FROM settings WHERE key = 'pushover_user_key'").fetchone()
        api_token = cur.execute("SELECT value FROM settings WHERE key = 'pushover_api_token'").fetchone()
        enabled = cur.execute("SELECT value FROM settings WHERE key = 'alerts_enabled'").fetchone()

        conn.close()

        return {
            'user_key': user_key[0] if user_key else None,
            'api_token': api_token[0] if api_token else None,
            'enabled': enabled[0] == '1' if enabled else False
        }

    def check_aircraft(self, aircraft):
        """
        Check if aircraft triggers any alert rules

        aircraft dict should contain:
        - icao_hex
        - callsign (flight)
        - aircraft_type (t)
        - squawk
        - altitude (alt_baro)
        - lat, lon
        """
        rules = self.get_active_rules()
        triggered = []

        for rule_id, rule_name, rule_type, rule_value in rules:
            match = False

            if rule_type == 'squawk':
                squawk = aircraft.get('squawk', '').strip()
                if squawk == rule_value:
                    match = True

            elif rule_type == 'callsign':
                callsign = aircraft.get('flight', '').strip()
                # Match partial or full callsign
                if rule_value.upper() in callsign.upper():
                    match = True

            elif rule_type == 'aircraft_type':
                aircraft_type = aircraft.get('t', '').strip()
                if aircraft_type.upper() == rule_value.upper():
                    match = True

            if match:
                # Check if we already triggered this recently (avoid spam)
                if not self.was_recently_triggered(rule_id, aircraft.get('hex', '')):
                    triggered.append({
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'rule_type': rule_type,
                        'rule_value': rule_value,
                        'aircraft': aircraft
                    })

        return triggered

    def was_recently_triggered(self, rule_id, icao_hex, minutes=30):
        """Check if this rule+aircraft combo was triggered in last X minutes"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cutoff = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')

        count = cur.execute("""
            SELECT COUNT(*) FROM alert_history
            WHERE rule_id = ? AND icao_hex = ? AND triggered_at > ?
        """, (rule_id, icao_hex, cutoff)).fetchone()[0]

        conn.close()
        return count > 0

    def log_alert(self, rule_id, aircraft, sent_push=False):
        """Log triggered alert to history"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO alert_history
            (rule_id, icao_hex, callsign, aircraft_type, squawk, altitude, lat, lon, sent_push)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_id,
            aircraft.get('hex', ''),
            aircraft.get('flight', '').strip(),
            aircraft.get('t', ''),
            aircraft.get('squawk', ''),
            aircraft.get('alt_baro'),
            aircraft.get('lat'),
            aircraft.get('lon'),
            1 if sent_push else 0
        ))

        conn.commit()
        conn.close()

    def send_pushover(self, title, message, priority=1):
        """Send push notification via Pushover"""
        settings = self.get_pushover_settings()

        if not settings['enabled']:
            print("Alerts disabled in settings")
            return False

        if not settings['user_key'] or not settings['api_token']:
            print("Pushover not configured")
            return False

        data = {
            'token': settings['api_token'],
            'user': settings['user_key'],
            'title': title,
            'message': message,
            'priority': priority,  # 1 = high priority
            'sound': 'siren'  # Special sound for alerts
        }

        try:
            resp = requests.post('https://api.pushover.net/1/messages.json', data=data, timeout=10)
            if resp.status_code == 200:
                print(f"✅ Alert sent: {title}")
                return True
            else:
                print(f"❌ Pushover failed: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Error sending alert: {e}")
            return False

    def process_alert(self, alert):
        """Process a triggered alert - log and send push"""
        rule_name = alert['rule_name']
        aircraft = alert['aircraft']

        # Build message
        callsign = aircraft.get('flight', 'Unknown').strip()
        icao = aircraft.get('hex', '')
        aircraft_type = aircraft.get('t', 'Unknown')
        altitude = aircraft.get('alt_baro', 0)
        squawk = aircraft.get('squawk', '')

        title = f"🚨 Alert: {rule_name}"

        message = f"Aircraft: {callsign} ({aircraft_type})\n"
        message += f"ICAO: {icao}\n"

        if squawk:
            message += f"Squawk: {squawk}\n"

        message += f"Altitude: {altitude} ft\n"
        message += f"\nTriggered: {datetime.now().strftime('%H:%M:%S')}"

        # Send push
        sent = self.send_pushover(title, message, priority=1)

        # Log to history
        self.log_alert(alert['rule_id'], aircraft, sent_push=sent)

        return sent

def check_alerts_for_aircraft_list(aircraft_list):
    """
    Convenience function to check a list of aircraft
    Returns list of alerts sent
    """
    manager = AlertManager()
    alerts_sent = []

    for aircraft in aircraft_list:
        triggered = manager.check_aircraft(aircraft)

        for alert in triggered:
            if manager.process_alert(alert):
                alerts_sent.append(alert)

    return alerts_sent

if __name__ == "__main__":
    # Test with sample aircraft
    test_aircraft = {
        'hex': '123456',
        'flight': 'TEST123',
        't': 'A388',
        'squawk': '7700',
        'alt_baro': 35000,
        'lat': 51.0,
        'lon': 13.0
    }

    manager = AlertManager()
    triggered = manager.check_aircraft(test_aircraft)

    if triggered:
        print(f"Found {len(triggered)} alerts:")
        for alert in triggered:
            print(f"  - {alert['rule_name']}")
            manager.process_alert(alert)
    else:
        print("No alerts triggered")
