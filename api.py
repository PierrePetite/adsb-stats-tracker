#!/usr/bin/env python3
"""
Flask API for ADSB Alert System
Provides REST endpoints for managing alerts via web interface
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

# Try to import config
try:
    from config import DB_PATH, TIMEZONE
except ImportError:
    DB_PATH = "/home/pi/adsb-stats/adsb.db"
    TIMEZONE = "Europe/Berlin"

os.environ['TZ'] = TIMEZONE

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# ALERT RULES ENDPOINTS
# ============================================================================

@app.route('/api/alert-rules', methods=['GET'])
def get_alert_rules():
    """Get all alert rules"""
    conn = get_db()
    cur = conn.cursor()

    rules = cur.execute("""
        SELECT id, name, type, value, enabled, created_at
        FROM alert_rules
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(r) for r in rules])

@app.route('/api/alert-rules', methods=['POST'])
def create_alert_rule():
    """Create new alert rule"""
    data = request.json

    if not data.get('name') or not data.get('type') or not data.get('value'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO alert_rules (name, type, value, enabled)
        VALUES (?, ?, ?, ?)
    """, (data['name'], data['type'], data['value'], data.get('enabled', 1)))

    conn.commit()
    rule_id = cur.lastrowid
    conn.close()

    return jsonify({'id': rule_id, 'message': 'Alert rule created'}), 201

@app.route('/api/alert-rules/<int:rule_id>', methods=['PUT'])
def update_alert_rule(rule_id):
    """Update existing alert rule"""
    data = request.json

    conn = get_db()
    cur = conn.cursor()

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if 'name' in data:
        updates.append('name = ?')
        params.append(data['name'])
    if 'type' in data:
        updates.append('type = ?')
        params.append(data['type'])
    if 'value' in data:
        updates.append('value = ?')
        params.append(data['value'])
    if 'enabled' in data:
        updates.append('enabled = ?')
        params.append(data['enabled'])

    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    params.append(rule_id)

    cur.execute(f"""
        UPDATE alert_rules
        SET {', '.join(updates)}
        WHERE id = ?
    """, params)

    conn.commit()
    conn.close()

    return jsonify({'message': 'Alert rule updated'})

@app.route('/api/alert-rules/<int:rule_id>', methods=['DELETE'])
def delete_alert_rule(rule_id):
    """Delete alert rule"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute('DELETE FROM alert_rules WHERE id = ?', (rule_id,))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Alert rule deleted'})

# ============================================================================
# ALERT HISTORY ENDPOINTS
# ============================================================================

@app.route('/api/alert-history', methods=['GET'])
def get_alert_history():
    """Get alert history with optional filters"""
    limit = request.args.get('limit', 50, type=int)
    rule_id = request.args.get('rule_id', type=int)

    conn = get_db()
    cur = conn.cursor()

    query = """
        SELECT
            ah.id,
            ah.rule_id,
            ar.name as rule_name,
            ah.icao_hex,
            ah.callsign,
            ah.aircraft_type,
            ah.squawk,
            ah.altitude,
            ah.lat,
            ah.lon,
            ah.triggered_at,
            ah.sent_push
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.id
    """

    params = []

    if rule_id:
        query += " WHERE ah.rule_id = ?"
        params.append(rule_id)

    query += " ORDER BY ah.triggered_at DESC LIMIT ?"
    params.append(limit)

    history = cur.execute(query, params).fetchall()

    conn.close()

    return jsonify([dict(h) for h in history])

@app.route('/api/alert-history/stats', methods=['GET'])
def get_alert_stats():
    """Get alert statistics"""
    conn = get_db()
    cur = conn.cursor()

    # Total alerts
    total = cur.execute("SELECT COUNT(*) FROM alert_history").fetchone()[0]

    # Alerts by type
    by_type = cur.execute("""
        SELECT ar.type, COUNT(*) as count
        FROM alert_history ah
        JOIN alert_rules ar ON ah.rule_id = ar.id
        GROUP BY ar.type
    """).fetchall()

    # Recent alerts (last 24h)
    recent = cur.execute("""
        SELECT COUNT(*) FROM alert_history
        WHERE triggered_at > datetime('now', '-24 hours')
    """).fetchone()[0]

    conn.close()

    return jsonify({
        'total': total,
        'by_type': [dict(r) for r in by_type],
        'last_24h': recent
    })

# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all settings"""
    conn = get_db()
    cur = conn.cursor()

    settings = cur.execute("SELECT key, value FROM settings").fetchall()

    conn.close()

    # Convert to dict, mask sensitive data
    result = {}
    for s in settings:
        key = s['key']
        value = s['value']

        # Mask API tokens (show only first/last 4 chars)
        if 'token' in key or 'key' in key:
            if len(value) > 8:
                value = value[:4] + '****' + value[-4:]

        result[key] = value

    return jsonify(result)

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """Update settings"""
    data = request.json

    conn = get_db()
    cur = conn.cursor()

    for key, value in data.items():
        cur.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now', 'localtime'))
        """, (key, value))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Settings updated'})

# ============================================================================
# TEST ENDPOINTS
# ============================================================================

@app.route('/api/test-alert', methods=['POST'])
def test_alert():
    """Send test push notification"""
    from alerts import AlertManager

    manager = AlertManager()

    title = "🧪 Test Alert"
    message = f"This is a test notification from your ADSB Alert System.\n\nTime: {datetime.now().strftime('%H:%M:%S')}"

    success = manager.send_pushover(title, message, priority=0)

    if success:
        return jsonify({'message': 'Test alert sent successfully'})
    else:
        return jsonify({'error': 'Failed to send test alert'}), 500

# ============================================================================
# AIRCRAFT ENDPOINTS (for live view)
# ============================================================================

@app.route('/api/aircraft/live', methods=['GET'])
def get_live_aircraft():
    """Get currently visible aircraft (from last 5 minutes)"""
    conn = get_db()
    cur = conn.cursor()

    aircraft = cur.execute("""
        SELECT
            callsign,
            icao_hex,
            airline,
            aircraft_type,
            last_seen,
            max_altitude,
            distance_nm,
            squawk
        FROM aircraft_sightings
        WHERE date = date('now')
        AND last_seen > datetime('now', '-5 minutes')
        ORDER BY last_seen DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return jsonify([dict(a) for a in aircraft])

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Run on all interfaces, port 5000
    # Use debug=True for development only!
    app.run(host='0.0.0.0', port=5000, debug=True)
