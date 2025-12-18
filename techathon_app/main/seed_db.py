import json
import random
import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Go up one level from 'main' to 'final'
DB_FILE = os.path.join(BASE_DIR, "database", "central_rfp_database.json")

def create_rich_rfp(i):
    clients = ["Adani Green Energy", "Tata Power Solar", "L&T Construction", "NTPC Renewables", "Reliance Jio Infra", "Sterling & Wilson"]
    locs = ["Khavda Solar Park, Gujarat", "Mumbai Metro Line 3", "Bangalore Data Center", "Delhi-Mumbai Expressway", "Pune Industrial Zone", "Hyderabad Pharma City"]
    
    # 1. Cost Math
    mat_cost = random.randint(35, 120) * 100000
    mfg_overhead = int(mat_cost * 0.12)
    packaging = 5 * 12000 + 7500
    testing = 15000 + 12500
    logistics = int(mat_cost * 0.05)
    
    total_cost = mat_cost + mfg_overhead + packaging + testing + logistics
    margin_pct = random.uniform(12.0, 25.0) # Ensure good margins for demo
    bid_val = int(total_cost * (1 + margin_pct/100))
    
    # 2. Priority Logic
    # Score = Margin (60%) + WinProb (40%)
    win_prob_val = random.randint(60, 95)
    margin_score = min(100, margin_pct * 4) 
    priority_score = int((margin_score * 0.6) + (win_prob_val * 0.4))
    
    prio_rank = "High" if priority_score > 75 else ("Medium" if priority_score > 50 else "Low")

    return {
        "rfp_unique_id": f"RFP-2025-10{i}",
        "status": f"Ready ({prio_rank})",
        "is_archived": False,
        "created_at": datetime.datetime.now().isoformat(),
        "document_url": "/static/rfp_docs/sample.pdf",
        "local_file_name": f"tender_doc_{i}.pdf",
        "processing_stage_tracker": {
            "sales_agent": "Completed",
            "tech_agent": "Completed",
            "pricing_agent": "Completed",
            "final_review": "Pending"
        },
        "sales_agent_output": {
            "summary": {
                "client_name": clients[i-1],
                "project_title": f"Phase {i} Electrical Infrastructure Upgrade - 33kV Network",
                "submission_deadline": f"2025-12-{15+i}",
                "contract_currency": "INR",
                "emd_amount": 500000
            },
            "logistics_constraints": {
                "delivery_location": locs[i-1],
                "delivery_timeline_days": 45
            },
            "line_items_extracted": [
                {"lot_id": "L1", "description": "33kV 3C 400sqmm Al Cable (Armoured)", "qty": 5000, "unit": "M"},
                {"lot_id": "L2", "description": "1.1kV 4C 16sqmm Cu Cable (FRLS)", "qty": 2000, "unit": "M"}
            ]
        },
        
        "tech_agent_output": {
            "status": "Success",
            "competitor_codes": random.sample(["Polycab India", "KEI Industries", "Havells"], k=2),
            "line_item_matches": [
                {"lot_id_ref": "L1", "product_name": "HT Power Cable 33kV (Armoured)", "match_confidence": 0.98},
                {"lot_id_ref": "L2", "product_name": "LT Control Cable FRLS", "match_confidence": 0.95}
            ]
        },
        
        "pricing_agent_output": {
            "status": "Success",
            "financial_summary": {
                "total_material_cost": mat_cost,
                "total_logistics_cost": logistics,
                "total_packaging_cost": packaging,
                "margin_percentage": f"{margin_pct:.1f}%",
                "final_bid_value": bid_val
            },
            "audit_details": {
                "manufacturing": {"total": mat_cost + mfg_overhead, "formula": "Standard BOM + 12% Ovhd", "breakdown": ["Copper Conductor", "XLPE Insulation", "Steel Armour"]},
                "packaging": {"total": packaging, "breakdown": ["Steel Drums x 5", "Lagging"]},
                "testing": {"total": testing, "breakdown": ["HV Test", "Resistance Test"]},
                "logistics": {"total": logistics, "formula": "Zone Z1 Rate"},
                "strategy": {"competitor_impact": "-2.0%", "zone_risk": "+1.5%"}
            },
            "breakdowns": {
                "strategy_rationale": ["Aggressive pricing against Tier-1", "Volume discount applied"]
            }
        },
        
        "sales_agent_2_output": {
            "priority_rank": prio_rank,
            "priority_score": priority_score,
            "win_probability": f"{win_prob_val}%",
            "recommendation": "Bid Immediately"
        }
    }

# Generate 6 records
data = [create_rich_rfp(i) for i in range(1, 7)]

# Ensure folder exists
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

with open(DB_FILE, 'w') as f:
    json.dump(data, f, indent=2)

print("✅ Database RESET with 6 Perfect Records (Scores Included).")