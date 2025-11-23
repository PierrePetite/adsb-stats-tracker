#!/bin/bash
# Installation script for ADSB Alert System on Raspberry Pi
# Run this on your Mac to copy all files to the Pi

PI_USER="pi"
PI_HOST="192.168.1.100"
PI_PATH="/home/pi/adsb-stats"

echo "🚀 Installing ADSB Alert System on Raspberry Pi..."

# Copy all necessary files
echo "📦 Copying files..."
scp alerts.py ${PI_USER}@${PI_HOST}:${PI_PATH}/
scp alerts_schema.sql ${PI_USER}@${PI_HOST}:${PI_PATH}/
scp setup_alerts.py ${PI_USER}@${PI_HOST}:${PI_PATH}/
scp collect.py ${PI_USER}@${PI_HOST}:${PI_PATH}/
scp migration_add_squawk.sql ${PI_USER}@${PI_HOST}:${PI_PATH}/

echo "✅ Files copied!"
echo ""
echo "Next steps on the Pi:"
echo "1. ssh ${PI_USER}@${PI_HOST}"
echo "2. cd ${PI_PATH}"
echo "3. python3 setup_alerts.py adsb.db"
echo "4. Configure Pushover credentials"
echo "5. Test: python3 alerts.py"
