import json
import os
import datetime
import shutil
from mock_agents import MockSalesAgent, MockTechAgent, MockPricingAgent, MockSalesAgent2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database", "central_rfp_database.json")
STATIC_DOCS_DIR = os.path.join(BASE_DIR, "static", "rfp_docs")
os.makedirs(STATIC_DOCS_DIR, exist_ok=True)
LOCAL_HOST_URL = "http://127.0.0.1:5000"

def get_rfp_template(rfp_id, filename, link):
    return {
        "rfp_unique_id": rfp_id,
        "status": "New",
        "is_archived": False,
        "created_at": datetime.datetime.now().isoformat(),
        "document_url": link,
        "audit_report_url": None,
        "local_file_name": filename,
        "processing_stage_tracker": {"sales_agent": "Pending", "tech_agent": "Pending", "pricing_agent": "Pending", "final_review": "Pending"},
        "sales_agent_output": { "summary": {"client_name": "Processing...", "project_title": "..."} },
        "tech_agent_output": { "status": "Pending", "competitor_codes": [], "line_item_matches": [] },
        "pricing_agent_output": { "status": "Pending", "financial_summary": {}, "breakdowns": {} },
        "sales_agent_2_output": { "priority_rank": "Pending" }
    }

class MainAgent:
    def __init__(self):
        self.load_db()
        self.sales = MockSalesAgent()
        self.tech = MockTechAgent()
        self.price = MockPricingAgent()
        self.sales2 = MockSalesAgent2()

    def load_db(self):
        if not os.path.exists(DB_FILE): self.db = []
        else:
            with open(DB_FILE, 'r') as f:
                try: self.db = json.load(f)
                except: self.db = []

    def save_db(self):
        with open(DB_FILE, 'w') as f: json.dump(self.db, f, indent=2)

    def create_rfp_card(self, temp_path):
        if not os.path.exists(temp_path): return None
        rfp_id = f"RFP-2025-{len(self.db)+101:03d}"
        filename = f"{rfp_id}.pdf"
        dest = os.path.join(STATIC_DOCS_DIR, filename)
        
        try: shutil.copy(temp_path, dest)
        except: return None
        
        link = f"/static/rfp_docs/{filename}"
        self.db.append(get_rfp_template(rfp_id, filename, link))
        self.save_db()
        return rfp_id

    def run_full_pipeline(self, rfp_id):
        print(f">>> [Main] Orchestrating Agents for {rfp_id}...")
        self.sales.process(rfp_id)
        self.tech.process(rfp_id)
        self.price.process(rfp_id)
        self.sales2.process(rfp_id) # This triggers re-ranking
        print(f">>> [Main] Pipeline Finished.")

    def toggle_archive(self, rfp_id):
        print(f"   [Main] Toggling Archive for {rfp_id}...")
        
        # 1. LOAD FRESH
        self.load_db()
        
        target_rfp = None
        for item in self.db:
            if item['rfp_unique_id'] == rfp_id:
                # Toggle Status
                current = item.get('is_archived', False)
                item['is_archived'] = not current
                target_rfp = item
                break
        
        if not target_rfp: return

        # 2. RE-CALCULATE PRIORITIES IN MEMORY (Don't call the external agent script yet)
        # We duplicate the simple ranking logic here to save in ONE go.
        active_items = [x for x in self.db if not x.get('is_archived', False) and x.get('pricing_agent_output')]
        
        # Sort by margin
        active_items.sort(key=lambda x: float(str(x['pricing_agent_output']['financial_summary'].get('margin_percentage', '0').strip('%'))) if x['pricing_agent_output'].get('financial_summary') else 0, reverse=True)
        
        # Re-assign Ranks
        total = len(active_items)
        for rank, rfp in enumerate(active_items):
            if rank < total * 0.33: p = "High"
            elif rank < total * 0.66: p = "Medium"
            else: p = "Low"
            
            # Update the record in memory
            if 'sales_agent_2_output' not in rfp: rfp['sales_agent_2_output'] = {}
            rfp['sales_agent_2_output']['priority_rank'] = p

        # 3. SAVE ONCE (Atomic)
        self.save_db()
        print(f"   [Main] Success. {rfp_id} moved to {'Archive' if target_rfp['is_archived'] else 'Active'}.")