import streamlit as st
import osmnx as ox
import networkx as networkx_lib
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime
import requests

# Page Configuration
st.set_page_config(
    page_title="RouteSafe – Smart Alternate Route Recommendation System",
    page_icon="🚦",
    layout="wide"
)

# Initialize Database for Disruption Reports
def init_db():
    conn = sqlite3.connect('disruptions.db', check_same_thread=False)
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

# Custom CSS Styling
st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0px; }
    .sub-title { font-size: 1.1rem; color: #4B5563; margin-bottom: 20px; }
    .weather-card { background-color: #EFF6FF; padding: 12px; border-radius: 8px; border: 1px solid #BFDBFE; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🚦 RouteSafe</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Smart Alternate Route Recommendation System with Live GPS & Weather Intelligence</p>', unsafe_allow_html=True)

# Sidebar Controls
st.sidebar.title("Navigation & Controls")
app_mode = st.sidebar.radio("Select Mode", ["Live Citizen Navigation", "Admin Disruption Control", "Manage Active Incidents"])

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Region Settings")
place_name = st.sidebar.text_input("Target Area (City/Neighborhood)", value="Connaught Place, New Delhi, India")

@st.cache_resource(show_spinner="Loading road network data from OpenStreetMap...")
def load_road_network(place):
    try:
        ox.settings.timeout = 60
        G = ox.graph_from_place(place, network_type='drive')
        return G
    except Exception as e:
        st.error(f"Could not load map for '{place}'. Error: {e}")
        return None

G = load_road_network(place_name)

if G is None:
    st.warning("Please enter a valid region in the sidebar to load the road network.")
    st.stop()

# Helper: Fetch Live Weather using Open-Meteo API (No API Key Required)
def get_live_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        res = requests.get(url).json()
        current = res.get("current", {})
        
        # Weather code mapping representation
        w_code = current.get("weather_code", 0)
        condition = "Clear Sky ☀️"
        if w_code in [1, 2, 3]: condition = "Partly Cloudy ⛅"
        elif w_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: condition = "Heavy Rain / Flooding Risk 🌧️"
        elif w_code in [45, 48]: condition = "Foggy / Low Visibility 🌫️"
        elif w_code >= 95: condition = "Thunderstorm / Severe Weather ⛈️"
        
        return {
            "temp": current.get("temperature_2m", 25),
            "humidity": current.get("relative_humidity_2m", 50),
            "wind": current.get("wind_speed_10m", 10),
            "condition": condition
        }
    except Exception:
        return {"temp": 25, "humidity": 50, "wind": 10, "condition": "Unavailable ☀️"}

# Helper to fetch active disruptions from DB
def get_active_disruptions():
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, status FROM disruptions WHERE status = 'Blocked'")
    return cursor.fetchall()

active_disruptions = get_active_disruptions()

# Apply disruptions to graph copy
G_modified = G.copy()
for disp in active_disruptions:
    d_id, d_name, d_lat, d_lon, d_reason, d_status = disp
    try:
        nearest_node = ox.distance.nearest_nodes(G_modified, X=d_lon, Y=d_lat)
        if nearest_node in G_modified:
            G_modified.remove_node(nearest_node)
    except Exception:
        pass

# --- MODE 1: CITIZEN NAVIGATION ---
if app_mode == "Live Citizen Navigation":
    st.subheader("🗺️ Live GPS Navigation & Alternate Rerouting")
    
    # Calculate Center of Map
    center_lat = sum(data['y'] for _, data in G.nodes(data=True)) / len(G.nodes())
    center_lon = sum(data['x'] for _, data in G.nodes(data=True)) / len(G.nodes())
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### 📍 Trip Planner")
        
        # GPS Simulation / Inputs
        use_gps = st.checkbox("Use Default Region Center as Start Position", value=True)
        if use_gps:
            start_lat, start_lon = center_lat, center_lon
            st.info(f"Using live region center coordinates: ({round(start_lat, 4)}, {round(start_lon, 4)})")
        else:
            start_lat = st.number_input("Start Latitude", value=center_lat, format="%.6f")
            start_lon = st.number_input("Start Longitude", value=center_lon, format="%.6f")
            
        nodes_list = list(G.nodes())
        default_dest_node = nodes_list[min(15, len(nodes_list)-1)]
        
        dest_lat = st.number_input("Destination Latitude", value=float(G.nodes[default_dest_node]['y']), format="%.6f")
        dest_lon = st.number_input("Destination Longitude", value=float(G.nodes[default_dest_node]['x']), format="%.6f")
        
        calc_route = st.button("Calculate Safe Route", type="primary")
        
        # Live Weather Widget for Current Coordinates
        st.markdown("---")
        st.markdown("#### 🌤️ Live Local Weather Condition")
        weather = get_live_weather(start_lat, start_lon)
        st.markdown(f"""
        <div class="weather-card">
            <b>Condition:</b> {weather['condition']}<br>
            <b>Temperature:</b> {weather['temp']}°C &nbsp;|&nbsp; <b>Humidity:</b> {weather['humidity']}%<br>
            <b>Wind Speed:</b> {weather['wind']} km/h
        </div>
        """, unsafe_allow_html=True)

    with col2:
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
        
        # Plot active disruptions
        for disp in active_disruptions:
            _, d_name, d_lat, d_lon, d_reason, _ = disp
            folium.Marker(
                location=[d_lat, d_lon],
                popup=f"<b>Blocked: {d_name}</b><br>Reason: {d_reason}",
                icon=folium.Icon(color="red", icon="ban", prefix="fa")
            ).add_to(m)

        if calc_route:
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
                
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.metric("Safe Route Distance", f"{round(total_length_m/1000, 2)} km")
                with rc2:
                    st.metric("Estimated Travel Time", f"{est_time_mins} mins")
                
                folium.PolyLine(route_coords, color="green", weight=6, opacity=0.85, tooltip="Safe Alternate Route").add_to(m)
                folium.Marker(location=[start_lat, start_lon], popup="Start Position", icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
                folium.Marker(location=[dest_lat, dest_lon], popup="Destination", icon=folium.Icon(color="green", icon="flag", prefix="fa")).add_to(m)

            except networkx_lib.NetworkXNoPath:
                st.error("⚠️ No safe path available! The target area is entirely cut off by active disruptions or severe weather closures.")
            except Exception as ex:
                st.error(f"Routing error: {ex}")

        st_map = st_folium(m, width="100%", height=480)

# --- MODE 2: ADMIN DISRUPTION CONTROL ---
elif app_mode == "Admin Disruption Control":
    st.subheader("🚨 Admin Portal: Broadcast Disruption")
    
    with st.form("disruption_form"):
        col1, col2 = st.columns(2)
        with col1:
            loc_name = st.text_input("Location / Street Name", placeholder="e.g., Main Arterial Road Junction")
            reason = st.selectbox("Disruption Type", ["Heavy Flooding / Waterlogged", "Road Accident / Crash", "Road Construction / Maintenance", "Severe Weather / Storm Damage"])
        with col2:
            lat_input = st.number_input("Latitude", value=center_lat, format="%.6f")
            lon_input = st.number_input("Longitude", value=center_lon, format="%.6f")
            
        submitted = st.form_submit_button("Broadcast Incident & Trigger Rerouting", type="primary")
        
        if submitted:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO disruptions (location_name, lat, lon, reason, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (loc_name, lat_input, lon_input, reason, 'Blocked', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            st.success(f"Incident at '{loc_name}' registered successfully! Citizens' navigation systems have been automatically updated.")
            st.rerun()

# --- MODE 3: MANAGE ACTIVE INCIDENTS ---
elif app_mode == "Manage Active Incidents":
    st.subheader("🛠️ Active Incidents & Road Restoration")
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, timestamp FROM disruptions WHERE status = 'Blocked'")
    records = cursor.fetchall()
    
    if not records:
        st.info("No active road disruptions reported. All routes are operating normally!")
    else:
        for rec in records:
            r_id, r_loc, r_lat, r_lon, r_reason, r_time = rec
            with st.container():
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**Location:** {r_loc} | **Reason:** {r_reason}")
                    st.caption(f"Reported at: {r_time} | Coordinates: ({r_lat}, {r_lon})")
                with cols[1]:
                    if st.button("Mark Restored / Open", key=f"restore_{r_id}"):
                        cursor.execute("UPDATE disruptions SET status = 'Resolved' WHERE id = ?", (r_id,))
                        conn.commit()
                        st.success(f"Road {r_loc} cleared and reopened!")
                        st.rerun()
                st.markdown("---")
