#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime, timedelta
import os
import sys

# Try to import config, fall back to defaults if not found
try:
    from config import (
        TIMEZONE, DB_PATH, DASHBOARD_OUTPUT_PATH,
        LOCATION_NAME, PUBLIC_URL, TAR1090_PATH,
        AVERAGE_DAYS, CHART_DAYS, TOP_N, ROLLING_24H_TOP_N,
        DASHBOARD_TITLE, PRIMARY_COLOR, SECONDARY_COLOR
    )
except ImportError:
    print("⚠️  config.py not found! Using default configuration.")
    print("   Copy config.py.example to config.py and adjust settings.")
    TIMEZONE = "Europe/Berlin"
    DB_PATH = "/home/YOUR_USER/adsb-stats/adsb.db"
    DASHBOARD_OUTPUT_PATH = "/var/www/html/adsb-stats/index.html"
    LOCATION_NAME = "Your Location"
    PUBLIC_URL = None
    TAR1090_PATH = "/tar1090/"
    AVERAGE_DAYS = 7
    CHART_DAYS = 14
    TOP_N = 10
    ROLLING_24H_TOP_N = 7
    DASHBOARD_TITLE = f"✈️ ADSB Statistics {LOCATION_NAME}"
    PRIMARY_COLOR = "#667eea"
    SECONDARY_COLOR = "#764ba2"

# Set timezone
os.environ['TZ'] = TIMEZONE

# Backwards compatibility aliases
DB = DB_PATH
OUTPUT = DASHBOARD_OUTPUT_PATH

