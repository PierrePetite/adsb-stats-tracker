# ADSB Statistics Tracker 📡✈️

A comprehensive statistics system for tracking aircraft via ADS-B receivers (readsb/tar1090). Collects flight data, generates beautiful dashboards, provides detailed analytics, and supports **both local and remote installations**.

Perfect for running on a **separate machine** (like Proxmox LXC, VPS, or dedicated server) while pulling data from your ADS-B receiver remotely!

## ✨ Features

- 📊 **Real-time Statistics Dashboard** with Chart.js visualizations
- ✈️ **Flight Tracking** - Tracks all aircraft with position data
- 📈 **Hourly Analysis** - Expected vs. actual flight patterns
- 🏢 **Airline Statistics** - Top airlines (7 days, today, last 24h)
- 🛫 **Aircraft Type Analysis** - Most common aircraft types
- 🌍 **Airport Statistics** - Top 10 airports (origin/destination)
- 🛣️ **Route Tracking** - Automatic route lookup with caching
- 🚨 **Alert System** - Get notified for emergency squawk codes, specific aircraft, or callsigns
- 📅 **Historical Data** - Daily flight counts and trends
- 🔄 **Rolling 24h Charts** - Multi-line charts for airlines and aircraft types
- 🌐 **Remote Support** - Run dashboard on separate machine, pull data from remote ADS-B receiver
- 🔗 **tar1090 Integration** - Clickable links to historical tracks

## 🚀 Quick Install (One-Liner)

**Easy installation with interactive setup:**

```bash
curl -sSL https://raw.githubusercontent.com/PierrePetite/adsb-stats-tracker/main/install.sh | bash
```

Or safer (two-step):

```bash
wget https://raw.githubusercontent.com/PierrePetite/adsb-stats-tracker/main/install.sh
chmod +x install.sh
./install.sh
```

The installer will:
- ✅ Auto-detect your readsb installation (local or remote)
- ✅ Guide you through interactive setup
- ✅ Install all dependencies
- ✅ Create database and configure everything
- ✅ Set up cron jobs for automatic data collection
- ✅ Test the installation
- ✅ Show you the dashboard URL

## 📋 Prerequisites

Before running the installer, make sure you have:

### For Local Installation (readsb on same machine):
- Raspberry Pi or Linux machine with **readsb** and **tar1090** running
- SSH access with sudo privileges
- Internet connection

### For Remote Installation (recommended for LXC/VPS):
- Separate machine (Proxmox LXC, VPS, Docker container, etc.)
- Network access to your ADS-B receiver
- Your ADS-B receiver must have **tar1090 web interface** accessible via HTTP
- Example: `http://your-pi-ip/tar1090/` should be accessible

**Supported Systems:**
- Debian 11/12
- Ubuntu 20.04/22.04/24.04
- Raspberry Pi OS

## 🎯 Installation Scenarios

### Scenario 1: All-in-One (Raspberry Pi)
Install directly on your Raspberry Pi that runs readsb:

```bash
ssh pi@your-pi-ip
curl -sSL https://raw.githubusercontent.com/PierrePetite/adsb-stats-tracker/main/install.sh | bash
```

Select **"Local"** when asked about readsb location.

### Scenario 2: Separate Stats Server (Recommended)
Run the dashboard on a separate machine (LXC, VPS, etc.) and pull data remotely:

**Example: Proxmox LXC Container**

1. Create LXC container (Debian 12, 1 vCPU, 512MB RAM, 8GB storage)
2. Start container and get shell access
3. Run installer:

```bash
curl -sSL https://raw.githubusercontent.com/PierrePetite/adsb-stats-tracker/main/install.sh | bash
```

4. Select **"Remote"** when asked
5. Enter your Raspberry Pi's IP address (e.g., `192.168.1.100`)
6. The installer will auto-detect the correct path

**Benefits of Remote Installation:**
- 📊 Centralized stats server for multiple ADS-B receivers
- 🔒 Keep ADS-B receiver isolated, stats server in DMZ
- 💪 Better performance (dedicated resources)
- 🔄 Easy backups and updates
- 🚀 No load on your Raspberry Pi

## 🛠️ Manual Installation

If you prefer manual installation or want more control:

### 1. Clone Repository

```bash
git clone https://github.com/PierrePetite/adsb-stats-tracker.git
cd adsb-stats-tracker
```

### 2. Run Interactive Installer

```bash
chmod +x install.sh
./install.sh
```

The installer will guide you through:
- readsb detection (local/remote)
- Location and GPS coordinates setup
- Timezone configuration
- Path configuration
- Dependency installation
- Database setup
- Web server configuration
- Cron job setup

### 3. Access Dashboard

After installation completes, access your dashboard at:

```
http://your-server-ip/adsb-stats/
```

## 📊 Dashboard Features

### Statistics Cards
- **Today**: Total flights seen today
- **Average**: Average flights per day
- **Max Distance**: Furthest aircraft tracked (in nautical miles)

