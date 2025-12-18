import requests
import os

class RealSalesAgent:
    def __init__(self):
        # Point to the local API we just created
        self.api_url = "http://127.0.0.1:8000/process-rfp"

    def process_rfp(self, filepath, filename="doc.pdf"):
        print(f"📡 Sending {filename} to Sales API at {self.api_url}...")
        
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'application/pdf')}
                # Send request to local server
                response = requests.post(self.api_url, files=files)
            
            if response.status_code == 200:
                print("✅ API Success!")
                return response.json()
            else:
                return {"error": f"API Error {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"error": f"Connection failed. Make sure you are running 'python sales_api.py' in a separate terminal! Error: {e}"}