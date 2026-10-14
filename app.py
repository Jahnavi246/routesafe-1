import streamlit as st
import osmnx as ox
import networkx as networkx_lib
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime
import requests
import pandas as pd
import io

# -------------------------------------------------------------
# PAGE CONFIGURATION & PROFESSIONAL UI STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="RouteSafe – Emergency Alternate Route Assistance System",
    page_icon="🛡️",
    layout="wide"
)

st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 25px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-title { font-size: 2.2rem; font-weight: 800; margin: 0; color: #FFFFFF; }
    .sub-title { font-size: 1.05rem; color: #E0E7FF; margin-top: 5px; margin-bottom: 0; }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 16px;
        border-radius: 8px;
        border-left: 5px solid #3B82F6;
    }
    .weather-box {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #BFDBFE;
        color: #1E40AF;
    }
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="main-header">
        <p class="main-title">🛡️ RouteSafe: SafeSync Multi-Hazard Emergency & Logistics Portal</p>
        <p class="sub-title">Official Real-Time Disaster Response, Road Disruption Management & Automated Alternate Rerouting System</p>
    </div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect('routesafe_disruptions.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disruptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT,
            lat REAL,
            lon REAL,
            reason TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION & CONTROLS
# -------------------------------------------------------------
st.sidebar.markdown("### 🎛️ Control Panel")
app_mode = st.sidebar.radio(
    "Select Portal View", 
    [
        "🗺️ Citizen Navigation & Live Map", 
        "🚨 Admin Emergency Incident Report", 
        "📤 Upload & Report Hazard Data", 
        "🛠️ Manage Active Disruption Zones"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Target Operations Zone")
place_name = st.sidebar.text_input("City / Region Area", value="Connaught Place, New Delhi, India")

# Optimized fast map loading via point and radius to avoid Overpass API timeouts
@st.cache_resource(show_spinner="📥 Downloading local road network grid...")
def load_road_network(place):
    try:
        ox.settings.timeout = 30
        ox.settings.use_cache = True
        # Using Connaught Place default coordinates (Lat: 28.6315, Lon: 77.2167) with a safe 1.5km radius
        center_point = (28.6315, 77.2167)
        G = ox.graph_from_point(center_point, dist=1500, network_type='drive')
        return G
    except Exception as e:
        st.warning(f"OSM API timeout. Using fallback graph area. Error: {e}")
        return ox.graph_from_point((28.6315, 77.2167), dist=1000, network_type='drive')

G = load_road_network(place_name)

if G is None:
    st.warning("⚠️ Failed to load map network.")
    st.stop()

center_lat = sum(data['y'] for _, data in G.nodes(data=True)) / len(G.nodes())
center_lon = sum(data['x'] for _, data in G.nodes(data=True)) / len(G.nodes())

# -------------------------------------------------------------
# LIVE WEATHER API INTEGRATION (Open-Meteo)
# -------------------------------------------------------------
def get_live_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        res = requests.get(url, timeout=4).json()
        current = res.get("current", {})
        
        w_code = current.get("weather_code", 0)
        condition = "Clear & Safe ☀️"
        if w_code in [1, 2, 3]: condition = "Partly Cloudy ⛅"
        elif w_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: condition = "Heavy Rainfall / Waterlogging Risk 🌧️"
        elif w_code in [45, 48]: condition = "Low Visibility Fog 🌫️"
        elif w_code >= 95: condition = "Severe Storm / Hazard Warning ⛈️"
        
        return {
            "temp": current.get("temperature_2m", 28),
            "humidity": current.get("relative_humidity_2m", 60),
            "wind": current.get("wind_speed_10m", 12),
            "condition": condition
        }
    except Exception:
        return {"temp": 28, "humidity": 60, "wind": 12, "condition": "Normal Conditions ☀️"}

def get_active_disruptions():
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, status FROM disruptions WHERE status = 'Blocked'")
    return cursor.fetchall()

active_disruptions = get_active_disruptions()

G_modified = G.copy()
for disp in active_disruptions:
    d_id, d_name, d_lat, d_lon, d_reason, d_status = disp
    try:
        nearest_node = ox.distance.nearest_nodes(G_modified, X=d_lon, Y=d_lat)
        if nearest_node in G_modified:
            G_modified.remove_node(nearest_node)
    except Exception:
        pass

# =============================================================
# VIEW 1: CITIZEN NAVIGATION & LIVE MAP
# =============================================================
if app_mode == "🗺️ Citizen Navigation & Live Map":
    col_l, col_r = st.columns([1.2, 2.8], gap="medium")
    
    with col_l:
        st.markdown("#### 🧭 Journey & Route Planner")
        
        use_default_gps = st.checkbox("Use Zone Default Coordinates for Start", value=True)
        if use_default_gps:
            start_lat, start_lon = center_lat, center_lon
            st.info(f"📍 GPS Locked: ({round(start_lat, 4)}, {round(start_lon, 4)})")
        else:
            start_lat = st.number_input("Start Latitude", value=center_lat, format="%.6f")
            start_lon = st.number_input("Start Longitude", value=center_lon, format="%.6f")
            
        nodes_list = list(G.nodes())
        sample_dest = nodes_list[min(20, len(nodes_list)-1)]
        
        dest_lat = st.number_input("Destination Latitude", value=float(G.nodes[sample_dest]['y']), format="%.6f")
        dest_lon = st.number_input("Destination Longitude", value=float(G.nodes[sample_dest]['x']), format="%.6f")
        
        calc_route_btn = st.button("🚀 Calculate Safe Alternate Route", type="primary")
        
        st.markdown("---")
        st.markdown("#### 🌤️ Live Environmental Intelligence")
        weather = get_live_weather(start_lat, start_lon)
        st.markdown(f"""
        <div class="weather-box">
            <b>Hazard Status:</b> {weather['condition']}<br>
            🌡️ <b>Temperature:</b> {weather['temp']}°C &nbsp;|&nbsp; 💧 <b>Humidity:</b> {weather['humidity']}%<br>
            💨 <b>Wind Speed:</b> {weather['wind']} km/h
        </div>
        """, unsafe_allow_html=True)

    with col_r:
        st.markdown("#### 🛰️ Real-Time Interactive GIS Map")
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14, control_scale=True)
        
        for disp in active_disruptions:
            _, d_name, d_lat, d_lon, d_reason, _ = disp
            folium.Marker(
                location=[d_lat, d_lon],
                popup=f"<b>⛔ ROAD CLOSED: {d_name}</b><br>Reason: {d_reason}",
                icon=folium.Icon(color="red", icon="ban", prefix="fa")
            ).add_to(m)
            folium.Circle(location=[d_lat, d_lon], radius=150, color='red', fill=True, fill_opacity=0.15).add_to(m)

        if calc_route_btn:
            try:
                orig_node = ox.distance.nearest_nodes(G_modified, X=start_lon, Y=start_lat)
                dest_node = ox.distance.nearest_nodes(G_modified, X=dest_lon, Y=dest_lat)
                
                route = networkx_lib.shortest_path(G_modified, orig_node, dest_node, weight='length')
                route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]
                
                total_length_m = sum(
                    ox.distance.great_circle_vec(
                        G.nodes[route[i]]['y'], G.nodes[route[i]]['x'],
                        G.nodes[route[i+1]]['y'], G.nodes[route[i+1]]['x']
                    ) for i in range(len(route)-1)
                )
                
                est_time_mins = round((total_length_m / 1000) / 30 * 60, 1)
                
                mc1, mc2, mc3 = st.columns(3)
                with mc1: st.metric("Route Status", "✅ Clear / Safe")
                with mc2: st.metric("Distance", f"{round(total_length_m/1000, 2)} km")
                with mc3: st.metric("Est. Travel Time", f"{est_time_mins} mins")
                
                folium.PolyLine(route_coords, color="#10B981", weight=6, opacity=0.85, tooltip="Safe Alternate Route").add_to(m)
                folium.Marker(location=[start_lat, start_lon], popup="Start Position", icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
                folium.Marker(location=[dest_lat, dest_lon], popup="Destination", icon=folium.Icon(color="green", icon="flag", prefix="fa")).add_to(m)

            except networkx_lib.NetworkXNoPath:
                st.error("⚠️ Critical Alert: All direct pathways are obstructed by active disruptions.")
            except Exception as ex:
                st.error(f"Routing computation error: {ex}")

        st_folium(m, width="100%", height=520)

# =============================================================
# VIEW 2: ADMIN EMERGENCY INCIDENT REPORT
# =============================================================
elif app_mode == "🚨 Admin Emergency Incident Report":
    st.subheader("🚨 Emergency Disruption & Disaster Reporting Portal")
    
    with st.form("admin_disruption_form"):
        col1, col2 = st.columns(2)
        with col1:
            loc_name = st.text_input("Location / Street / Junction Name", placeholder="e.g., Ring Road Flyover Junction")
            reason = st.selectbox("Disruption / Hazard Classification", [
                "Heavy Flooding / Severe Waterlogging 🌧️", 
                "Traffic Accident / Vehicle Crash 💥", 
                "Road Construction / Maintenance 🚧", 
                "Severe Weather Storm / Tree Fall ⚡"
            ])
        with col2:
            lat_input = st.number_input("Incident Latitude", value=center_lat, format="%.6f")
            lon_input = st.number_input("Incident Longitude", value=center_lon, format="%.6f")
            
        submit_incident = st.form_submit_button("📢 Broadcast Incident & Trigger Dynamic Rerouting", type="primary")
        
        if submit_incident:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO disruptions (location_name, lat, lon, reason, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (loc_name, lat_input, lon_input, reason, 'Blocked', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            st.success(f"Emergency broadcast successful for '{loc_name}'!")
            st.rerun()

# =============================================================
# VIEW 3: UPLOAD & REPORT HAZARD DATA (NEW FEATURE)
# =============================================================
elif app_mode == "📤 Upload & Report Hazard Data":
    st.subheader("📤 Bulk Hazard Data Upload & Citizen Submissions")
    st.markdown("Upload a CSV file containing multiple road incidents or hazard reports to instantly integrate them into the live routing network.")
    
    with st.expander("📌 View Required CSV Data Format", expanded=False):
        st.markdown("""
        Your uploaded CSV file must contain the following column headers:
        * `location_name` (Text description of the location)
        * `lat` (Latitude coordinate, e.g., 28.6315)
        * `lon` (Longitude coordinate, e.g., 77.2167)
        * `reason` (Description of hazard / block)
        """)
        
        # Sample CSV Download Option
        sample_df = pd.DataFrame({
            "location_name": ["Main Street Bridge", "Central Avenue Crossing"],
            "lat": [center_lat + 0.002, center_lat - 0.003],
            "lon": [center_lon + 0.002, center_lon - 0.003],
            "reason": ["Heavy Flooding / Waterlogging", "Road Accident"]
        })
        st.download_button(
            label="Download Sample CSV Template",
            data=sample_df.to_csv(index=False).encode('utf-8'),
            file_name="hazard_template.csv",
            mime="text/csv"
        )

    st.markdown("---")
    uploaded_file = st.file_uploader("Upload Incident CSV File", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            required_cols = ["location_name", "lat", "lon", "reason"]
            if all(col in df.columns for col in required_cols):
                st.dataframe(df, use_container_width=True)
                if st.button("📥 Import & Broadcast All Uploaded Incidents", type="primary"):
                    cursor = conn.cursor()
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for _, row in df.iterrows():
                        cursor.execute(
                            "INSERT INTO disruptions (location_name, lat, lon, reason, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                            (str(row['location_name']), float(row['lat']), float(row['lon']), str(row['reason']), 'Blocked', current_time)
                        )
                    conn.commit()
                    st.success(f"Successfully imported {len(df)} hazard records into the system database and triggered alternate rerouting!")
                    st.rerun()
            else:
                st.error("Uploaded CSV file is missing required columns. Please check the sample template format.")
        except Exception as e:
                st.error(f"Error reading uploaded file: {e}")

# =============================================================
# VIEW 4: MANAGE ACTIVE DISRUPTION ZONES
# =============================================================
elif app_mode == "🛠️ Manage Active Disruption Zones":
    st.subheader("🛠️ Active Emergency Incidents & Road Restoration")
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, timestamp FROM disruptions WHERE status = 'Blocked'")
    records = cursor.fetchall()
    
    if not records:
        st.info("✅ All zones are clear! No active road disruptions or weather hazards reported.")
    else:
        for rec in records:
            r_id, r_loc, r_lat, r_lon, r_reason, r_time = rec
            with st.container():
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**📍 Location:** {r_loc}")
                    st.markdown(f"**⚠️ Hazard Type:** {r_reason}")
                    st.caption(f"Reported Timestamp: {r_time} | Coordinates: ({r_lat}, {r_lon})")
                with cols[1]:
                    if st.button("🟢 Mark Restored / Open", key=f"restore_{r_id}"):
                        cursor.execute("UPDATE disruptions SET status = 'Resolved' WHERE id = ?", (r_id,))
                        conn.commit()
                        st.success(f"Road segment '{r_loc}' successfully restored to service!")
                        st.rerun()
                st.markdown("---")
