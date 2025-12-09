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

import re
from collections import Counter

def generate_dashboard_html(df):
    """Generates a text-based HTML dashboard of top streets and intersections."""
    
    # --- 1. Top Streets Logic ---
    # We strip out the house numbers to group by Street Name
    # e.g., "1200 W Markham" becomes "W Markham"
    street_names = []
    intersections = []
    
    for address in df['street_address'].dropna():
        address = str(address).upper().strip()
        
        # Check if it's an intersection
        if '&' in address or ' AND ' in address or '/' in address:
            intersections.append(address)
        else:
            # Regex: Remove leading numbers (e.g. "123 Main" -> "Main")
            clean_street = re.sub(r'^\d+\s+', '', address)
            # Optional: Remove "Block Of" if present
            clean_street = clean_street.replace("BLOCK OF ", "")
            street_names.append(clean_street)

    # Get Top 10s
    top_streets = Counter(street_names).most_common(10)
    top_intersections = Counter(intersections).most_common(5)
    
    # --- 2. Build the HTML ---
    # We use simple CSS to make it look like the blog post style
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; padding: 20px; color: #333; }}
            h2 {{ border-bottom: 2px solid #e74c3c; padding-bottom: 10px; color: #e74c3c; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ 
                background: #f9f9f9; 
                margin: 5px 0; 
                padding: 10px; 
                border-left: 5px solid #e74c3c; 
                display: flex; 
                justify-content: space-between;
            }}
            .count {{ font-weight: bold; color: #555; }}
            .footer {{ margin-top: 20px; font-size: 0.8em; color: #777; }}
        </style>
    </head>
    <body>
        <h2>Streets with Most Potholes</h2>
        <ul>
            {''.join([f'<li><span>{name.title()}</span> <span class="count">{count} Potholes</span></li>' for name, count in top_streets])}
        </ul>

        <h2>Top Intersections</h2>
        <ul>
            {''.join([f'<li><span>{name.title()}</span> <span class="count">{count} Potholes</span></li>' for name, count in top_intersections])}
        </ul>
        
        <div class="footer">
            Data updated automatically: {pd.Timestamp.now().strftime('%Y-%m-%d')}
        </div>
    </body>
    </html>
    """
    
    # --- 3. Save the file ---
    with open("pothole_stats.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Dashboard saved to pothole_stats.html")


# --- MAIN LOGIC ---

data = fetch_data()

if not data:
    print("No data available.")
    exit()

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

generate_dashboard_html(df)