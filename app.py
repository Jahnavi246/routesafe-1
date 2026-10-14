import streamlit as st
import osmnx as ox
import networkx as networkx_lib
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime

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
    .metric-card { background-color: #F3F4F6; padding: 15px; border-radius: 8px; border-left: 5px solid #3B82F6; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🚦 RouteSafe</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Smart Alternate Route Recommendation System for Emergency & Weather Disruption Management</p>', unsafe_allow_html=True)

# Sidebar Navigation & Admin Controls
st.sidebar.title("Navigation & Controls")
app_mode = st.sidebar.radio("Select Mode", ["Live Citizen Navigation", "Admin Disruption Control", "Manage Active Incidents"])

# Default Location Preset (e.g., Connaught Place, New Delhi or custom coords)
st.sidebar.markdown("---")
st.sidebar.subheader("📍 Region Settings")
place_name = st.sidebar.text_input("Target Area (City/Neighborhood)", value="Connaught Place, New Delhi, India")

@st.cache_resource(show_spinner="Loading road network data from OpenStreetMap...")
def load_road_network(place):
    try:
        # Download road network graph for driving
        G = ox.graph_from_place(place, network_type='drive')
        return G
    except Exception as e:
        st.error(f"Could not load map for '{place}'. Error: {e}")
        return None

G = load_road_network(place_name)

if G is None:
    st.warning("Please enter a valid city or landmark region in the sidebar to load the road network.")
    st.stop()

# Helper to fetch active disruptions from DB
def get_active_disruptions():
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, status FROM disruptions WHERE status = 'Blocked'")
    return cursor.fetchall()

active_disruptions = get_active_disruptions()

# Apply disruptions to graph copy
G_modified = G.copy()
# Simple simulation: find nearest nodes to reported disruptions and disable edges connected to them
for disp in active_disruptions:
    d_id, d_name, d_lat, d_lon, d_reason, d_status = disp
    try:
        nearest_node = ox.distance.nearest_nodes(G_modified, X=d_lon, Y=d_lat)
        # Remove outgoing/incoming edges of the blocked node to simulate complete blockage
        if nearest_node in G_modified:
            G_modified.remove_node(nearest_node)
    except Exception:
        pass

# --- MODE 1: CITIZEN NAVIGATION ---
if app_mode == "Live Citizen Navigation":
    st.subheader("🗺️ Citizen Safe Navigation & Rerouting")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Plan Your Journey")
        # Let user select start and end points via text or coordinates, or pick nodes
        nodes_list = list(G.nodes())
        
        # For user friendliness, let's pick sample nodes or allow coordinate entry
        start_lat = st.number_input("Start Latitude", value=float(G.nodes[nodes_list[0]]['y']))
        start_lon = st.number_input("Start Longitude", value=float(G.nodes[nodes_list[0]]['x']))
        
        end_lat = st.number_input("Destination Latitude", value=float(G.nodes[nodes_list[min(10, len(nodes_list)-1)]]['y']))
        end_lon = st.number_input("Destination Longitude", value=float(G.nodes[nodes_list[min(10, len(nodes_list)-1)]]['x']))
        
        calc_route = st.button("Calculate Safe Route", type="primary")

    with col2:
        # Center map around graph center
        center_lat = sum(data['y'] for _, data in G.nodes(data=True)) / len(G.nodes())
        center_lon = sum(data['x'] for _, data in G.nodes(data=True)) / len(G.nodes())
        
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
                dest_node = ox.distance.nearest_nodes(G_modified, X=end_lon, Y=end_lat)
                
                # Compute shortest path using NetworkX (weights by length)
                route = networkx_lib.shortest_path(G_modified, orig_node, dest_node, weight='length')
                
                # Extract route coordinates for folium
                route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]
                
                # Calculate total distance
                total_length_m = sum(
                    ox.distance.great_circle_vec(
                        G.nodes[route[i]]['y'], G.nodes[route[i]]['x'],
                        G.nodes[route[i+1]]['y'], G.nodes[route[i+1]]['x']
                    ) for i in range(len(route)-1)
                )
                
                # Estimate travel time (assuming 30 km/h average city speed)
                est_time_mins = round((total_length_m / 1000) / 30 * 60, 1)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Estimated Distance", f"{round(total_length_m/1000, 2)} km")
                with col_b:
                    st.metric("Estimated Travel Time", f"{est_time_mins} mins")
                
                # Draw safe route line
                folium.PolyLine(route_coords, color="green", weight=5, opacity=0.8, tooltip="Recommended Safe Alternate Route").add_to(m)
                folium.Marker(location=[start_lat, start_lon], icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
                folium.Marker(location=[end_lat, end_lon], icon=folium.Icon(color="green", icon="flag", prefix="fa")).add_to(m)

            except networkx_lib.NetworkXNoPath:
                st.error("No safe route available! All paths might be blocked by current disruptions.")
            except Exception as ex:
                st.error(f"Routing calculation error: {ex}")

        st_map = st_folium(m, width="100%", height=450)

# --- MODE 2: ADMIN DISRUPTION CONTROL ---
elif app_mode == "Admin Disruption Control":
    st.subheader("🚨 Admin Portal: Report Road Disruption")
    
    with st.form("disruption_form"):
        col1, col2 = st.columns(2)
        with col1:
            loc_name = st.text_input("Location / Street Name", placeholder="e.g., Main Street Bridge")
            reason = st.selectbox("Disruption Type", ["Heavy Flooding / Waterlogging", "Road Accident", "Construction / Maintenance", "Landfall / Road Cave-in"])
        with col2:
            # Let admin click or provide coordinates
            lat_input = st.number_input("Latitude", value=sum(data['y'] for _, data in G.nodes(data=True)) / len(G.nodes()), format="%.6f")
            lon_input = st.number_input("Longitude", value=sum(data['x'] for _, data in G.nodes(data=True)) / len(G.nodes()), format="%.6f")
            
        submitted = st.form_submit_button("Broadcast Disruption & Trigger Rerouting", type="primary")
        
        if submitted:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO disruptions (location_name, lat, lon, reason, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (loc_name, lat_input, lon_input, reason, 'Blocked', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            st.success(f"Disruption at '{loc_name}' successfully registered and broadcasted! Alternate routing systems updated.")
            st.rerun()

# --- MODE 3: MANAGE ACTIVE INCIDENTS ---
elif app_mode == "Manage Active Incidents":
    st.subheader("🛠️ Active Incidents & Road Restoration")
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, location_name, lat, lon, reason, timestamp FROM disruptions WHERE status = 'Blocked'")
    records = cursor.fetchall()
    
    if not records:
        st.info("No active road disruptions reported. All routes clear!")
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
                        st.success(f"Road {r_loc} restored!")
                        st.rerun()
                st.markdown("---")
