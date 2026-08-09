import os
import requests
import hashlib
from urllib.parse import quote_plus


CLIENT_ID = "58581984514889"
API_KEY = "7cabuU8J8ZjGexlwXIG7tTkqSBukQNWp"

# Use the assets folder to cache downloaded icons
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "iconscout_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def search_and_download_3d_icon(keyword):
    """
    Searches IconScout for a 3D icon matching the keyword.
    Downloads the transparent PNG and caches it locally.
    Returns the absolute path to the local PNG file, or None if failed/not found.
    """
    keyword = str(keyword).strip().lower()
    if not keyword:
        return None
        
    # Check cache first
    safe_name = quote_plus(keyword)
    cache_path = os.path.join(CACHE_DIR, f"{safe_name}.png")
    if os.path.exists(cache_path):
        return cache_path
        
    headers = {
        "Client-ID": CLIENT_ID,
        "IconScout-Secret": API_KEY,
        "Accept": "application/json"
    }
    
    url = f"https://api.iconscout.com/v3/search?query={quote_plus(keyword)}&asset=3d&price=free"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
            
        data = res.json()
        items = data.get("response", {}).get("items", {}).get("data", [])
        if not items:
            return None
            
        first_item = items[0]
        thumb_url = first_item.get("urls", {}).get("thumb")
        if not thumb_url:
            return None
            
        # Download the image
        img_res = requests.get(thumb_url, stream=True, timeout=10)
        if img_res.status_code == 200:
            with open(cache_path, 'wb') as f:
                for chunk in img_res.iter_content(1024):
                    f.write(chunk)
            return cache_path
    except Exception as e:
        print(f"[IconScout] Error fetching icon for '{keyword}': {e}", flush=True)
        return None
        
    return None
