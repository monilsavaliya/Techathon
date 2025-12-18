import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database", "central_rfp_database.json")

class MockAgentBase:
    def load_db(self):
        if not os.path.exists(DB_FILE): return []
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return []
    
    def save_db(self, data):
        with open(DB_FILE, 'w') as f: json.dump(data, f, indent=2)
    
    def get_index(self, data, rfp_id):
        for i, x in enumerate(data):
            if x['rfp_unique_id'] == rfp_id: return i
        return -1

# 1. SALES AGENT (Extraction)
class MockSalesAgent(MockAgentBase):
    def process(self, rfp_id):
        data = self.load_db()
        i = self.get_index(data, rfp_id)
        if i == -1: return
        
        clients = ["Adani Green Energy", "Tata Power", "Reliance Jio Infra", "L&T Construction", "NTPC Limited"]
        projects = ["Solar Park Cabling Phase 4", "Metro Line 3 Electrification", "5G Fiber Rollout", "Highway Lighting Upgrade"]
        
        data[i]['sales_agent_output']['summary'] = {
            "client_name": random.choice(clients),
            "project_title": random.choice(projects),
            "submission_deadline": "2025-12-20",
            "contract_currency": "INR",
            "emd_amount": 500000
        }
        # Add dummy logistics
        data[i]['sales_agent_output']['logistics_constraints'] = {
            "delivery_location": "Gujarat, Solar Park",
            "delivery_timeline_days": 45
        }
        data[i]['processing_stage_tracker']['sales_agent'] = "Completed"
        self.save_db(data)

# 2. TECH AGENT (Matching)
class MockTechAgent(MockAgentBase):
    def process(self, rfp_id):
        data = self.load_db()
        i = self.get_index(data, rfp_id)
        if i == -1: return
        
        comps = ["Polycab", "KEI Industries", "Havells", "Finolex"]
        detected = random.sample(comps, k=random.randint(1, 3))
        
        data[i]['tech_agent_output']['status'] = "Success"
        data[i]['tech_agent_output']['competitor_codes'] = detected
        data[i]['tech_agent_output']['line_item_matches'] = [
            {"lot_id_ref": "L1", "product_name": "33kV 3C 400sqmm Al Cable (HT)", "match_confidence": 0.98, "required_tests": ["Type Test"]},
            {"lot_id_ref": "L2", "product_name": "1.1kV 4C 16sqmm Cu Cable (LT)", "match_confidence": 0.95, "required_tests": ["Routine Test"]}
        ]
        data[i]['processing_stage_tracker']['tech_agent'] = "Completed"
        self.save_db(data)

# 3. PRICING AGENT (Calculation)
class MockPricingAgent(MockAgentBase):
    def process(self, rfp_id):
        data = self.load_db()
        i = self.get_index(data, rfp_id)
        if i == -1: return
        
        base_cost = random.randint(35, 85) * 100000 
        logistics = int(base_cost * 0.05)
        packaging = 25000
        testing = 15000
        margin_pct = random.uniform(8.0, 22.0)
        
        total_cost = base_cost + logistics + packaging + testing
        final_bid = total_cost * (1 + (margin_pct/100))
        
        data[i]['pricing_agent_output']['status'] = "Success"
        data[i]['pricing_agent_output']['financial_summary'] = {
            "total_material_cost": base_cost,
            "total_logistics_cost": logistics,
            "total_packaging_cost": packaging,
            "margin_percentage": f"{margin_pct:.1f}%",
            "final_bid_value": int(final_bid)
        }
        
        # Populate Deep Audit Data for the "Sexy" UI
        data[i]['pricing_agent_output']['audit_details'] = {
            "manufacturing": {
                "total": base_cost,
                "formula": "Dynamic Pricing Engine v2.1",
                "breakdown": ["Raw Material Cost: Aluminum/Copper", "Manufacturing Overheads (12%)"]
            },
            "packaging": { "total": packaging, "breakdown": ["Steel Drums", "Wooden Lagging"] },
            "testing": { "total": testing, "breakdown": ["HV Test", "Resistance Test"] },
            "logistics": { "total": logistics, "formula": "Zone-based Calculation" },
            "strategy": { "competitor_impact": "-2%", "zone_risk": "Standard" }
        }
        
        data[i]['pricing_agent_output']['breakdowns']['strategy_rationale'] = [
            "Competitor detected, margin adjusted.",
            "High volume discount applicable."
        ]
        
        data[i]['audit_report_url'] = data[i]['document_url'] # Mock link
        data[i]['processing_stage_tracker']['pricing_agent'] = "Completed"
        
        self.save_db(data)

