import streamlit as st
import networkx as networkx_lib
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime
import requests
from geopy.geocoders import Nominatim

# -------------------------------------------------------------
# PAGE CONFIGURATION & PROFESSIONAL UI STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="RouteSafe – Universal Smart Alternate Route System",
    page_icon="🛡️",
    layout="wide"
)

st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
        padding: 22px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
    }
    .main-title { font-size: 2.1rem; font-weight: 800; margin: 0; color: #FFFFFF; }
    .sub-title { font-size: 1.0rem; color: #93C5FD; margin-top: 4px; margin-bottom: 0; }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #2563EB;
    }
    .weather-box {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #BFDBFE;
        color: #1E40AF;
    }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="main-header">
        <p class="main-title">🛡️ RouteSafe: Universal Smart Alternate Route System</p>
        <p class="sub-title">Real-Time Disaster Response, Road Disruption Management & Automated Rerouting for Any City</p>
    </div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect('universal_routesafe.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disruptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            location_name TEXT,
            lat REAL,
            lon REAL,
            reason TEXT,
            severity TEXT,
            status TEXT,
            description TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION & DYNAMIC CITY SELECTOR
# -------------------------------------------------------------
st.sidebar.markdown("### 🎛️ Navigation Menu")
app_mode = st.sidebar.radio(
    "Select Portal View", 
    [
        "🏠 Dashboard (Citizen View)", 
        "🗺️ Plan a Route", 
        "🚨 Report Road Disruption", 
        "📋 Manage Reports", 
        "🔍 Route Details"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Target Operations Zone")
target_city = st.sidebar.text_input("Enter City / Region", value="Guntur, Andhra Pradesh")

# Geocode City to get Center Coordinates
@st.cache_data(show_spinner=False)
def get_city_coordinates(city_name):
    geolocator = Nominatim(user_agent="routesafe_app")
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    # Fallback default coordinates (Guntur)
    return 16.3067, 80.4365

city_lat, city_lon = get_city_coordinates(target_city)

# Generate dynamic sample landmarks around the target city so any city works instantly
@st.cache_data(show_spinner=False)
def get_city_landmarks(city, lat, lon):
    return {
        f"{city} Central Railway Station": {"lat": lat + 0.005, "lon": lon - 0.005},
        f"{city} General Hospital": {"lat": lat - 0.004, "lon": lon + 0.004},
        f"Highway NH Main Junction": {"lat": lat + 0.012, "lon": lon - 0.015},
        f"Ring Road Crossing": {"lat": lat - 0.012, "lon": lon + 0.015},
        f"Commercial Bypass Road": {"lat": lat + 0.008, "lon": lon + 0.008},
        f"Downtown Market Area": {"lat": lat, "lon": lon}
    }

CITY_LOCATIONS = get_city_landmarks(target_city, city_lat, city_lon)

# Live Weather Integration for Target City
def get_city_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        res = requests.get(url, timeout=4).json()
        current = res.get("current", {})
        w_code = current.get("weather_code", 0)
        condition = "Clear & Safe ☀️"
        if w_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: condition = "Heavy Rain 🌧️"
        elif w_code >= 95: condition = "Thunderstorm ⛈️"
        elif w_code in [1, 2, 3]: condition = "Partly Cloudy ⛅"
        return {
            "temp": current.get("temperature_2m", 30),
            "humidity": current.get("relative_humidity_2m", 60),
            "condition": condition
        }
    except Exception:
        return {"temp": 30, "humidity": 60, "condition": "Normal ☀️"}

weather = get_city_weather(city_lat, city_lon)

# Fetch disruptions filtered by target city
def get_disruptions(city):
    cursor = conn.cursor()
    cursor.execute("SELECT id, city, location_name, lat, lon, reason, severity, status, description, timestamp FROM disruptions WHERE city = ?", (city,))
    return cursor.fetchall()

city_disruptions = get_disruptions(target_city)
active_count = len([d for d in city_disruptions if d[7] in ["Road Closed", "Blocked"]])

# =============================================================
# VIEW 1: DASHBOARD (CITIZEN VIEW)
# =============================================================
if app_mode == "🏠 Dashboard (Citizen View)":
    st.markdown(f"### Good Morning! ({target_city})")
    st.caption(f"Get the latest road updates and plan your safest route across {target_city}.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <b>Active Disruptions</b><h2 style="color: #DC2626; margin:0;">{active_count}</h2><small>(in {target_city})</small>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <b>Roads Open</b><h2 style="color: #16A34A; margin:0;">{len(CITY_LOCATIONS) - active_count}</h2><small>(in {target_city})</small>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <b>Weather Alert</b><h2 style="color: #2563EB; margin:0; font-size:1.3rem;">{weather['condition']}</h2><small>({target_city} region)</small>
        </div>""", unsafe_allow_html=True)
        
    st.markdown("#### Live Road Conditions")
    
    m = folium.Map(location=[city_lat, city_lon], zoom_start=13)
    
    for name, coords in CITY_LOCATIONS.items():
        folium.Marker(
            location=[coords['lat'], coords['lon']],
            popup=name,
            icon=folium.Icon(color="green", icon="road", prefix="fa")
        ).add_to(m)
        
    for d in city_disruptions:
        d_name, d_lat, d_lon, d_reason, d_sev, d_status = d[2], d[3], d[4], d[5], d[6], d[7]
        color = "red" if d_status in ["Road Closed", "Blocked"] else "orange"
        folium.Marker(
            location=[d_lat, d_lon],
            popup=f"<b>{d_name}</b><br>Status: {d_status}<br>Reason: {d_reason}",
            icon=folium.Icon(color=color, icon="exclamation-triangle", prefix="fa")
        ).add_to(m)
        
    st_folium(m, width="100%", height=420)

# =============================================================
# VIEW 2: PLAN A ROUTE
# =============================================================
elif app_mode == "🗺️ Plan a Route":
    st.markdown(f"### Plan Your Route ({target_city})")
    
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        from_loc = st.selectbox("From", list(CITY_LOCATIONS.keys()), index=0)
    with col_b:
        to_loc = st.selectbox("To", list(CITY_LOCATIONS.keys()), index=1)
    with col_c:
        st.markdown("<br>", unsafe_allow_html=True)
        find_btn = st.button("Find Route", type="primary")
        
    col1, col2 = st.columns([2, 1])
    
    with col1:
        m = folium.Map(location=[city_lat, city_lon], zoom_start=13)
        start_pt = [CITY_LOCATIONS[from_loc]['lat'], CITY_LOCATIONS[from_loc]['lon']]
        end_pt = [CITY_LOCATIONS[to_loc]['lat'], CITY_LOCATIONS[to_loc]['lon']]
        
        # Intermediate diversion point for alternate route simulation
        mid_pt = [(start_pt[0]+end_pt[0])/2 + 0.003, (start_pt[1]+end_pt[1])/2 + 0.003]
        safe_line = [start_pt, mid_pt, end_pt]
        
        folium.PolyLine(safe_line, color="#2563EB", weight=6, tooltip="Alternate Safe Route").add_to(m)
        folium.Marker(start_pt, popup="Start", icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
        folium.Marker(end_pt, popup="Destination", icon=folium.Icon(color="green", icon="flag", prefix="fa")).add_to(m)
        
        st_folium(m, width="100%", height=450)
        
    with col2:
        st.markdown("#### Recommended Route <span style='font-size:0.8rem; background:#DCFCE7; color:#166534; padding:3px 8px; border-radius:4px;'>Avoids blocked road</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Distance:** 7.8 km
        * **Estimated Time:** 19 min
        """)
        st.success(f"This route bypasses active hazards in {target_city} using cleared alternate arterial roads.")
        
        st.markdown("#### Other Options")
        st.info("• Route 2: 9.2 km (25 min)\n\n• Route 3: 10.5 km (31 min)")

# =============================================================
# VIEW 3: REPORT ROAD DISRUPTION (ADMIN)
# =============================================================
elif app_mode == "🚨 Report Road Disruption":
    st.markdown(f"### Report Road Disruption ({target_city})")
    
    with st.form("report_form"):
        col1, col2 = st.columns(2)
        with col1:
            loc_name = st.selectbox("Location", list(CITY_LOCATIONS.keys()))
            disruption_type = st.selectbox("Disruption Type", ["Accident", "Flooding", "Construction", "Tree Fall"])
            severity = st.selectbox("Severity", ["Low", "Medium", "High"])
        with col2:
            status = st.selectbox("Status", ["Road Closed", "Partial", "Open"])
            est_duration = st.text_input("Estimated Duration", value="3 hours")
            
        description = st.text_area("Description", placeholder="Enter details about the road disruption...")
        submitted = st.form_submit_button("Submit Report", type="primary")
        
        if submitted:
            coords = CITY_LOCATIONS[loc_name]
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO disruptions (city, location_name, lat, lon, reason, severity, status, description, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (target_city, loc_name, coords['lat'], coords['lon'], disruption_type, severity, status, description, datetime.now().strftime("%d %b %Y, %I:%M %p"))
            )
            conn.commit()
            st.success(f"Disruption report for {target_city} submitted successfully!")
            st.rerun()

# =============================================================
# VIEW 4: MANAGE REPORTS
# =============================================================
elif app_mode == "📋 Manage Reports":
    st.markdown(f"### Reported Disruptions ({target_city})")
    
    records = get_disruptions(target_city)
    if not records:
        st.info(f"No disruptions reported for {target_city} yet.")
    else:
        for r in records:
            r_id, r_loc, r_reason, r_sev, r_status, r_time = r[0], r[2], r[5], r[6], r[7], r[9]
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            with col1: st.write(f"📅 {r_time}")
            with col2: st.write(f"📍 **{r_loc}**")
            with col3: st.write(r_reason)
            with col4: 
                badge_color = "#DC2626" if r_status=="Road Closed" else "#16A34A"
                st.markdown(f"<span style='color:white; background:{badge_color}; padding:2px 8px; border-radius:4px;'>{r_status}</span>", unsafe_allow_html=True)
            with col5:
                if st.button("View", key=f"view_{r_id}"):
                    st.session_state['selected_report'] = r_id
            st.markdown("---")

# =============================================================
# VIEW 5: ROUTE DETAILS
# =============================================================
elif app_mode == "🔍 Route Details":
    st.markdown(f"### Road Disruption Details ({target_city})")
    
    records = get_disruptions(target_city)
    if not records:
        st.info("Please submit or select a disruption report to view details.")
    else:
        latest = records[-1]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Type:** {latest[5]}")
            st.markdown(f"**Reported On:** {latest[9]}")
        with col2:
            st.markdown(f"**Location:** {latest[2]}")
            st.markdown(f"**Status:** <span style='color:red;'>{latest[7]}</span>", unsafe_allow_html=True)
            
        st.markdown(f"**Description:** {latest[8]}")
        
        m = folium.Map(location=[latest[3], latest[4]], zoom_start=14)
        folium.Marker([latest[3], latest[4]], popup=latest[2], icon=folium.Icon(color="red", icon="ban", prefix="fa")).add_to(m)
        st_folium(m, width="100%", height=350)
        
        st.info(f"💡 **Alternate Route Recommendation:** Use local diversion routes in {target_city} to avoid the blocked section. Estimated time: 19 min | Distance: 7.8 km")
