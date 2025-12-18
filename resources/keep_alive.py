import time
import requests
from datetime import datetime

# --- CONFIGURATION ---
URL_TO_PING = "https://techathon-app-1.onrender.com/"
PING_INTERVAL_SECONDS = 840  # 14 Minutes (Render sleeps after 15 mins)

def keep_alive():
    print(f"🚀 Keep-Alive Script Started for: {URL_TO_PING}")
    print(f"⏱️  Pinging every {PING_INTERVAL_SECONDS} seconds...")
    print("-" * 50)

    count = 1
    while True:
        try:
            # Send a simple GET request
            response = requests.get(URL_TO_PING)
            
            # Timestamp for log
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if response.status_code == 200:
                print(f"[{now}] ✅ Ping #{count} Successful! (Status: {response.status_code})")
            else:
                print(f"[{now}] ⚠️ Ping #{count} Returned Status: {response.status_code}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error pinging server: {e}")

        count += 1
        
        # Wait for the next interval
        time.sleep(PING_INTERVAL_SECONDS)

if __name__ == "__main__":
    keep_alive()