def get_stats():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    total_today = cur.execute("SELECT COUNT(*) FROM aircraft_sightings WHERE date=?", (today,)).fetchone()[0]
    total_all = cur.execute("SELECT COUNT(*) FROM aircraft_sightings").fetchone()[0]
    days = cur.execute("SELECT COUNT(DISTINCT date) FROM aircraft_sightings").fetchone()[0]
    avg_per_day = total_all / days if days > 0 else 0

    # Max distance today
    max_distance_today = cur.execute("SELECT MAX(distance_nm) FROM aircraft_sightings WHERE date=?", (today,)).fetchone()[0]
    max_distance_today = round(max_distance_today, 1) if max_distance_today else 0

    flights_per_day = cur.execute("SELECT date, COUNT(*) FROM aircraft_sightings WHERE date >= date('now', '-14 days') GROUP BY date ORDER BY date").fetchall()

    # Top airlines today (for both list and chart)
    top_airlines_today = cur.execute("SELECT airline, COUNT(*) as cnt FROM aircraft_sightings WHERE date = ? AND airline IS NOT NULL GROUP BY airline ORDER BY cnt DESC LIMIT 10", (today,)).fetchall()

    top_aircraft_today = cur.execute("SELECT aircraft_type, COUNT(*) as cnt FROM aircraft_sightings WHERE date = ? AND aircraft_type != '' GROUP BY aircraft_type ORDER BY cnt DESC LIMIT 10", (today,)).fetchall()

    # Get detailed flights for each aircraft type (for modal) with route info
    aircraft_flights = {}
    for aircraft_type, _ in top_aircraft_today:
        flights = cur.execute("""
            SELECT
                a.callsign, a.aircraft_type, a.first_seen, a.distance_nm, a.airline,
                r.origin_iata, r.destination_iata, r.origin_name, r.destination_name
            FROM aircraft_sightings a
            LEFT JOIN route_cache r ON a.callsign = r.callsign
            WHERE a.date = ? AND a.aircraft_type = ?
            ORDER BY a.first_seen DESC
        """, (today, aircraft_type)).fetchall()
        aircraft_flights[aircraft_type] = flights

    # Get detailed flights for each airline (for modal) with route info
    airline_flights = {}
    for airline, _ in top_airlines_today:
        flights = cur.execute("""
            SELECT
                a.callsign, a.aircraft_type, a.first_seen, a.distance_nm, a.airline,
                r.origin_iata, r.destination_iata, r.origin_name, r.destination_name
            FROM aircraft_sightings a
            LEFT JOIN route_cache r ON a.callsign = r.callsign
            WHERE a.date = ? AND a.airline = ?
            ORDER BY a.first_seen DESC
        """, (today, airline)).fetchall()
        airline_flights[airline] = flights

    # All flights today for searchable table
    all_flights_today = cur.execute("""
        SELECT
            a.callsign, a.icao_hex, a.airline, a.aircraft_type,
            a.first_seen, a.last_seen, a.min_altitude, a.max_altitude, a.distance_nm,
            r.origin_iata, r.destination_iata, r.origin_name, r.destination_name
        FROM aircraft_sightings a
        LEFT JOIN route_cache r ON a.callsign = r.callsign
        WHERE a.date = ?
        ORDER BY a.first_seen DESC
    """, (today,)).fetchall()

    # Top 10 Airports (origin or destination) today
    top_airports_today = cur.execute("""
        SELECT airport_iata, airport_name, COUNT(*) as cnt
        FROM (
            SELECT r.origin_iata as airport_iata, r.origin_name as airport_name
            FROM aircraft_sightings a
            JOIN route_cache r ON a.callsign = r.callsign
            WHERE a.date = ? AND r.origin_iata IS NOT NULL
            UNION ALL
            SELECT r.destination_iata as airport_iata, r.destination_name as airport_name
            FROM aircraft_sightings a
            JOIN route_cache r ON a.callsign = r.callsign
            WHERE a.date = ? AND r.destination_iata IS NOT NULL
        )
        GROUP BY airport_iata, airport_name
        ORDER BY cnt DESC
        LIMIT 10
    """, (today, today)).fetchall()

    # Get detailed flights for each airport (for modal)
    airport_flights = {}
    for airport_iata, airport_name, _ in top_airports_today:
        flights = cur.execute("""
            SELECT DISTINCT
                a.callsign, a.aircraft_type, a.first_seen, a.distance_nm, a.airline,
                r.origin_iata, r.destination_iata, r.origin_name, r.destination_name
            FROM aircraft_sightings a
            JOIN route_cache r ON a.callsign = r.callsign
            WHERE a.date = ?
            AND (r.origin_iata = ? OR r.destination_iata = ?)
            ORDER BY a.first_seen DESC
        """, (today, airport_iata, airport_iata)).fetchall()
        airport_flights[airport_iata] = flights

    # Rarest airlines (seen only once or twice, all time)
    rarest_airlines = cur.execute("""
        SELECT airline, COUNT(*) as cnt
        FROM aircraft_sightings
        WHERE airline IS NOT NULL
        GROUP BY airline
        HAVING cnt <= 3
        ORDER BY cnt ASC, airline ASC
        LIMIT 5
    """).fetchall()

    # Rarest aircraft types (seen only once or twice, all time)
    # Include callsigns for tooltip
    rarest_aircraft = cur.execute("""
        SELECT aircraft_type, COUNT(*) as cnt, GROUP_CONCAT(callsign, ', ') as callsigns
        FROM aircraft_sightings
        WHERE aircraft_type != ''
        GROUP BY aircraft_type
        HAVING cnt <= 3
        ORDER BY cnt ASC, aircraft_type ASC
        LIMIT 5
    """).fetchall()

    # Hourly average (all past days WITHOUT today)
    hourly_avg = cur.execute("""
        SELECT CAST(strftime('%H', first_seen) AS INTEGER) as hour,
               CAST(COUNT(*) AS REAL) / COUNT(DISTINCT date) as avg_count
        FROM aircraft_sightings
        WHERE date < date('now')
        GROUP BY hour
        ORDER BY hour
    """).fetchall()

    # Today per hour
    hourly_today = cur.execute("""
        SELECT CAST(strftime('%H', first_seen) AS INTEGER) as hour,
               COUNT(*) as count
        FROM aircraft_sightings
        WHERE date = ?
        GROUP BY hour
        ORDER BY hour
    """, (today,)).fetchall()

    # Create 24-hour arrays (00-23)
    hourly_avg_data = [0] * 24
    hourly_today_data = [0] * 24

    for hour, count in hourly_avg:
        hourly_avg_data[hour] = round(count, 1)

    for hour, count in hourly_today:
        hourly_today_data[hour] = count

    # Airlines per hour (rolling 24h)
    hours_24h = []
    now = datetime.now()
    for i in range(24):
        h = (now - timedelta(hours=23-i)).strftime('%Y-%m-%d %H:00')
        hours_24h.append(h)

    # Top 7 Airlines last 24h
    top_airlines_24h = cur.execute("""
        SELECT airline, COUNT(*) as cnt
        FROM aircraft_sightings
        WHERE first_seen >= datetime('now', '-24 hours')
        AND airline IS NOT NULL
        GROUP BY airline
        ORDER BY cnt DESC
        LIMIT 7
    """).fetchall()

    airlines_hourly_24h = {}
    for airline, _ in top_airlines_24h:
        hourly_data = cur.execute("""
            SELECT strftime('%Y-%m-%d %H:00', first_seen) as hour,
                   COUNT(*) as count
            FROM aircraft_sightings
            WHERE first_seen >= datetime('now', '-24 hours')
            AND airline = ?
            GROUP BY hour
            ORDER BY hour
        """, (airline,)).fetchall()

        hour_counts = {}
        for h, c in hourly_data:
            hour_counts[h] = c

        airlines_hourly_24h[airline] = [hour_counts.get(h, 0) for h in hours_24h]

    # Aircraft Types per hour (rolling 24h)
    top_aircraft_24h = cur.execute("""
        SELECT aircraft_type, COUNT(*) as cnt
        FROM aircraft_sightings
        WHERE first_seen >= datetime('now', '-24 hours')
        AND aircraft_type != ''
        GROUP BY aircraft_type
        ORDER BY cnt DESC
        LIMIT 7
    """).fetchall()

    aircraft_hourly_24h = {}
    for aircraft_type, _ in top_aircraft_24h:
        hourly_data = cur.execute("""
            SELECT strftime('%Y-%m-%d %H:00', first_seen) as hour,
                   COUNT(*) as count
            FROM aircraft_sightings
            WHERE first_seen >= datetime('now', '-24 hours')
            AND aircraft_type = ?
            GROUP BY hour
            ORDER BY hour
        """, (aircraft_type,)).fetchall()

        hour_counts = {}
        for h, c in hourly_data:
            hour_counts[h] = c

        aircraft_hourly_24h[aircraft_type] = [hour_counts.get(h, 0) for h in hours_24h]

    conn.close()

    return {
        'total_today': total_today,
        'total_all': total_all,
        'avg_per_day': round(avg_per_day, 1),
        'max_distance_today': max_distance_today,
        'days': days,
        'flights_per_day': flights_per_day,
        'top_airlines_today': top_airlines_today,
        'top_aircraft_today': top_aircraft_today,
        'top_airports_today': top_airports_today,
        'aircraft_flights': aircraft_flights,
        'airline_flights': airline_flights,
        'airport_flights': airport_flights,
        'all_flights_today': all_flights_today,
        'rarest_airlines': rarest_airlines,
        'rarest_aircraft': rarest_aircraft,
        'hourly_avg': hourly_avg_data,
        'hourly_today': hourly_today_data,
        'hours_24h': hours_24h,
        'airlines_hourly_24h': airlines_hourly_24h,
        'aircraft_hourly_24h': aircraft_hourly_24h,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def generate_html(s):
    # Build Top Airlines Today list HTML with detail buttons
    airlines_list_html = ""
    for idx, (airline, count) in enumerate(s['top_airlines_today'][:10], 1):
        airlines_list_html += f'''
            <div class="list-item">
                <span class="rank">#{idx}</span>
                <span class="name">{airline}</span>
                <span class="count">{count} flights</span>
                <button class="detail-btn" onclick="showAirlineFlights('{airline}')">Details</button>
            </div>'''

    # Build Rarest Airlines list HTML
    rarest_airlines_html = ""
    if s['rarest_airlines']:
        for airline, count in s['rarest_airlines']:
            rarest_airlines_html += f'<div class="rare-item"><span class="name">{airline}</span><span class="count">{count}x seen</span></div>'
    else:
        rarest_airlines_html = '<div class="rare-item">No rare airlines yet</div>'

    # Build Rarest Aircraft list HTML with callsign tooltips
    rarest_aircraft_html = ""
    if s['rarest_aircraft']:
        for aircraft, count, callsigns in s['rarest_aircraft']:
            rarest_aircraft_html += f'<div class="rare-item" title="Callsigns: {callsigns}"><span class="name">{aircraft}</span><span class="count">{count}x seen</span></div>'
    else:
        rarest_aircraft_html = '<div class="rare-item">No rare aircraft yet</div>'

    # Build Top Aircraft Today list HTML with detail buttons
    aircraft_list_html = ""
    for idx, (aircraft, count) in enumerate(s['top_aircraft_today'][:10], 1):
        aircraft_list_html += f'''
            <div class="list-item">
                <span class="rank">#{idx}</span>
                <span class="name">{aircraft}</span>
                <span class="count">{count} flights</span>
                <button class="detail-btn" onclick="showAircraftFlights('{aircraft}')">Details</button>
            </div>'''

    # Build Top Airports Today list HTML with detail buttons
    airports_list_html = ""
    for idx, (airport_iata, airport_name, count) in enumerate(s['top_airports_today'][:10], 1):
        airports_list_html += f'''
            <div class="list-item">
                <span class="rank">#{idx}</span>
                <span class="name">{airport_iata} - {airport_name}</span>
                <span class="count">{count} flights</span>
                <button class="detail-btn" onclick="showAirportFlights('{airport_iata}')">Details</button>
            </div>'''

    # Prepare 24h labels for rolling charts
    hours_labels = [h.split(' ')[1] for h in s['hours_24h']]

    # Colors for charts
    colors = ['#667eea','#764ba2','#f093fb','#4facfe','#43e97b','#fa709a','#fee140','#30cfd0','#a8edea','#fed6e3']

    # Airlines 24h datasets
    airlines_datasets = []
    for idx, (airline, data) in enumerate(s['airlines_hourly_24h'].items()):
        color = colors[idx % len(colors)]
        airlines_datasets.append({
            'label': airline,
            'data': data,
            'borderColor': color,
            'backgroundColor': f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)',
            'tension': 0.4,
            'fill': False,
            'borderWidth': 2
        })

    # Aircraft 24h datasets
    aircraft_datasets = []
    for idx, (aircraft, data) in enumerate(s['aircraft_hourly_24h'].items()):
        color = colors[idx % len(colors)]
        aircraft_datasets.append({
            'label': aircraft,
            'data': data,
            'borderColor': color,
            'backgroundColor': f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)',
            'tension': 0.4,
            'fill': False,
            'borderWidth': 2
        })

    charts = f"""
    new Chart(document.getElementById('hourlyChart'),{{type:'bar',data:{{labels:['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23'],datasets:[{{type:'bar',label:'Expected (Avg)',data:{json.dumps(s['hourly_avg'])},backgroundColor:'rgba(102,126,234,0.5)',borderColor:'#667eea',borderWidth:1}},{{type:'line',label:'Today',data:{json.dumps(s['hourly_today'])},borderColor:'#fa709a',backgroundColor:'rgba(250,112,154,0.1)',borderWidth:3,tension:0.4,fill:false,pointRadius:4,pointBackgroundColor:'#fa709a'}}]}},options:{{responsive:true,plugins:{{legend:{{display:true,position:'top'}}}},scales:{{y:{{beginAtZero:true,title:{{display:true,text:'Flights'}}}},x:{{title:{{display:true,text:'Hour'}}}}}}}}}});
    new Chart(document.getElementById('airlinesChart'),{{type:'doughnut',data:{{labels:{json.dumps([a[0] for a in s['top_airlines_today']])},datasets:[{{data:{json.dumps([a[1] for a in s['top_airlines_today']])},backgroundColor:['#667eea','#764ba2','#f093fb','#4facfe','#43e97b','#fa709a','#fee140','#30cfd0','#a8edea','#fed6e3']}}]}},options:{{responsive:true,plugins:{{legend:{{position:'right'}}}}}}}});
    new Chart(document.getElementById('aircraftChart'),{{type:'doughnut',data:{{labels:{json.dumps([a[0] for a in s['top_aircraft_today']])},datasets:[{{data:{json.dumps([a[1] for a in s['top_aircraft_today']])},backgroundColor:['#667eea','#764ba2','#f093fb','#4facfe','#43e97b','#fa709a','#fee140','#30cfd0','#a8edea','#fed6e3']}}]}},options:{{responsive:true,plugins:{{legend:{{position:'right'}}}}}}}});
    new Chart(document.getElementById('airlines24h'),{{type:'line',data:{{labels:{json.dumps(hours_labels)},datasets:{json.dumps(airlines_datasets)}}},options:{{responsive:true,plugins:{{legend:{{display:true,position:'top'}}}},scales:{{y:{{beginAtZero:true,title:{{display:true,text:'Flights'}}}},x:{{title:{{display:true,text:'Hour (Last 24h)'}}}}}}}}}});
    new Chart(document.getElementById('aircraft24h'),{{type:'line',data:{{labels:{json.dumps(hours_labels)},datasets:{json.dumps(aircraft_datasets)}}},options:{{responsive:true,plugins:{{legend:{{display:true,position:'top'}}}},scales:{{y:{{beginAtZero:true,title:{{display:true,text:'Flights'}}}},x:{{title:{{display:true,text:'Hour (Last 24h)'}}}}}}}}}});
    """

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADSB Statistics {LOCATION_NAME}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #fff; text-align: center; margin-bottom: 10px; font-size: 2.5em; text-shadow: 2px 2px 4px rgba(0,0,0,.3); }}
        .subtitle {{ color: rgba(255,255,255,.9); text-align: center; margin-bottom: 30px; font-size: 1.1em; }}
        .nav-links {{ text-align: center; margin-bottom: 20px; }}
        .nav-links a {{ color: white; text-decoration: none; margin: 0 15px; padding: 8px 16px; background: rgba(255,255,255,0.2); border-radius: 6px; font-weight: 500; transition: all 0.2s; }}
        .nav-links a:hover {{ background: rgba(255,255,255,0.3); }}

        /* Stats Cards */
        .stats-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,.1); transition: transform .2s; }}
        .card:hover {{ transform: translateY(-5px); box-shadow: 0 6px 12px rgba(0,0,0,.15); }}
        .card-title {{ color: #667eea; font-size: .9em; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 10px; }}
        .card-value {{ color: #333; font-size: 2.5em; font-weight: 700; }}
        .card-subtitle {{ color: #666; font-size: .85em; margin-top: 5px; }}

        /* Charts */
        .chart-container {{ background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,.1); margin-bottom: 30px; }}
        .chart-title {{ color: #333; font-size: 1.2em; font-weight: 600; margin-bottom: 20px; text-align: center; }}
        canvas {{ max-height: 350px; }}

        /* Grid Layouts */
        .two-col-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}

        /* List Styles */
        .list-container {{ background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,.1); }}
        .list-item {{ display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #eee; }}
        .list-item:last-child {{ border-bottom: none; }}
        .list-item .rank {{ color: #667eea; font-weight: 700; font-size: 1.1em; width: 40px; }}
        .list-item .name {{ flex: 1; color: #333; font-weight: 600; }}
        .list-item .count {{ color: #666; font-size: .9em; margin-right: 10px; }}
        .detail-btn {{ background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: .85em; transition: background .2s; }}
        .detail-btn:hover {{ background: #5568d3; }}

        /* Rare Items */
        .rare-container {{ background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,.1); }}
        .rare-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; cursor: help; transition: background .2s; }}
        .rare-item:hover {{ background: rgba(102,126,234,0.05); }}
        .rare-item:last-child {{ border-bottom: none; }}
        .rare-item .name {{ color: #333; font-weight: 600; }}
        .rare-item .count {{ color: #fa709a; font-size: .9em; font-weight: 600; }}

        .footer {{ text-align: center; color: rgba(255,255,255,.8); margin-top: 30px; padding: 20px; font-size: .9em; }}
        .footer a {{ color: #fff; text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}

        /* All Flights Table */
        .all-flights-container {{ background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,.1); margin-bottom: 30px; }}
        .search-box {{ width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; margin-bottom: 15px; transition: border-color .2s; }}
        .search-box:focus {{ outline: none; border-color: #667eea; }}
        .table-wrapper {{ max-height: 600px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; }}
        .all-flights-table {{ width: 100%; border-collapse: collapse; }}
        .all-flights-table thead {{ position: sticky; top: 0; background: #f7fafc; z-index: 10; }}
        .all-flights-table th {{ padding: 12px; text-align: left; font-weight: 600; color: #667eea; border-bottom: 2px solid #ddd; white-space: nowrap; }}
        .all-flights-table td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        .all-flights-table tbody tr:hover {{ background: #f7fafc; }}
        .all-flights-table tbody tr.hidden {{ display: none; }}
        .all-flights-table a {{ color: #667eea; text-decoration: none; }}
        .all-flights-table a:hover {{ text-decoration: underline; }}

        @media (max-width: 768px) {{
            .stats-cards {{ grid-template-columns: 1fr; }}
            .two-col-grid {{ grid-template-columns: 1fr; }}
            h1 {{ font-size: 1.8em; }}
        }}

        /* Modal Styles */
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }}
        .modal.show {{ display: flex; }}
        .modal-content {{ background: white; border-radius: 12px; padding: 30px; max-width: 800px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.3); }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #667eea; }}
        .modal-header h2 {{ color: #667eea; font-size: 1.5em; margin: 0; }}
        .modal-close {{ background: none; border: none; font-size: 28px; cursor: pointer; color: #999; padding: 0; width: 30px; height: 30px; line-height: 30px; }}
        .modal-close:hover {{ color: #333; }}
        .flight-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .flight-table th {{ background: #f7fafc; padding: 12px; text-align: left; font-weight: 600; color: #667eea; border-bottom: 2px solid #ddd; }}
        .flight-table td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        .flight-table tr:hover {{ background: #f7fafc; }}
        .flight-table tr:last-child td {{ border-bottom: none; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✈️ ADSB Statistics {LOCATION_NAME}</h1>
        <div class="subtitle">Aircraft Tracking • Updated: {s['updated']}</div>
        <div class="nav-links">
            <a href="/tar1090/">🗺️ Live Map</a>
            <a href="alerts.html">🚨 Alert Management</a>
        </div>

        <!-- Stats Cards (3 cards) -->
        <div class="stats-cards">
            <div class="card">
                <div class="card-title">Today</div>
                <div class="card-value">{s['total_today']}</div>
                <div class="card-subtitle">Flights</div>
            </div>
            <div class="card">
                <div class="card-title">Average</div>
                <div class="card-value">{s['avg_per_day']}</div>
                <div class="card-subtitle">Flights per Day</div>
            </div>
            <div class="card">
                <div class="card-title">Max Distance</div>
                <div class="card-value">{s['max_distance_today']}</div>
                <div class="card-subtitle">NM (Today)</div>
            </div>
        </div>

        <!-- Hourly Traffic Chart -->
        <div class="chart-container">
            <div class="chart-title">Hourly Traffic - Expected vs Today</div>
            <canvas id="hourlyChart"></canvas>
        </div>

        <!-- Top Airlines Today: List + Chart -->
        <div class="two-col-grid">
            <div class="list-container">
                <div class="chart-title">Top Airlines Today</div>
                {airlines_list_html}
            </div>
            <div class="chart-container">
                <div class="chart-title">Top Airlines Today</div>
                <canvas id="airlinesChart"></canvas>
            </div>
        </div>

        <!-- Top Aircraft Types Today: List + Chart -->
        <div class="two-col-grid">
            <div class="list-container">
                <div class="chart-title">Top Aircraft Types Today</div>
                {aircraft_list_html}
            </div>
            <div class="chart-container">
                <div class="chart-title">Top Aircraft Types Today</div>
                <canvas id="aircraftChart"></canvas>
            </div>
        </div>

        <!-- Top Airports Today -->
        <div class="list-container" style="max-width: 100%;">
            <div class="chart-title">Top 10 Airports Today</div>
            {airports_list_html}
        </div>

        <!-- Rolling 24h Charts -->
        <div class="chart-container">
            <div class="chart-title">Airlines per Hour - Last 24 Hours (Rolling)</div>
            <canvas id="airlines24h"></canvas>
        </div>

        <div class="chart-container">
            <div class="chart-title">Aircraft Types per Hour - Last 24 Hours (Rolling)</div>
            <canvas id="aircraft24h"></canvas>
        </div>

        <!-- Rarest Airlines + Aircraft -->
        <div class="two-col-grid">
            <div class="rare-container">
                <div class="chart-title">Rarest Airlines (Top 5)</div>
                {rarest_airlines_html}
            </div>
            <div class="rare-container">
                <div class="chart-title">Rarest Aircraft Types (Top 5)</div>
                {rarest_aircraft_html}
            </div>
        </div>

        <!-- All Flights Today Table -->
        <div class="all-flights-container">
            <div class="chart-title">All Flights Today ({s['total_today']} flights)</div>
            <input type="text" class="search-box" id="flightSearch" placeholder="Search by callsign, airline, aircraft type, route..." onkeyup="filterFlights()">
            <div class="table-wrapper">
                <table class="all-flights-table" id="allFlightsTable">
                    <thead>
                        <tr>
                            <th>Callsign</th>
                            <th>Airline</th>
                            <th>Aircraft</th>
                            <th>Route</th>
                            <th>First Seen</th>
                            <th>Last Seen</th>
                            <th>Min Alt (ft)</th>
                            <th>Max Alt (ft)</th>
                            <th>Distance (NM)</th>
                            <th>Track</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f"""
                        <tr>
                            <td>{flight[0]}</td>
                            <td>{flight[2] or '-'}</td>
                            <td>{flight[3] or '-'}</td>
                            <td title="{flight[11] or ''} → {flight[12] or ''}">{flight[9] + ' → ' + flight[10] if flight[9] and flight[10] else '-'}</td>
                            <td>{flight[4].split(' ')[1][:5] if flight[4] else '-'}</td>
                            <td>{flight[5].split(' ')[1][:5] if flight[5] else '-'}</td>
                            <td>{flight[6] if flight[6] else '-'}</td>
                            <td>{flight[7] if flight[7] else '-'}</td>
                            <td>{round(flight[8], 1) if flight[8] else '-'}</td>
                            <td><a href="{TAR1090_PATH}?pTracks&filterCallSign={flight[0].strip()}" target="_blank">View</a></td>
                        </tr>""" for flight in s['all_flights_today']])}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            📡 ADSB Receiver {LOCATION_NAME} • <a href="{TAR1090_PATH}">Live Map</a>{' • <a href="' + PUBLIC_URL + '">Public Access</a>' if PUBLIC_URL else ''}
        </div>
    </div>

    <!-- Modal for Airline Flight Details -->
    <div id="airlineModal" class="modal" onclick="closeAirlineModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2 id="airlineModalTitle">Airline Flights</h2>
                <button class="modal-close" onclick="closeAirlineModal()">&times;</button>
            </div>
            <div id="airlineModalBody">
                <!-- Flights will be inserted here -->
            </div>
        </div>
    </div>

    <!-- Modal for Aircraft Flight Details -->
    <div id="aircraftModal" class="modal" onclick="closeAircraftModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2 id="aircraftModalTitle">Aircraft Flights</h2>
                <button class="modal-close" onclick="closeAircraftModal()">&times;</button>
            </div>
            <div id="aircraftModalBody">
                <!-- Flights will be inserted here -->
            </div>
        </div>
    </div>

    <!-- Modal for Airport Flight Details -->
    <div id="airportModal" class="modal" onclick="closeAirportModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2 id="airportModalTitle">Airport Flights</h2>
                <button class="modal-close" onclick="closeAirportModal()">&times;</button>
            </div>
            <div id="airportModalBody">
                <!-- Flights will be inserted here -->
            </div>
        </div>
    </div>

    <script>
    // Aircraft, airline, and airport flights data
    const aircraftFlights = {json.dumps(s['aircraft_flights'])};
    const airlineFlights = {json.dumps(s['airline_flights'])};
    const airportFlights = {json.dumps(s['airport_flights'])};

    // Show airline flights in modal
    function showAirlineFlights(airline) {{
        const modal = document.getElementById('airlineModal');
        const modalTitle = document.getElementById('airlineModalTitle');
        const modalBody = document.getElementById('airlineModalBody');

        modalTitle.textContent = `Flights for ${{airline}} Today`;

        const flights = airlineFlights[airline] || [];

        if (flights.length === 0) {{
            modalBody.innerHTML = '<p>No flights found</p>';
        }} else {{
            let html = '<table class="flight-table">';
            html += '<thead><tr>';
            html += '<th>Callsign</th>';
            html += '<th>Aircraft Type</th>';
            html += '<th>Route</th>';
            html += '<th>First Seen</th>';
            html += '<th>Distance (NM)</th>';
            html += '</tr></thead>';
            html += '<tbody>';

            flights.forEach(flight => {{
                const distance = flight[3] ? flight[3].toFixed(1) : 'N/A';
                const aircraftType = flight[1] || 'Unknown';
                const time = flight[2].split(' ')[1].substring(0, 5); // Extract HH:MM
                const originIata = flight[5] || '';
                const destIata = flight[6] || '';
                const route = (originIata && destIata) ? `${{originIata}} → ${{destIata}}` : '-';
                const routeTitle = flight[7] && flight[8] ? `${{flight[7]}} → ${{flight[8]}}` : '';

                const tar1090Url = `{TAR1090_PATH}?pTracks&filterCallSign=${{flight[0].trim()}}`;

                html += `<tr>`;
                html += `<td><a href="${{tar1090Url}}" target="_blank" style="color: #667eea; text-decoration: none;">${{flight[0]}}</a></td>`;
                html += `<td>${{aircraftType}}</td>`;
                html += `<td title="${{routeTitle}}">${{route}}</td>`;
                html += `<td>${{time}}</td>`;
                html += `<td>${{distance}}</td>`;
                html += `</tr>`;
            }});

            html += '</tbody></table>';
            modalBody.innerHTML = html;
        }}

        modal.classList.add('show');
    }}

    // Show aircraft flights in modal
    function showAircraftFlights(aircraftType) {{
        const modal = document.getElementById('aircraftModal');
        const modalTitle = document.getElementById('aircraftModalTitle');
        const modalBody = document.getElementById('aircraftModalBody');

        modalTitle.textContent = `Flights for ${{aircraftType}} Today`;

        const flights = aircraftFlights[aircraftType] || [];

        if (flights.length === 0) {{
            modalBody.innerHTML = '<p>No flights found</p>';
        }} else {{
            let html = '<table class="flight-table">';
            html += '<thead><tr>';
            html += '<th>Callsign</th>';
            html += '<th>Airline</th>';
            html += '<th>Route</th>';
            html += '<th>First Seen</th>';
            html += '<th>Distance (NM)</th>';
            html += '</tr></thead>';
            html += '<tbody>';

            flights.forEach(flight => {{
                const distance = flight[3] ? flight[3].toFixed(1) : 'N/A';
                const airline = flight[4] || 'Unknown';
                const time = flight[2].split(' ')[1].substring(0, 5); // Extract HH:MM
                const originIata = flight[5] || '';
                const destIata = flight[6] || '';
                const route = (originIata && destIata) ? `${{originIata}} → ${{destIata}}` : '-';
                const routeTitle = flight[7] && flight[8] ? `${{flight[7]}} → ${{flight[8]}}` : '';

                const tar1090Url = `{TAR1090_PATH}?pTracks&filterCallSign=${{flight[0].trim()}}`;

                html += `<tr>`;
                html += `<td><a href="${{tar1090Url}}" target="_blank" style="color: #667eea; text-decoration: none;">${{flight[0]}}</a></td>`;
                html += `<td>${{airline}}</td>`;
                html += `<td title="${{routeTitle}}">${{route}}</td>`;
                html += `<td>${{time}}</td>`;
                html += `<td>${{distance}}</td>`;
                html += `</tr>`;
            }});

            html += '</tbody></table>';
            modalBody.innerHTML = html;
        }}

        modal.classList.add('show');
    }}

    // Close airline modal
    function closeAirlineModal(event) {{
        if (!event || event.target === document.getElementById('airlineModal')) {{
            document.getElementById('airlineModal').classList.remove('show');
        }}
    }}

    // Close aircraft modal
    function closeAircraftModal(event) {{
        if (!event || event.target === document.getElementById('aircraftModal')) {{
            document.getElementById('aircraftModal').classList.remove('show');
        }}
    }}

    // Show airport flights in modal
    function showAirportFlights(airportIata) {{
        const modal = document.getElementById('airportModal');
        const modalTitle = document.getElementById('airportModalTitle');
        const modalBody = document.getElementById('airportModalBody');

        modalTitle.textContent = `Flights for ${{airportIata}} Today`;

        const flights = airportFlights[airportIata] || [];

        if (flights.length === 0) {{
            modalBody.innerHTML = '<p>No flights found</p>';
        }} else {{
            let html = '<table class="flight-table">';
            html += '<thead><tr>';
            html += '<th>Callsign</th>';
            html += '<th>Airline</th>';
            html += '<th>Aircraft Type</th>';
            html += '<th>Route</th>';
            html += '<th>First Seen</th>';
            html += '<th>Distance (NM)</th>';
            html += '</tr></thead>';
            html += '<tbody>';

            flights.forEach(flight => {{
                const distance = flight[3] ? flight[3].toFixed(1) : 'N/A';
                const aircraftType = flight[1] || 'Unknown';
                const airline = flight[4] || '-';
                const time = flight[2].split(' ')[1].substring(0, 5); // Extract HH:MM
                const originIata = flight[5] || '';
                const destIata = flight[6] || '';
                const route = (originIata && destIata) ? `${{originIata}} → ${{destIata}}` : '-';
                const routeTitle = flight[7] && flight[8] ? `${{flight[7]}} → ${{flight[8]}}` : '';

                const tar1090Url = `{TAR1090_PATH}?pTracks&filterCallSign=${{flight[0].trim()}}`;

                html += `<tr>`;
                html += `<td><a href="${{tar1090Url}}" target="_blank" style="color: #667eea; text-decoration: none;">${{flight[0]}}</a></td>`;
                html += `<td>${{airline}}</td>`;
                html += `<td>${{aircraftType}}</td>`;
                html += `<td title="${{routeTitle}}">${{route}}</td>`;
                html += `<td>${{time}}</td>`;
                html += `<td>${{distance}}</td>`;
                html += `</tr>`;
            }});

            html += '</tbody></table>';
            modalBody.innerHTML = html;
        }}

        modal.classList.add('show');
    }}

    // Close airport modal
    function closeAirportModal(event) {{
        if (!event || event.target === document.getElementById('airportModal')) {{
            document.getElementById('airportModal').classList.remove('show');
        }}
    }}

    // Close modals on ESC key
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') {{
            closeAirlineModal();
            closeAircraftModal();
            closeAirportModal();
        }}
    }});

    // Filter flights table
    function filterFlights() {{
        const searchInput = document.getElementById('flightSearch');
        const filter = searchInput.value.toUpperCase();
        const table = document.getElementById('allFlightsTable');
        const rows = table.getElementsByTagName('tr');

        let visibleCount = 0;

        for (let i = 1; i < rows.length; i++) {{
            const row = rows[i];
            const cells = row.getElementsByTagName('td');
            let found = false;

            // Search through all cells
            for (let j = 0; j < cells.length; j++) {{
                const cell = cells[j];
                if (cell) {{
                    const txtValue = cell.textContent || cell.innerText;
                    if (txtValue.toUpperCase().indexOf(filter) > -1) {{
                        found = true;
                        break;
                    }}
                }}
            }}

            if (found) {{
                row.classList.remove('hidden');
                visibleCount++;
            }} else {{
                row.classList.add('hidden');
            }}
        }}
    }}

    // Charts
    {charts}
    </script>
</body>
</html>'''
    return html

if __name__ == "__main__":
    stats = get_stats()
    html = generate_html(stats)
    with open(OUTPUT, 'w') as f:
        f.write(html)
    print(f"Dashboard generated: {OUTPUT}")
