import io
import json
import requests
import pandas as pd
from datetime import datetime

# Redfin Region IDs (5 = County)
# 1996 = Montgomery County, PA | 1867 = Bucks County, PA
COUNTIES = ["1996", "1867"]
MAX_PRICE = 600000
MIN_BEDS = 3
MIN_SQFT = 2000

def fetch_active_listings():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    active_homes = []
    seen_urls = set()

    for region_id in COUNTIES:
        url = (
            f"https://www.redfin.com/stingray/api/gis-csv?"
            f"al=1&region_id={region_id}&region_type=5&status=1&uipt=1,2,3,4"
            f"&max_price={MAX_PRICE}&num_beds={MIN_BEDS}&sqft_min={MIN_SQFT}"
        )
        
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200 and "SALE TYPE" in res.text:
                df = pd.read_csv(io.StringIO(res.text))
                df.columns = [c.strip().upper() for c in df.columns]
                
                for _, row in df.iterrows():
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
                        "city": str(row.get('CITY', '')),
                        "state": str(row.get('STATE OR PROVINCE', 'PA')),
                        "zip": str(row.get('ZIP OR POSTAL CODE', '')),
                        "price": int(row.get('PRICE', 0)),
                        "beds": int(row.get('BEDS', 0)),
                        "baths": float(row.get('BATHS', 0)),
                        "sqft": int(row.get('SQUARE FEET', 0)),
                        "url": full_url,
                        "image": img_url,
                        "date_seen": datetime.now().strftime('%Y-%m-%d')
                    })
        except Exception as e:
            print(f"Error processing region {region_id}: {e}")

    # Overwrite listings.json (Auto-deletes sold homes!)
    with open('listings.json', 'w') as f:
        json.dump(active_homes, f, indent=2)

    # Optional local/repo Excel copy
    if active_homes:
        df_excel = pd.DataFrame(active_homes)
        df_excel.to_excel('homes.xlsx', index=False)
    
    print(f"Successfully updated feed: {len(active_homes)} active homes found.")

if __name__ == "__main__":
    fetch_active_listings()
