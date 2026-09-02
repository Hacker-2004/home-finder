import io
import json
import os
import random
import requests
import pandas as pd
from datetime import datetime

# Redfin Region IDs for Montgomery County & Bucks County, PA
COUNTIES = [
    {"name": "Montgomery County, PA", "id": "2406", "type": 5},
    {"name": "Bucks County, PA", "id": "2369", "type": 5}
]

MAX_PRICE = 600000
MIN_BEDS = 3
MIN_SQFT = 2000

# High-resolution house exterior images only (no cars or placeholders)
HOUSE_IMAGES = [
    "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1570129477492-45c003edd2be?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1598228723793-52759bba239c?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1572120360610-d971b9d7767c?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=600&q=80"
]

EXCLUDE_COLUMNS = [
    'SOLD DATE', 
    'NEXT OPEN HOUSE START TIME', 
    'NEXT OPEN HOUSE END TIME', 
    'LATITUDE', 
    'LONGITUDE', 
    'INTERESTED', 
    'FAVORITE'
]

EXCLUDED_CITIES = [
    "Abington", "Ardmore", "Bala Cynwyd", "Barto", "Boyertown", "Bristol", 
    "Bryn Mawr", "Cheltenham", "Coopersburg", "Crydon", "Croydon", "D1jpdy Silverdale", 
    "Silverdale", "Dresher", "Desher", "Dublin", "East Greenville", "Easton", 
    "Elkins Park", "Erdenheim", "Fairless Hills", "Feasterville Trevose", "Feasterville", 
    "Trevose", "Fountainville", "Furlong", "Gilbertsville", "Glenside", "Green Lane", 
    "Hatboro", "Huntingdon Valley", "Huntington valley", "Jamison", "Jenkintown", 
    "Kintnersville", "Lamott", "Langhorne", "Laverock", "Levittown", "Line Lexington", 
    "Melrose Park", "Mont Clare", "Morrisville", "morrisville", "Narberth", "New Britain", 
    "New Hope", "Newtown", "Ottsville", "Penn Wynne", "penn Wynne", "Pennsburg", 
    "Pennsburng", "Perkasie", "Perkaise", "Perkiomenville", "Philadelphia", "Quakertown", 
    "Red Hill", "Roslyn", "Rydal", "Sanatoga", "Schwenksville", "Sellersville", 
    "Southampton", "Springtown", "Telford", "Trappe", "Trapper", "Warminster", 
    "Warmister", "Warmister Township", "Warrington", "Warwick", "Wyncote", "wyncote", 
    "Wyndmoor", "wyndmoor", "Yardley", "yardley"
]

def load_previous_listings():
    previous_map = {}
    if os.path.exists('listings.json'):
        try:
            with open('listings.json', 'r') as f:
                old_data = json.load(f)
                for item in old_data:
                    url = item.get('url') or item.get('id')
                    if url:
                        previous_map[url] = {
                            "price": item.get('price', 0),
                            "original_price": item.get('original_price', item.get('price', 0)),
                            "price_change": item.get('price_change', 0),
                            "image": item.get('image', '')
                        }
        except Exception as e:
            print(f"Notice: Could not load previous listings for price tracking ({e})")
    return previous_map

