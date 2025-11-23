#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script version
VERSION="1.0.0"

# Default values
READSB_MODE="local"
READSB_HOST="localhost"
READSB_PORT="8080"
READSB_PATH="/tar1090/data/aircraft.json"
DB_PATH="$HOME/adsb-stats/adsb.db"
DASHBOARD_OUTPUT_PATH="/var/www/html/adsb-stats/index.html"
LOCATION_NAME=""
RECEIVER_LAT=""
RECEIVER_LON=""
TIMEZONE="Europe/Berlin"

# Print functions
print_header() {
    echo -e "${PURPLE}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║        🛫 ADSB Statistics Tracker - Installer 🛫         ║"
    echo "║                    Version $VERSION                         ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${CYAN}${BOLD}▶ $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root!"
        print_info "Run as a regular user with sudo privileges."
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking Prerequisites"

    local missing=0

    # Check if sudo is available
    if ! command -v sudo &> /dev/null; then
        print_error "sudo is not installed"
        missing=1
    else
        print_success "sudo is available"
    fi

    # Check if we have sudo privileges
    if ! sudo -n true 2>/dev/null; then
        print_info "Testing sudo access (you may be asked for your password)"
        if ! sudo true; then
            print_error "User does not have sudo privileges"
            exit 1
        fi
    fi
    print_success "User has sudo privileges"

    return $missing
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
        print_success "Detected OS: $OS $VER"
    else
        print_error "Cannot detect OS"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    print_step "Installing System Dependencies"

    print_info "Updating package list..."
    sudo apt update -qq

    print_info "Installing packages..."
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-flask \
        python3-flask-cors \
        sqlite3 \
        nginx \
        curl \
        wget \
        cron

    print_success "System dependencies installed"
}

# Test readsb connection
test_readsb_connection() {
    local host=$1
    local port=$2
    local path=$3
    local url="http://${host}:${port}${path}"

    print_info "Testing connection to: $url"

    # Try to fetch data
    if response=$(curl -s -m 5 "$url" 2>/dev/null); then
        # Check if response is valid JSON
        if echo "$response" | python3 -m json.tool &>/dev/null; then
            # Check if it has aircraft array
            if echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if 'aircraft' in data else 1)" 2>/dev/null; then
                local count=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('aircraft', [])))" 2>/dev/null)
                print_success "Connection successful! Found $count aircraft"
                return 0
            fi
        fi
    fi

    return 1
}

# Auto-detect readsb
auto_detect_readsb() {
    print_step "Auto-detecting readsb"

    local hosts=("localhost" "127.0.0.1")
    local ports=("80" "8080" "30003")
    local paths=("/data/aircraft.json" "/tar1090/data/aircraft.json" "/skyaware/data/aircraft.json")

    # Add local network detection if not localhost
    local local_ip=$(hostname -I | awk '{print $1}' 2>/dev/null)
    if [ -n "$local_ip" ]; then
        hosts+=("$local_ip")
    fi

    print_info "Scanning for readsb..."

    for host in "${hosts[@]}"; do
        for port in "${ports[@]}"; do
            for path in "${paths[@]}"; do
                if test_readsb_connection "$host" "$port" "$path"; then
                    READSB_HOST="$host"
                    READSB_PORT="$port"
                    READSB_PATH="$path"
                    if [ "$host" = "localhost" ] || [ "$host" = "127.0.0.1" ]; then
                        READSB_MODE="local"
                        print_success "Found local readsb at port $port"
                    else
                        READSB_MODE="remote"
                        print_success "Found readsb at $host:$port"
                    fi
                    return 0
                fi
            done
        done
    done

    print_warning "Could not auto-detect readsb"
    return 1
}