### Charts & Visualizations
1. **Hourly Traffic** - Expected vs. Today (shows if today is busier than usual)
2. **Flights per Day** - 14-day trend
3. **Top Airlines Today** - List + Pie chart
4. **Top Aircraft Types Today** - List + Pie chart
5. **Top 10 Airports** - Most frequent origin/destination airports
6. **Rolling 24h Charts** - Multi-line charts showing airline/aircraft trends
7. **Rarest Airlines & Aircraft** - Rarely seen visitors
8. **All Flights Table** - Searchable table with all flights

### Interactive Features
- 🔍 **Search** - Filter flights by callsign, airline, aircraft type, or route
- 🗺️ **tar1090 Links** - Click any callsign to view historical track
- 📄 **Flight Details** - Click "Details" button to see all flights for airline/aircraft/airport
- 🛣️ **Route Information** - Hover over routes to see full airport names

## 🚨 Alert System

Get notified via Pushover for:
- Emergency squawk codes (7700, 7600, 7500)
- Specific callsigns (track a particular flight)
- Aircraft types (e.g., get alerted when A380 appears)

**Manage alerts via web UI:**

```
http://your-server-ip:5000/
```

See [ALERTS_README.md](ALERTS_README.md) for detailed alert setup.

## 🔧 Configuration

After installation, you can modify settings in `config.py`:

```python
# Location
LOCATION_NAME = "Dresden"
RECEIVER_LAT = 51.103895
RECEIVER_LON = 13.675288

# Remote readsb
READSB_MODE = "remote"
READSB_URL = "http://192.168.1.100/tar1090/data/aircraft.json"

# Paths
DB_PATH = "/home/user/adsb-stats/adsb.db"
DASHBOARD_OUTPUT_PATH = "/var/www/html/adsb-stats/index.html"

# Timezone
TIMEZONE = "Europe/Berlin"
```

## 📈 Usage

### Automatic Updates (via Cron)

The installer sets up automatic cron jobs:
- **Data collection**: Every minute
- **Dashboard generation**: Every 10 minutes

### Manual Commands

```bash
# Collect data manually
python3 collect_remote.py

# Generate dashboard manually
python3 generate_dashboard.py

# View database
sqlite3 ~/adsb-stats/adsb.db "SELECT * FROM aircraft_sightings LIMIT 10;"
```

### Logs

```bash
# View collection log
tail -f ~/adsb-stats/collect.log

# View dashboard generation log
tail -f ~/adsb-stats/dashboard.log
```

## 🗄️ Database

The system uses SQLite with three main tables:

- **aircraft_sightings** - All flight data (callsign, airline, aircraft type, times, altitudes, distance)
- **route_cache** - Cached route information (origin/destination airports, refreshed every 7 days)
- **alert_rules** - Alert configuration

### Storage Requirements

- **Per day**: ~250 KB (based on ~400 flights/day)
- **Per month**: ~7.5 MB
- **Per year**: ~90 MB

Very efficient for long-term storage!

## 🔄 Updates

To update to the latest version:

```bash
cd ~/adsb-stats-tracker
git pull
python3 generate_dashboard.py
```

To apply new database migrations (if any):

```bash
# Check migration files
ls migration_*.sql

# Apply manually if needed
sqlite3 ~/adsb-stats/adsb.db < migration_add_routes.sql
```

## 🐛 Troubleshooting

### No data being collected

```bash
# Check if readsb is reachable
curl http://192.168.1.100/tar1090/data/aircraft.json | head

# Check collection logs
tail -f ~/adsb-stats/collect.log

# Test collection manually
python3 collect_remote.py
```

### Dashboard not updating

```bash
# Check dashboard generation
python3 generate_dashboard.py

# Check cron jobs
crontab -l

# Check nginx status
sudo systemctl status nginx
```

### Connection issues (remote mode)

```bash
# Test connectivity
ping 192.168.1.100

# Test HTTP access
curl -I http://192.168.1.100/tar1090/

# Check firewall
sudo iptables -L
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Credits

- Built for tracking aircraft via **readsb** and **tar1090**
- Uses **Chart.js** for beautiful visualizations
- Route data from **adsbdb.com** API
- Inspired by the amazing ADS-B community

## 💬 Support

- 🐛 **Bug reports**: [GitHub Issues](https://github.com/PierrePetite/adsb-stats-tracker/issues)
- 💡 **Feature requests**: [GitHub Issues](https://github.com/PierrePetite/adsb-stats-tracker/issues)
- ⭐ **Star the repo** if you find it useful!

## 📸 Screenshots

### Main Dashboard
Beautiful, responsive dashboard with real-time statistics

### Hourly Analysis
Compare today's traffic with historical averages

### Top Airlines & Aircraft
Interactive charts and detailed flight lists

### Route Tracking
Automatic route lookup with origin/destination airports

---

Made with ❤️ for the ADS-B tracking community

🛫 Happy Tracking! ✈️
