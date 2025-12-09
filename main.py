from pathlib import Path
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from folium.plugins import HeatMap
import re
from collections import Counter



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

def generate_dashboard_html(df):
    """Generates a text-based HTML dashboard of top streets and intersections."""
    
    # --- 1. Top Streets Logic ---
    street_names = []
    intersections = []
    
    for address in df['street_address'].dropna():
        address = str(address).upper().strip()
        
        # Check if it's an intersection
        if '&' in address or ' AND ' in address or '/' in address:
            intersections.append(address)
        else:
            # Clean street names
            clean_street = re.sub(r'^\d+\s+', '', address)
            clean_street = clean_street.replace("BLOCK OF ", "")
            street_names.append(clean_street)

    # Get Top 10 Streets
    top_streets = Counter(street_names).most_common(10)
    
    # Get Intersections (Filter: Must have > 1 pothole)
    # We grab the top 10 candidates first, then filter out the singles
    raw_intersections = Counter(intersections).most_common(10)
    valid_intersections = [(name, count) for name, count in raw_intersections if count > 1]
    
    # --- 2. Build the HTML ---
    # Start the HTML structure
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; padding: 20px; color: #333; }}
            h2 {{ border-bottom: 2px solid #0e6394; padding-bottom: 10px; color: #e74c3c; font-size: 1.2em; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ 
                background: #f9f9f9; 
                margin: 5px 0; 
                padding: 10px; 
                border-left: 5px solid #0e6394; 
                display: flex; 
                justify-content: space-between;
                font-size: 0.9em;
            }}
            .count {{ font-weight: bold; color: #555; }}
            .footer {{ margin-top: 20px; font-size: 0.8em; color: #777; text-align: center;}}
        </style>
    </head>
    <body>
        <h2>Streets with Most Potholes</h2>
        <ul>
            {''.join([f'<li><span>{name.title()}</span> <span class="count">{count} Potholes</span></li>' for name, count in top_streets])}
        </ul>
    """
    
    # CONDITIONAL SECTION: Only add Intersections if we have valid ones
    if valid_intersections:
        html_content += f"""
        <h2>Top Intersections</h2>
        <ul>
            {''.join([f'<li><span>{name.title()}</span> <span class="count">{count} Potholes</span></li>' for name, count in valid_intersections])}
        </ul>
        """
        
    # Close out the HTML
    html_content += f"""
        <div class="footer">
            Data updated: {pd.Timestamp.now().strftime('%Y-%m-%d')}
        </div>
    </body>
    </html>
    """
    
    # --- 3. Save the file ---
    output_path = Path("pothole_stats.html")
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard saved to {output_path}")


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