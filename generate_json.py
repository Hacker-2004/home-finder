import io
import json
import requests
import pandas as pd
from datetime import datetime

# Redfin Region IDs (5 = County level)
# 1996 = Montgomery County, PA | 1867 = Bucks County, PA
COUNTIES = [
    {"name": "Montgomery County, PA", "id": "1996"},
    {"name": "Bucks County, PA", "id": "1867"}
]

MAX_PRICE = 600000
MIN_BEDS = 3
MIN_SQFT = 2000

def fetch_active_listings():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    active_homes = []
    seen_urls = set()

    for county in COUNTIES:
        url = (
            f"https://www.redfin.com/stingray/api/gis-csv?"
            f"al=1&region_id={county['id']}&region_type=5&status=1&uipt=1,2,3,4"
            f"&max_price={MAX_PRICE}&num_beds={MIN_BEDS}&sqft_min={MIN_SQFT}"
        )
        
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200 and "SALE TYPE" in res.text:
                df = pd.read_csv(io.StringIO(res.text))
                
                # Clean column headers
                df.columns = [c.strip().upper() for c in df.columns]
                
                # Identify exact URL column from Redfin's header
                url_col = [c for c in df.columns if "URL" in c]
                url_col_name = url_col[0] if url_col else 'URL'

                for _, row in df.iterrows():
                    url_path = str(row.get(url_col_name, ''))
                    if not url_path or url_path == 'nan':
                        continue
                    
                    full_url = url_path if url_path.startswith("http") else f"https://www.redfin.com{url_path}"
                    
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # Extract values cleanly with fallbacks
                    price = int(row.get('PRICE', 0)) if pd.notna(row.get('PRICE')) else 0
                    beds = int(row.get('BEDS', 0)) if pd.notna(row.get('BEDS')) else 0
                    baths = float(row.get('BATHS', 0)) if pd.notna(row.get('BATHS')) else 0
                    sqft = int(row.get('SQUARE FEET', 0)) if pd.notna(row.get('SQUARE FEET')) else 0
                    address = str(row.get('ADDRESS', '')) if pd.notna(row.get('ADDRESS')) else 'Address N/A'
                    city = str(row.get('CITY', '')) if pd.notna(row.get('CITY')) else 'PA'
                    state = str(row.get('STATE OR PROVINCE', 'PA')) if pd.notna(row.get('STATE OR PROVINCE')) else 'PA'
                    zip_code = str(row.get('ZIP OR POSTAL CODE', '')) if pd.notna(row.get('ZIP OR POSTAL CODE')) else ''
                    
                    # Generate visual card image placeholder with city & address label
                    image_placeholder = f"https://via.placeholder.com/400x250/2563eb/ffffff?text={city.replace(' ', '+')}"

                    active_homes.append({
                        "id": full_url,
                        "address": address,
                        "city": city,
                        "state": state,
                        "zip": zip_code,
                        "price": price,
                        "beds": beds,
                        "baths": baths,
                        "sqft": sqft,
                        "url": full_url,
                        "image": image_placeholder,
                        "date_seen": datetime.now().strftime('%Y-%m-%d')
                    })
        except Exception as e:
            print(f"Error processing {county['name']}: {e}")

    # Write listings.json
    with open('listings.json', 'w') as f:
        json.dump(active_homes, f, indent=2)

    # Write homes.xlsx
    df_excel = pd.DataFrame(active_homes if active_homes else [], columns=[
        "address", "city", "state", "zip", "price", "beds", "baths", "sqft", "url", "date_seen"
    ])
    df_excel.to_excel('homes.xlsx', index=False)
    
    print(f"Successfully updated feed: {len(active_homes)} active homes found.")

if __name__ == "__main__":
    fetch_active_listings()
