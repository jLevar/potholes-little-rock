import json
from pathlib import Path
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from folium.plugins import HeatMap


BASE_URL = "https://data.littlerock.gov/resource/2x6n-j9fb.json"
CACHE_FILE = Path("data.json")

def fetch_data():
    """Fetches fresh data from the API."""
    params = {
        "$limit": 5000,
        "$where": "issue_sub_category like '%Pothole%' AND ticket_status = 'Open' AND latitude IS NOT NULL",
        "$order": "ticket_created_date_time DESC"
    }
    
    print("Fetching data from Little Rock Open Data Portal...")
    response = requests.get(BASE_URL, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return []
    
    data = response.json()

    if not data:
        print("No 'Pothole' records found. The category names might have changed.")
        print("Fetching available categories to help you find the right one...")
        cat_params = {"$select": "issue_sub_category", "$group": "issue_sub_category", "$limit": 20}
        cat_response = requests.get(BASE_URL, params=cat_params)
        print(pd.DataFrame(cat_response.json()))
        exit()

    return data

# --- MAIN LOGIC ---

data = fetch_data()

if not data:
    print("No data available.")
    exit()

# print(f"Saving new data to cache ({CACHE_FILE})...")
# with CACHE_FILE.open("w", encoding="utf-8") as f:
#     json.dump(data, f, ensure_ascii=False, indent=2)

df = pd.DataFrame(data)

# Center map on Little Rock
lr_map = folium.Map(location=[34.7465, -92.2896], zoom_start=12)

def add_markers():
    marker_cluster = MarkerCluster().add_to(lr_map)

    for idx, row in df.iterrows():
        # Convert lat/lon to float
        try:
            lat = float(row['latitude'])
            lon = float(row['longitude'])
        except (ValueError, TypeError):
            continue

        # Color code: Open = Red, Closed = Green
        status = row.get('ticket_status', 'Unknown')
        color = 'red' if status == 'Open' else 'green'
        
        popup_text = f"""
        <b>Type:</b> {row.get('issue_sub_category', 'N/A')}<br>
        <b>Status:</b> {status}<br>
        <b>Date:</b> {row.get('ticket_created_date_time', 'N/A')}<br>
        <b>Address:</b> {row.get('street_address', 'N/A')}
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(marker_cluster)
  

def add_heat_clouds():
    heat_data = []

    for idx, row in df.iterrows():
        try:
            lat = float(row['latitude'])
            lon = float(row['longitude'])
            heat_data.append([lat, lon])
        except (ValueError, TypeError):
            continue

    # Add HeatMap layer
    HeatMap(
        heat_data, 
        radius=25, 
        blur=25, 
        min_opacity=0.4
    ).add_to(lr_map)

add_markers()

output_file = "map.html"
lr_map.save(output_file)
print(f"Map saved to {output_file}")