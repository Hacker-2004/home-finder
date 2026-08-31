import io
import json
import requests
import pandas as pd
from datetime import datetime

# Redfin region query strings (Towns & Counties)
TARGET_LOCATIONS = [
    # Full Counties
    {"name": "Montgomery County, PA", "id": "1996", "type": 5},
    {"name": "Bucks County, PA", "id": "1867", "type": 5},
    # Specific Towns (Fallback in case county bounds filter too strictly)
    {"name": "Doylestown", "id": "5096", "type": 6},
    {"name": "Lansdale", "id": "10688", "type": 6},
    {"name": "Collegeville", "id": "4026", "type": 6},
    {"name": "Hatfield", "id": "8680", "type": 6},
    {"name": "Harleysville", "id": "8573", "type": 6},
    {"name": "Norristown", "id": "13702", "type": 6},
    {"name": "Conshohocken", "id": "4220", "type": 6}
]

MAX_PRICE = 600000
MIN_BEDS = 3
MIN_SQFT = 2000

def fetch_active_listings():
    # Full browser headers to prevent GitHub Action runner blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    active_homes = []
    seen_urls = set()

    for loc in TARGET_LOCATIONS:
        # Fetch properties with price & beds filter (SqFt filtered in Python to avoid API drop-offs)
        url = (
            f"https://www.redfin.com/stingray/api/gis-csv?"
            f"al=1&region_id={loc['id']}&region_type={loc['type']}&status=1&uipt=1,2,3,4"
            f"&max_price={MAX_PRICE}&num_beds={MIN_BEDS}"
        )
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and "SALE TYPE" in res.text:
                df = pd.read_csv(io.StringIO(res.text))
                df.columns = [c.strip().upper() for c in df.columns]
                
                for _, row in df.iterrows():
                    # Filter SqFt locally in Python
                    sqft = int(row.get('SQUARE FEET', 0)) if pd.notna(row.get('SQUARE FEET')) else 0
                    price = int(row.get('PRICE', 0)) if pd.notna(row.get('PRICE')) else 0
                    beds = int(row.get('BEDS', 0)) if pd.notna(row.get('BEDS')) else 0

                    if price <= MAX_PRICE and beds >= MIN_BEDS and sqft >= MIN_SQFT:
                        url_path = str(row.get('URL (SEE HTTPS://WWW.REDFIN.COM/LOCATION)', ''))
                        if not url_path or url_path == 'nan':
                            continue
                        
                        full_url = url_path if url_path.startswith("http") else f"https://www.redfin.com{url_path}"
                        
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)
                        
                        img_url = str(row.get('IMAGE URL', ''))
                        if not img_url or img_url == 'nan':
                            img_url = "https://ssl.cdn-redfin.com/photo/site/no-photo.jpg"

                        active_homes.append({
                            "id": str(row.get('PROPERTY ID', url_path)),
                            "address": str(row.get('ADDRESS', '')),
                            "city": str(row.get('CITY', loc['name'])),
                            "state": str(row.get('STATE OR PROVINCE', 'PA')),
                            "zip": str(row.get('ZIP OR POSTAL CODE', '')),
                            "price": price,
                            "beds": beds,
                            "baths": float(row.get('BATHS', 0)) if pd.notna(row.get('BATHS')) else 0,
                            "sqft": sqft,
                            "url": full_url,
                            "image": img_url,
                            "date_seen": datetime.now().strftime('%Y-%m-%d')
                        })
        except Exception as e:
            print(f"Error querying {loc['name']}: {e}")

    # Write listings.json
    with open('listings.json', 'w') as f:
        json.dump(active_homes, f, indent=2)

    # Write homes.xlsx
    df_excel = pd.DataFrame(active_homes if active_homes else [], columns=[
        "id", "address", "city", "state", "zip", "price", "beds", "baths", "sqft", "url", "image", "date_seen"
    ])
    df_excel.to_excel('homes.xlsx', index=False)
    
    print(f"Successfully updated feed: {len(active_homes)} active homes found.")

if __name__ == "__main__":
    fetch_active_listings()