# Configure readsb
configure_readsb() {
    print_step "Configuring readsb Connection"

    # Try auto-detection first
    if auto_detect_readsb; then
        echo ""
        read -p "Use detected settings? (Y/n): " use_detected
        if [[ ! $use_detected =~ ^[Nn]$ ]]; then
            return 0
        fi
    fi

    # Manual configuration
    echo ""
    echo "Is readsb running locally or on a remote host?"
    echo "1) Local (this machine)"
    echo "2) Remote (another machine)"
    read -p "Select [1/2] (default: 1): " mode_choice

    if [ "$mode_choice" = "2" ]; then
        READSB_MODE="remote"

        # Get host
        read -p "Enter readsb host IP/hostname: " host_input
        READSB_HOST=${host_input:-$READSB_HOST}

        # Get port
        read -p "Enter readsb HTTP port (default: 80): " port_input
        READSB_PORT=${port_input:-80}

        # Get path
        echo ""
        print_info "The aircraft data is available at different paths depending on your setup:"
        echo ""
        echo "  1) /tar1090/data/aircraft.json    (if you use tar1090 - most common)"
        echo "  2) /data/aircraft.json             (if you use plain readsb)"
        echo "  3) /skyaware/data/aircraft.json    (if you use dump1090-fa)"
        echo ""
        read -p "Select [1-3] or enter custom path (default: 1): " path_choice

        case $path_choice in
            2) READSB_PATH="/data/aircraft.json" ;;
            3) READSB_PATH="/skyaware/data/aircraft.json" ;;
            /*) READSB_PATH="$path_choice" ;;
            *) READSB_PATH="/tar1090/data/aircraft.json" ;;
        esac

        # Test connection
        echo ""
        if ! test_readsb_connection "$READSB_HOST" "$READSB_PORT" "$READSB_PATH"; then
            print_error "Cannot connect to readsb at http://${READSB_HOST}:${READSB_PORT}${READSB_PATH}"
            echo ""
            read -p "Continue anyway? (y/N): " continue_anyway
            if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        READSB_MODE="local"
        READSB_HOST="localhost"
        READSB_PORT="8080"
        read -p "Enter path to aircraft.json (default: /run/readsb/aircraft.json): " json_path
        READSB_PATH=${json_path:-/run/readsb/aircraft.json}
    fi
}

# Configure location
configure_location() {
    print_step "Configuring Location"

    echo ""
    print_info "This information is used for the dashboard header and distance calculations."
    echo ""

    read -p "Enter your location name (e.g., Dresden): " location_input
    LOCATION_NAME=${location_input:-"My Location"}

    echo ""
    print_info "Your GPS coordinates are used to calculate the distance to each aircraft."
    print_info "You can find your coordinates at: https://www.google.com/maps"
    echo ""

    # Loop until valid coordinates are provided
    while true; do
        read -p "Enter your latitude (e.g., 51.103895): " lat_input
        if [ -n "$lat_input" ]; then
            RECEIVER_LAT=${lat_input}
            break
        else
            print_error "Latitude is required for distance calculations!"
        fi
    done

    while true; do
        read -p "Enter your longitude (e.g., 13.675288): " lon_input
        if [ -n "$lon_input" ]; then
            RECEIVER_LON=${lon_input}
            break
        else
            print_error "Longitude is required for distance calculations!"
        fi
    done

    print_success "Coordinates set: $RECEIVER_LAT, $RECEIVER_LON"

    # Timezone
    echo ""
    print_info "Select your timezone for correct time display:"
    echo ""
    echo "  1) Europe/Berlin       (Germany, most of Central Europe)"
    echo "  2) Europe/London       (UK, Ireland, Portugal)"
    echo "  3) America/New_York    (US East Coast)"
    echo "  4) America/Los_Angeles (US West Coast)"
    echo "  5) America/Chicago     (US Central)"
    echo "  6) UTC                 (Universal Time)"
    echo "  7) Other (enter manually)"
    echo ""
    read -p "Select [1-7] (default: 1): " tz_choice

    case $tz_choice in
        2) TIMEZONE="Europe/London" ;;
        3) TIMEZONE="America/New_York" ;;
        4) TIMEZONE="America/Los_Angeles" ;;
        5) TIMEZONE="America/Chicago" ;;
        6) TIMEZONE="UTC" ;;
        7)
            read -p "Enter timezone (e.g., Asia/Tokyo): " tz_input
            TIMEZONE=${tz_input:-Europe/Berlin}
            ;;
        *) TIMEZONE="Europe/Berlin" ;;
    esac

    print_success "Selected timezone: $TIMEZONE"
}

# Configure paths
configure_paths() {
    print_step "Configuring Paths"

    echo ""
    print_info "The default paths work for most installations."
    print_info "Just press ENTER to use the defaults, or enter a custom path."
    echo ""

    read -p "Database path (default: $HOME/adsb-stats/adsb.db): " db_input
    DB_PATH=${db_input:-$HOME/adsb-stats/adsb.db}
    print_success "Using: $DB_PATH"

    echo ""
    read -p "Dashboard output path (default: /var/www/html/adsb-stats/index.html): " dashboard_input
    DASHBOARD_OUTPUT_PATH=${dashboard_input:-/var/www/html/adsb-stats/index.html}
    print_success "Using: $DASHBOARD_OUTPUT_PATH"
}

# Generate config file
generate_config() {
    print_step "Generating Configuration File"

    local config_file="$(pwd)/config.py"

    # Build READSB_URL for remote mode
    local readsb_url=""
    if [ "$READSB_MODE" = "remote" ]; then
        readsb_url="http://${READSB_HOST}:${READSB_PORT}${READSB_PATH}"
    fi

    # Build TAR1090_PATH (with trailing slash for query parameters)
    local tar1090_path=""
    if [ "$READSB_MODE" = "remote" ]; then
        tar1090_path="http://${READSB_HOST}:${READSB_PORT}/tar1090/"
    else
        tar1090_path="/tar1090/"
    fi

    cat > "$config_file" << EOF
#!/usr/bin/env python3
"""
ADSB Statistics Tracker - Configuration
Generated by install.sh on $(date)
"""

# ============================================
# BASIC CONFIGURATION
# ============================================

LOCATION_NAME = "$LOCATION_NAME"
RECEIVER_LAT = $RECEIVER_LAT
RECEIVER_LON = $RECEIVER_LON

# ============================================
# READSB CONFIGURATION
# ============================================

READSB_MODE = "$READSB_MODE"
READSB_URL = "$readsb_url"
AIRCRAFT_JSON_PATH = "$READSB_PATH"

# ============================================
# DATABASE CONFIGURATION
# ============================================

DB_PATH = "$DB_PATH"

# ============================================
# WEB SERVER CONFIGURATION
# ============================================

DASHBOARD_OUTPUT_PATH = "$DASHBOARD_OUTPUT_PATH"
PUBLIC_URL = None
TAR1090_PATH = "$tar1090_path"

# ============================================
# TIMEZONE CONFIGURATION
# ============================================

TIMEZONE = "$TIMEZONE"

# ============================================
# STATISTICS CONFIGURATION
# ============================================

AVERAGE_DAYS = 7
CHART_DAYS = 14
TOP_N = 10
ROLLING_24H_TOP_N = 7

# ============================================
# ADVANCED CONFIGURATION
# ============================================

MIN_ALTITUDE = None
MAX_RANGE_KM = None

# ============================================
# DASHBOARD CUSTOMIZATION
# ============================================

DASHBOARD_TITLE = f"✈️ ADSB Statistics {LOCATION_NAME}"
PRIMARY_COLOR = "#667eea"
SECONDARY_COLOR = "#764ba2"
EOF

    print_success "Configuration file created: $config_file"
}

# Install Python dependencies
install_python_deps() {
    print_step "Installing Python Dependencies"

    print_info "Installing packages..."
    pip3 install -r requirements.txt --break-system-packages --quiet

    print_success "Python dependencies installed"
}

# Setup database
setup_database() {
    print_step "Setting Up Database"

    # Create database directory
    local db_dir=$(dirname "$DB_PATH")
    mkdir -p "$db_dir"
    print_success "Created database directory: $db_dir"

    # Create database and tables
    print_info "Creating database tables..."
    sqlite3 "$DB_PATH" < schema.sql
    sqlite3 "$DB_PATH" < schema_routes.sql
    sqlite3 "$DB_PATH" < alerts_schema.sql

    print_success "Database created: $DB_PATH"

    # Test database
    local tables=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM sqlite_master WHERE type='table';")
    print_info "Created $tables tables"
}

# Setup web server
setup_webserver() {
    print_step "Setting Up Web Server"

    # Create web directory
    local web_dir=$(dirname "$DASHBOARD_OUTPUT_PATH")
    sudo mkdir -p "$web_dir"
    sudo chown $USER:www-data "$web_dir"
    print_success "Created web directory: $web_dir"

    # Check nginx config
    if ! sudo nginx -t &>/dev/null; then
        print_warning "Nginx configuration test failed"
    fi

    # Start/restart nginx
    sudo systemctl enable nginx
    sudo systemctl restart nginx
    print_success "Nginx enabled and started"
}

# Setup alert system
setup_alerts() {
    print_step "Setting Up Alert System"

    local script_dir="$(pwd)"
    local web_dir=$(dirname "$DASHBOARD_OUTPUT_PATH")

    # Copy alerts.html to web directory
    if [ -f "$script_dir/alerts.html" ]; then
        cp "$script_dir/alerts.html" "$web_dir/"
        print_success "Copied alerts.html to $web_dir/"
    else
        print_warning "alerts.html not found, skipping..."
    fi

    # Initialize alert database tables
    if [ -f "$script_dir/setup_alerts.py" ]; then
        print_info "Initializing alert system database..."
        python3 "$script_dir/setup_alerts.py" "$DB_PATH" &>/dev/null
        print_success "Alert system initialized"
    else
        print_warning "setup_alerts.py not found, skipping..."
    fi

    print_info ""
    print_info "To use alerts, you need to:"
    print_info "1. Configure Pushover credentials in the web UI"
    print_info "2. Start the API server: python3 api.py"
    print_info "3. Access alerts at: http://YOUR_IP/adsb-stats/alerts.html"
}

# Setup cron jobs
setup_cron() {
    print_step "Setting Up Cron Jobs"

    local script_dir="$(pwd)"
    local collect_script="$script_dir/collect_remote.py"
    local dashboard_script="$script_dir/generate_dashboard.py"

    # Use collect_remote.py if it exists, otherwise collect.py
    if [ ! -f "$collect_script" ]; then
        collect_script="$script_dir/collect.py"
    fi

    # Create cron job entries
    local cron_collect="* * * * * /usr/bin/python3 $collect_script >> $HOME/adsb-stats/collect.log 2>&1"
    local cron_dashboard="*/10 * * * * /usr/bin/python3 $dashboard_script >> $HOME/adsb-stats/dashboard.log 2>&1"

    # Check if cron jobs already exist
    if crontab -l 2>/dev/null | grep -q "$collect_script"; then
        print_info "Cron jobs already exist, skipping..."
    else
        # Add cron jobs
        (crontab -l 2>/dev/null; echo "$cron_collect"; echo "$cron_dashboard") | crontab -
        print_success "Cron jobs installed"
        print_info "  - Data collection: every minute"
        print_info "  - Dashboard generation: every 10 minutes"
    fi
}