# 4. SALES AGENT 2 (Priority & Ranking)
class MockSalesAgent2(MockAgentBase):
    def process(self, rfp_id):
        data = self.load_db()
        i = self.get_index(data, rfp_id)
        if i != -1:
            data[i]['status'] = "Ready"
            data[i]['processing_stage_tracker']['final_review'] = "Ready"
            self.save_db(data)
        
        # Trigger global re-ranking
        self.process_all_priorities()

    def process_all_priorities(self):
        print("   [Sales Agent 2] 🔄 Recalculating Portfolio Priorities...")
        data = self.load_db()
        
        # 1. Filter Safe
        active_indices = []
        for i, rfp in enumerate(data):
            if rfp.get('is_archived', False): continue
            
            # Crash-Proof Check
            # Using 'or {}' ensures we don't crash on None
            pricing = rfp.get('pricing_agent_output') or {}
            fin = pricing.get('financial_summary') or {}
            
            if not fin: continue 
            active_indices.append(i)

        if not active_indices: return

        # 2. Score
        scored_rfps = []
        for i in active_indices:
            try:
                m_str = str(data[i]['pricing_agent_output']['financial_summary'].get('margin_percentage', '0%'))
                margin = float(m_str.replace('%', ''))
            except: margin = 0.0
            
            win_prob = min(99, max(10, 95 - (margin * 2.5)))
            
            # Formula
            raw_score = (margin * 4.5) + (win_prob * 0.2)
            score = min(99, int(raw_score))
            
            scored_rfps.append((i, score, int(win_prob)))

        # 3. Sort
        scored_rfps.sort(key=lambda x: x[1], reverse=True)

        for rank, (idx, score, win_prob) in enumerate(scored_rfps):
            if score >= 75: priority = "High"
            elif score >= 50: priority = "Medium"
            else: priority = "Low"
            
            data[idx]['sales_agent_2_output'] = {
                "priority_rank": priority,
                "priority_score": score,
                "win_probability": f"{win_prob}%",
                "recommendation": "Bid"
            }
        
        self.save_db(data)
        print("   [Sales Agent 2] 🔄 Recalculating Portfolio Priorities...")
        data = self.load_db()
        
        active_indices = []
        for i, rfp in enumerate(data):
            if rfp.get('is_archived', False): continue
            
            pricing = rfp.get('pricing_agent_output')
            if not pricing or not isinstance(pricing, dict): continue
            fin = pricing.get('financial_summary')
            if not fin or not isinstance(fin, dict): continue
            
            active_indices.append(i)

        if not active_indices: return

        scored_rfps = []
        for i in active_indices:
            try:
                m_str = str(data[i]['pricing_agent_output']['financial_summary'].get('margin_percentage', '0%'))
                margin = float(m_str.replace('%', ''))
            except: margin = 0.0
            
            win_prob = min(99, max(10, 95 - (margin * 2.5)))
            margin_score = min(100, margin * 5)
            final_score = int((margin_score * 0.6) + (win_prob * 0.4))
            
            scored_rfps.append((i, final_score, int(win_prob)))

        scored_rfps.sort(key=lambda x: x[1], reverse=True)

        for rank, (idx, score, win_prob) in enumerate(scored_rfps):
            if score >= 75: priority = "High"
            elif score >= 50: priority = "Medium"
            else: priority = "Low"
            
            data[idx]['sales_agent_2_output'] = {
                "priority_rank": priority,
                "priority_score": score,
                "win_probability": f"{win_prob}%",
                "recommendation": "Submit Bid" if score > 40 else "No Bid"
            }
        
        self.save_db(data)