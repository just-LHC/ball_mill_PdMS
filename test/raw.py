import os
import ssl
import requests
import urllib3

# Global SSL bypass for test environment
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL = "justice.wiruu.ext@holcim.com"      # Replace with your email
PASSWORD = "wj0fgjx6"      # Replace with your password
BASE_URL = "https://v3back-demo.i-sense.io/api/i-sense-v3"

TARGET_MEASURE_ID = 33
POSSIBLE_ASSET_IDS = [92, 93, 94, 95]

session = requests.Session()
session.verify = False

try:
    print("Authenticating...")
    res = session.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    res.raise_for_status()
    token = res.json().get("token") or res.json()["data"]["token"]
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    print(f"\nHunting for raw Wave Spectrum (Type 4) for Measure ID {TARGET_MEASURE_ID}...")
    
    for asset_id in POSSIBLE_ASSET_IDS:
        url = f"{BASE_URL}/tenant/signals/{asset_id}/{TARGET_MEASURE_ID}/4"
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"\n✔ SUCCESS! Measurement {TARGET_MEASURE_ID} belongs to sub-asset {asset_id}.")
            raw_data = response.json().get("data", {})
            if isinstance(raw_data, dict):
                print(f"Available array data: {list(raw_data.keys())}")
            break
        else:
            print(f"✖ Asset {asset_id}: Forbidden (Status {response.status_code})")

except Exception as e:
    print(f"\n[Error]: {e}")