# Test installation
test_installation() {
    print_step "Testing Installation"

    # Test data collection
    print_info "Testing data collection..."
    if [ "$READSB_MODE" = "remote" ]; then
        if python3 collect_remote.py 2>&1 | grep -q "Collected"; then
            print_success "Data collection test passed"
        else
            print_error "Data collection test failed"
            return 1
        fi
    else
        if python3 collect.py 2>&1 | grep -q "Collected"; then
            print_success "Data collection test passed"
        else
            print_error "Data collection test failed"
            return 1
        fi
    fi

    # Test dashboard generation
    print_info "Testing dashboard generation..."
    if python3 generate_dashboard.py 2>&1 | grep -q "Dashboard generated"; then
        print_success "Dashboard generation test passed"

        # Check if file was created
        if [ -f "$DASHBOARD_OUTPUT_PATH" ]; then
            local size=$(du -h "$DASHBOARD_OUTPUT_PATH" | cut -f1)
            print_success "Dashboard file created: $size"
        fi
    else
        print_error "Dashboard generation test failed"
        return 1
    fi

    return 0
}

# Print summary
print_summary() {
    local local_ip=$(hostname -I | awk '{print $1}')
    local dashboard_url="http://${local_ip}/adsb-stats/"

    echo ""
    print_header
    echo -e "${GREEN}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║           ✓ Installation Complete! ✓                     ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo -e "${BOLD}Configuration Summary:${NC}"
    echo -e "  ${CYAN}Mode:${NC}              $READSB_MODE"
    if [ "$READSB_MODE" = "remote" ]; then
        echo -e "  ${CYAN}readsb URL:${NC}        http://${READSB_HOST}:${READSB_PORT}${READSB_PATH}"
    fi
    echo -e "  ${CYAN}Database:${NC}          $DB_PATH"
    echo -e "  ${CYAN}Dashboard:${NC}         $DASHBOARD_OUTPUT_PATH"
    echo ""

    echo -e "${BOLD}Access Your Dashboard:${NC}"
    echo -e "  ${GREEN}$dashboard_url${NC}"
    echo ""

    echo -e "${BOLD}Next Steps:${NC}"
    echo -e "  1. Wait ~1 minute for first data collection"
    echo -e "  2. Dashboard updates every 10 minutes automatically"
    echo -e "  3. View logs: ${CYAN}tail -f ~/adsb-stats/collect.log${NC}"
    echo ""

    echo -e "${BOLD}Useful Commands:${NC}"
    echo -e "  ${CYAN}# Manual data collection${NC}"
    echo -e "  python3 $PWD/collect_remote.py"
    echo ""
    echo -e "  ${CYAN}# Manual dashboard generation${NC}"
    echo -e "  python3 $PWD/generate_dashboard.py"
    echo ""
    echo -e "  ${CYAN}# View database${NC}"
    echo -e "  sqlite3 $DB_PATH"
    echo ""

    print_success "Happy tracking! ✈️"
    echo ""
}

# Main installation flow
main() {
    print_header

    check_root
    check_prerequisites
    detect_os

    install_dependencies
    configure_readsb
    configure_location
    configure_paths

    generate_config
    install_python_deps
    setup_database
    setup_webserver
    setup_alerts
    setup_cron

    if test_installation; then
        print_summary
    else
        print_error "Installation completed with errors"
        print_info "Check the logs for more details"
        exit 1
    fi
}

# Run main
main