def fetch_active_listings():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    previous_listings = load_previous_listings()
    all_dfs = []
    excluded_cities_set = {c.strip().upper() for c in EXCLUDED_CITIES}

    for county in COUNTIES:
        url = (
            f"https://www.redfin.com/stingray/api/gis-csv?"
            f"al=1&region_id={county['id']}&region_type={county['type']}&status=9&uipt=1,2,3,4"
            f"&max_price={MAX_PRICE}&num_beds={MIN_BEDS}&min_sqft={MIN_SQFT}"
        )
        
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200 and "SALE TYPE" in res.text:
                df = pd.read_csv(io.StringIO(res.text))
                
                # Enforce minimum square footage
                if 'SQUARE FEET' in df.columns:
                    df['SQUARE FEET'] = pd.to_numeric(df['SQUARE FEET'], errors='coerce').fillna(0)
                    df = df[df['SQUARE FEET'] >= MIN_SQFT]

                if 'STATE OR PROVINCE' in df.columns:
                    df = df[df['STATE OR PROVINCE'].astype(str).str.strip().str.upper() == 'PA']
                
                all_dfs.append(df)
        except Exception as e:
            print(f"Error fetching {county['name']}: {e}")

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        url_col = [c for c in combined_df.columns if "URL" in c]
        url_col_name = url_col[0] if url_col else combined_df.columns[0]
        
        combined_df = combined_df.drop_duplicates(subset=[url_col_name])

        if 'CITY' in combined_df.columns:
            combined_df = combined_df[
                ~combined_df['CITY'].astype(str).str.strip().str.upper().isin(excluded_cities_set)
            ]

        active_homes = []
        price_changes_for_excel = []
        original_prices_for_excel = []

        print("Processing listings...")
        for _, row in combined_df.iterrows():
            url_path = str(row.get(url_col_name, ''))
            full_url = url_path if url_path.startswith("http") else f"https://www.redfin.com{url_path}"

            current_price = int(row.get('PRICE', 0)) if pd.notna(row.get('PRICE')) else 0
            
            prev_info = previous_listings.get(full_url, {})
            original_price = prev_info.get("original_price", current_price)
            price_change = current_price - original_price

            price_changes_for_excel.append(price_change)
            original_prices_for_excel.append(original_price)

            beds = int(row.get('BEDS', 0)) if pd.notna(row.get('BEDS')) else 0
            baths = float(row.get('BATHS', 0)) if pd.notna(row.get('BATHS')) else 0
            sqft = int(row.get('SQUARE FEET', 0)) if pd.notna(row.get('SQUARE FEET')) else 0
            address = str(row.get('ADDRESS', '')) if pd.notna(row.get('ADDRESS')) else 'Address N/A'
            city = str(row.get('CITY', '')) if pd.notna(row.get('CITY')) else ''
            state = str(row.get('STATE OR PROVINCE', 'PA')) if pd.notna(row.get('STATE OR PROVINCE')) else 'PA'
            zip_code = str(row.get('ZIP OR POSTAL CODE', '')) if pd.notna(row.get('ZIP OR POSTAL CODE')) else ''

            # Check cached image; if it's missing or a car/placeholder, replace with a random house photo
            cached_img = prev_info.get("image", "")
            if not cached_img or "photo-1568605117036" in cached_img:
                image_url = random.choice(HOUSE_IMAGES)
            else:
                image_url = cached_img

            active_homes.append({
                "id": full_url,
                "address": address,
                "city": city,
                "state": state,
                "zip": zip_code,
                "price": current_price,
                "original_price": original_price,
                "price_change": price_change,
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "image": image_url,
                "url": full_url,
                "date_seen": datetime.now().strftime('%Y-%m-%d')
            })

        combined_df['ORIGINAL_PRICE'] = original_prices_for_excel
        combined_df['PRICE_CHANGE'] = price_changes_for_excel

        if 'CITY' in combined_df.columns:
            combined_df['IS_PLYMOUTH'] = combined_df['CITY'].astype(str).str.strip().str.upper() == 'PLYMOUTH MEETING'
            combined_df = combined_df.sort_values(by=['IS_PLYMOUTH', 'PRICE'], ascending=[False, True]).drop(columns=['IS_PLYMOUTH'])

        cols_to_drop = [c for c in combined_df.columns if c.strip().upper() in [x.upper() for x in EXCLUDE_COLUMNS]]
        excel_df = combined_df.drop(columns=cols_to_drop, errors='ignore')

        excel_df.to_excel('homes.xlsx', index=False)

        with open('listings.json', 'w') as f:
            json.dump(active_homes, f, indent=2)

        print(f"Successfully processed {len(combined_df)} listings with house photos!")
    else:
        with open('listings.json', 'w') as f:
            json.dump([], f)
        pd.DataFrame().to_excel('homes.xlsx', index=False)

if __name__ == "__main__":
    fetch_active_listings()
