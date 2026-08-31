import io
import json
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

# Columns to exclude from homes.xlsx
EXCLUDE_COLUMNS = [
    'SOLD DATE', 
    'NEXT OPEN HOUSE START TIME', 
    'NEXT OPEN HOUSE END TIME', 
    'LATITUDE', 
    'LONGITUDE', 
    'INTERESTED', 
    'FAVORITE'
]

def fetch_active_listings():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    all_dfs = []

    for county in COUNTIES:
        url = (
            f"https://www.redfin.com/stingray/api/gis-csv?"
            f"al=1&region_id={county['id']}&region_type={county['type']}&status=1&uipt=1,2,3,4"
            f"&max_price={MAX_PRICE}&num_beds={MIN_BEDS}&sqft_min={MIN_SQFT}"
        )
        
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200 and "SALE TYPE" in res.text:
                df = pd.read_csv(io.StringIO(res.text))
                
                # Filter strictly for Pennsylvania listings
                if 'STATE OR PROVINCE' in df.columns:
                    df = df[df['STATE OR PROVINCE'].astype(str).str.strip().str.upper() == 'PA']
                
                all_dfs.append(df)
        except Exception as e:
            print(f"Error fetching {county['name']}: {e}")

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # Locate URL column for deduplication
        url_col = [c for c in combined_df.columns if "URL" in c]
        url_col_name = url_col[0] if url_col else combined_df.columns[0]
        
        # Remove duplicate rows based on listing URL
        combined_df = combined_df.drop_duplicates(subset=[url_col_name])

        # Sort so Plymouth Meeting homes appear at the top of the Excel sheet
        if 'CITY' in combined_df.columns:
            combined_df['IS_PLYMOUTH'] = combined_df['CITY'].astype(str).str.upper() == 'PLYMOUTH MEETING'
            combined_df = combined_df.sort_values(by=['IS_PLYMOUTH', 'PRICE'], ascending=[False, True]).drop(columns=['IS_PLYMOUTH'])

        # Drop specified excluded columns
        cols_to_drop = [c for c in combined_df.columns if c.strip().upper() in [x.upper() for x in EXCLUDE_COLUMNS]]
        excel_df = combined_df.drop(columns=cols_to_drop, errors='ignore')

        # 1. Export sorted DataFrame to homes.xlsx
        excel_df.to_excel('homes.xlsx', index=False)

        # 2. Process listings.json for the web dashboard
        active_homes = []
        for _, row in combined_df.iterrows():
            url_path = str(row.get(url_col_name, ''))
            full_url = url_path if url_path.startswith("http") else f"https://www.redfin.com{url_path}"

            price = int(row.get('PRICE', 0)) if pd.notna(row.get('PRICE')) else 0
            beds = int(row.get('BEDS', 0)) if pd.notna(row.get('BEDS')) else 0
            baths = float(row.get('BATHS', 0)) if pd.notna(row.get('BATHS')) else 0
            sqft = int(row.get('SQUARE FEET', 0)) if pd.notna(row.get('SQUARE FEET')) else 0
            address = str(row.get('ADDRESS', '')) if pd.notna(row.get('ADDRESS')) else 'Address N/A'
            city = str(row.get('CITY', '')) if pd.notna(row.get('CITY')) else ''
            state = str(row.get('STATE OR PROVINCE', 'PA')) if pd.notna(row.get('STATE OR PROVINCE')) else 'PA'
            zip_code = str(row.get('ZIP OR POSTAL CODE', '')) if pd.notna(row.get('ZIP OR POSTAL CODE')) else ''

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
                "date_seen": datetime.now().strftime('%Y-%m-%d')
            })

        with open('listings.json', 'w') as f:
            json.dump(active_homes, f, indent=2)

        print(f"Successfully saved {len(combined_df)} listings!")
    else:
        with open('listings.json', 'w') as f:
            json.dump([], f)
        pd.DataFrame().to_excel('homes.xlsx', index=False)

if __name__ == "__main__":
    fetch_active_listings()
