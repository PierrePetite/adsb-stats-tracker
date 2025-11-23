# Alert System Setup 🚨

Real-time push notifications for aircraft events!

## Quick Links

- **Web Interface**: http://your-pi-ip/adsb-stats/alerts.html
- **API**: http://your-pi-ip:5000/api
- **Dashboard**: http://your-pi-ip/adsb-stats/

## Features

- **Squawk Code Alerts**: Get notified on 7700 (Emergency), 7600 (Radio Failure), 7500 (Hijack)
- **Custom Callsign Alerts**: Track specific flights (e.g., "DLH400", "UAL123")
- **Aircraft Type Alerts**: Get notified when rare aircraft appear (e.g., A380, B748)
- **Pushover Integration**: Instant push notifications to your phone
- **Smart Throttling**: Prevents spam (30-minute cooldown per alert)

## Installation

### 0. Install Python Dependencies

```bash
cd /home/pi/adsb-stats-tracker
pip3 install -r requirements.txt
```

### 1. Setup Database

```bash
cd /home/pi/adsb-stats-tracker
python3 setup_alerts.py /home/pi/adsb-stats/adsb.db
```

### 2. Configure Pushover

Get your credentials from https://pushover.net/

```bash
sqlite3 /home/pi/adsb-stats/adsb.db

UPDATE settings SET value='YOUR_USER_KEY' WHERE key='pushover_user_key';
UPDATE settings SET value='YOUR_API_TOKEN' WHERE key='pushover_api_token';
.quit
```

### 3. Copy Files to Pi

```bash
scp alerts.py pi@192.168.1.100:/home/pi/adsb-stats/
scp collect.py pi@192.168.1.100:/home/pi/adsb-stats/
```

### 4. Start API Server

```bash
# Run in background
nohup python3 /home/pi/adsb-stats/api.py > /home/pi/adsb-stats/api.log 2>&1 &
```

Or create systemd service for auto-start:

```bash
sudo nano /etc/systemd/system/adsb-api.service
```

Content:
```ini
[Unit]
Description=ADSB Stats API
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/adsb-stats
ExecStart=/usr/bin/python3 /home/pi/adsb-stats/api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable adsb-api
sudo systemctl start adsb-api
sudo systemctl status adsb-api
```

### 5. Copy alerts.html to web directory

```bash
sudo cp /home/pi/adsb-stats-tracker/alerts.html /var/www/html/adsb-stats/
```

### 6. Test

Open in browser: `http://192.168.1.100/adsb-stats/alerts.html`

Or test via command line:
```bash
python3 alerts.py
```

If configured correctly, you should see "Pushover not configured" or test alerts.

## Usage

### Web Interface (Recommended)

Open `http://192.168.1.100/adsb-stats/alerts.html` in your browser to:
- Create, edit, and delete alert rules
- View alert history
- Configure Pushover settings
- Send test notifications

### Command Line (Alternative)

#### View Active Alert Rules

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "SELECT * FROM alert_rules WHERE enabled=1"
```

#### Add Alert Rule for A380

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "INSERT INTO alert_rules (name, type, value) VALUES ('A380 Spotted!', 'aircraft_type', 'A388')"
```

#### Add Alert for Specific Flight

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "INSERT INTO alert_rules (name, type, value) VALUES ('My Flight DLH400', 'callsign', 'DLH400')"
```

#### Add Alert for Squawk 7600

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "INSERT INTO alert_rules (name, type, value) VALUES ('Radio Failure - 7600', 'squawk', '7600')"
```

#### Disable an Alert

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "UPDATE alert_rules SET enabled=0 WHERE id=1"
```

#### View Alert History

```bash
sqlite3 /home/pi/adsb-stats/adsb.db "SELECT * FROM alert_history ORDER BY triggered_at DESC LIMIT 10"
```

## How It Works

1. **collect.py** runs every minute (via cron)
2. Reads all visible aircraft from readsb
3. Checks each aircraft against active alert rules
4. If match found:
   - Checks if alert was recently triggered (30min cooldown)
   - Sends Pushover notification
   - Logs to alert_history table

## Alert Types

### Squawk Codes

```python
type: 'squawk'
value: '7700'  # Emergency
value: '7600'  # Radio Failure
value: '7500'  # Hijack
```

### Callsigns (Partial Match)

```python
type: 'callsign'
value: 'DLH'     # Matches all Lufthansa flights
value: 'DLH400'  # Matches specific flight
```

### Aircraft Types (Exact Match)

```python
type: 'aircraft_type'
value: 'A388'  # Airbus A380-800
value: 'B748'  # Boeing 747-8
value: 'CONC'  # Concorde (if only!)
```

## Pushover Message Format

**Title:** 🚨 Alert: {Rule Name}

**Message:**
```
Aircraft: DLH400 (A388)
ICAO: 3C6647
Squawk: 7700
Altitude: 35000 ft

Triggered: 14:32:15
```

**Priority:** High (1)
**Sound:** Siren

## Troubleshooting

### No alerts received

1. Check Pushover credentials:
   ```bash
   sqlite3 /home/pi/adsb-stats/adsb.db "SELECT * FROM settings WHERE key LIKE 'pushover%'"
   ```

2. Check if alerts are enabled:
   ```bash
   sqlite3 /home/pi/adsb-stats/adsb.db "SELECT * FROM settings WHERE key='alerts_enabled'"
   ```

3. Check alert rules:
   ```bash
   sqlite3 /home/pi/adsb-stats/adsb.db "SELECT * FROM alert_rules"
   ```

4. Check collect.py logs:
   ```bash
   tail -50 /home/pi/adsb-stats/collect.log
   ```

### Too many alerts

Increase cooldown period in `alerts.py`:
```python
def was_recently_triggered(self, rule_id, icao_hex, minutes=30):  # Change 30 to 60
```

## Examples

### Monitor for Long-Haul Flights

```sql
INSERT INTO alert_rules (name, type, value) VALUES
  ('B777 Spotted', 'aircraft_type', 'B77W'),
  ('B787 Dreamliner', 'aircraft_type', 'B788'),
  ('A350 Spotted', 'aircraft_type', 'A359');
```

### Track Friend's Flight

```sql
INSERT INTO alert_rules (name, type, value) VALUES
  ('John arriving from NYC', 'callsign', 'UAL960');
```

### Emergency Monitoring

```sql
INSERT INTO alert_rules (name, type, value) VALUES
  ('Emergency - 7700', 'squawk', '7700'),
  ('Radio Failure - 7600', 'squawk', '7600'),
  ('Hijack - 7500', 'squawk', '7500');
```

## API Endpoints

The Flask API provides the following endpoints:

- `GET /api/alert-rules` - Get all alert rules
- `POST /api/alert-rules` - Create new alert rule
- `PUT /api/alert-rules/{id}` - Update alert rule
- `DELETE /api/alert-rules/{id}` - Delete alert rule
- `GET /api/alert-history` - Get alert history
- `GET /api/alert-history/stats` - Get alert statistics
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings
- `POST /api/test-alert` - Send test notification

## Future Features

- ✅ **Web UI for managing alerts** (DONE!)
- Email notifications
- Telegram bot integration
- Distance-based alerts ("Alert when aircraft >200 NM")
- Time-based alerts ("Only alert between 6am-10pm")

---

Made with ❤️ for the ADSB community
