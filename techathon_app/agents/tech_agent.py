import json
import os
import re
import pandas as pd
from pathlib import Path

# ================= CONFIGURATION =================
# Navigate up from 'agents' to 'final'
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"

PRODUCT_MASTER_FILE = DB_DIR / "product_master_enriched.json"
COMPETITORS_FILE = DB_DIR / "competitors.json"
TEST_MASTER_FILE = DB_DIR / "test_master.json"

class RealTechAgent:
    def __init__(self):
        self.inventory = self.load_json(PRODUCT_MASTER_FILE)
        self.competitors = self.load_json(COMPETITORS_FILE)
        self.tests = self.load_json(TEST_MASTER_FILE)
        
        # Normalize Inventory Structure
        if isinstance(self.inventory, dict):
            self.inventory = (
                self.inventory.get("products") or 
                self.inventory.get("items") or 
                list(self.inventory.values())
            )
        
        # Create quick lookup map
        self.inventory_map = {
            sku.get("product_id"): sku 
            for sku in self.inventory 
            if isinstance(sku, dict)
        }
        
        # Load Settings
        try:
            with open(BASE_DIR / "settings.json", "r") as f:
                self.config = json.load(f).get("tech_config", {})
        except:
            self.config = {}

    def load_json(self, path):
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Tech Agent: Could not load {path.name}: {e}")
        return []

    # ================= NORMALIZATION HELPERS =================
    def normalize(self, v):
        if v is None: return None
        return str(v).strip().lower()

    def normalize_material(self, v):
        # Remove qualifications like (Flexible), (Solid)
        n = self.normalize(v)
        if not n: return None
        n = re.sub(r"\(.*?\)", "", n).strip()
        
        # 1. Exact Map
        mat_map = {"aluminum": "aluminium", "al": "aluminium", "alu": "aluminium", "cu": "copper", "copper": "copper", "aluminium": "aluminium"}
        if n in mat_map: return mat_map[n]

        # 2. Fuzzy Containment
        # Check for word boundaries to avoid false positives (e.g. 'cal' should not match 'al')
        tokens = n.split()
        if "al" in tokens or "aluminum" in tokens or "aluminium" in tokens or "alu" in tokens:
            return "aluminium"
        if "cu" in tokens or "copper" in tokens:
            return "copper"
            
        return n

    def is_not_specified(self, v):
        """Return True if the value indicates an unspecified field.
        Handles None, empty strings, and case‑insensitive "NOT SPECIFIED".
        """
        if v is None:
            return True
        if isinstance(v, str):
            stripped = v.strip()
            return stripped.upper() == "NOT SPECIFIED" or stripped == ""
        return False

    def normalize_standard(self, s):
        if not s: return None
        s = self.normalize(s)
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r":\d{4}", "", s)
        return s.replace("part-", "part ").strip()

    # ================= MATCHING LOGIC (From main_code.py) =================
    # ================= SMART NORMALIZATION & MATCHING =================
    def normalize_standard(self, s):
        if not s: return None
        s = self.normalize(s)
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r":\d{4}", "", s)
        return s.replace("part-", "part ").strip()

    # ================= MATCHING LOGIC (Using Advanced Legacy Algorithms) =================
    
    def match_cross_section(self, rfp_val, inv_val):
        if self.is_not_specified(rfp_val): return 1.0 # Loose match
        try:
            r = float(rfp_val)
            i = float(inv_val)
        except: return 0.0
        
        # Percentage difference score: 1.0 - error
        score = 1.0 - abs(i - r) / r
        return max(0.0, round(score, 3))

    def match_standards(self, rfp_list, inv_list):
        """
        - Total standards weight = 1.0
        - Divided equally among all RFP standards
        - Each standard checked independently
        """
        if not rfp_list: return 1.0 # No requirement = Perfect match
        
        # Ensure lists
        if isinstance(rfp_list, str): rfp_list = [rfp_list]
        if isinstance(inv_list, str): inv_list = [inv_list]
        
        rfp_norm = [self.normalize_standard(s) for s in rfp_list]
        inv_norm = set(self.normalize_standard(s) for s in (inv_list or []))
        
        total = len(rfp_norm)
        if total == 0: return 1.0
        
        score = 0.0
        per_std_weight = 1.0 / total
        
        for std in rfp_norm:
            if std == "isi marked": score += per_std_weight
            elif std in inv_norm: score += per_std_weight
            
        return round(score, 3)

    def normalize_voltage(self, v):
        """Converts 1.1kV -> 1100, 1100V -> 1100"""
        if not v: return 0
        s = str(v).upper().replace("VOLTS", "").replace("V", "").strip()
        try:
            val = float(re.findall(r"[\d\.]+", s)[0])
            if "K" in str(v).upper() or val < 50: # Assume < 50 means kV (e.g. 11kV)
                return val * 1000
            return val
        except:
            return 0

    def calculate_weighted_score(self, rfp, inv):
        """
        Calculates a 'Smart Score' using 7-Factor Legacy Logic.
        """
        score = 0.0
        max_score = 0.0
        
        # Weights Configuration (Total 100)
        weights = {
            "voltage_grade": 20,       
            "core_count": 15,          
            "cross_section_sqmm": 15,  
            "conductor_material": 15,  
            "insulation": 10,
            "sheath": 5,
            "armour_type": 5,
            "standards": 15 # Added Standards
        }
        
        # 1. Voltage (Strict)
        rfp_v = self.normalize_voltage(rfp.get("voltage_grade"))
        inv_v = self.normalize_voltage(inv.get("voltage_grade"))
        if rfp_v == inv_v: score += weights["voltage_grade"]
        elif rfp_v and inv_v and abs(rfp_v - inv_v) / rfp_v < 0.1: score += weights["voltage_grade"] * 0.5 
        max_score += weights["voltage_grade"]
        
        # 2. Core Count (Exact)
        try:
            if float(rfp.get("core_count", 0)) == float(inv.get("core_count", 0)):
                score += weights["core_count"]
        except: pass
        max_score += weights["core_count"]

        # 3. Size (Fuzzy Percentage Score)
        sz_score = self.match_cross_section(rfp.get("cross_section_sqmm"), inv.get("cross_section_sqmm"))
        score += weights["cross_section_sqmm"] * sz_score
        max_score += weights["cross_section_sqmm"]

        # 4. Material (Synonyms)
        r_mat = self.normalize_material(rfp.get("conductor_material"))
        i_mat = self.normalize_material(inv.get("conductor_material"))
        if r_mat == i_mat: score += weights["conductor_material"]
        max_score += weights["conductor_material"]

        # 5. Standards (New)
        std_score = self.match_standards(rfp.get("standards"), inv.get("standards"))
        score += weights["standards"] * std_score
        max_score += weights["standards"]

        # 6. Rest (Normal string match)
        for field in ["insulation", "sheath", "armour_type"]:
            r_val = self.normalize(rfp.get(field))
            i_val = self.normalize(inv.get(field))
            if r_val and i_val and (r_val in i_val or i_val in r_val): 
                score += weights[field]
            max_score += weights[field]

        return round((score / max_score) * 100, 1)

    def compute_match_score(self, rfp_attrs, inv_specs):
        return self.calculate_weighted_score(rfp_attrs, inv_specs)

    # ================= MAIN PIPELINE STEPS =================
    def find_best_matches(self, line_items):
        results = []
        for item in line_items:
            best_match = None
            highest_score = -1
            
            # Compare against every product in inventory
            for sku in self.inventory:
                score = self.compute_match_score(item.get("technical_attributes", {}), sku.get("technical_specs", {}))
                if score > highest_score:
                    highest_score = score
                    best_match = sku
            
            # Detailed Breakdown for the best match
            breakdown = self.generate_breakdown(item.get("technical_attributes", {}), best_match)
            
            results.append({
                "lot_id": item.get("lot_id"),
                "rfp_description": item.get("raw_description"),
                "matched_sku_id": best_match.get("product_id") if best_match else "NO_MATCH",
                "matched_sku_name": best_match.get("product_name") if best_match else "No Suitable Product Found",
                "match_score": highest_score,
                "quantity": item.get("quantity"),  # Preserve Quantity for Pricing
                "technical_breakdown": breakdown,
                "commercial_ref": best_match.get("commercial", {}) if best_match else {}
            })
        return results

    def generate_breakdown(self, rfp_specs, sku):
        """Creates the detailed comparison list for the HTML report"""
        if not sku: return []
        sku_specs = sku.get("technical_specs", {})
        
        # Compare key fields
        fields = ["voltage_grade", "core_count", "cross_section_sqmm", "conductor_material", "insulation"]
        breakdown = []
        
        for f in fields:
            r_val = rfp_specs.get(f, "N/A")
            s_val = sku_specs.get(f, "N/A")
            
            # FIX: Use specialized material comparisons
            if f == "conductor_material":
                 is_match = self.normalize_material(str(r_val)) == self.normalize_material(str(s_val))
            elif f == "voltage_grade":
                 is_match = self.normalize_voltage(r_val) == self.normalize_voltage(s_val)
            else:
                 is_match = self.normalize(str(r_val)) == self.normalize(str(s_val))
            
            breakdown.append({
                "spec": f.replace("_", " ").title(),
                "requested": r_val,
                "actual": s_val,
                "status": "Match" if is_match else "Mismatch"
            })
        return breakdown

    def analyze_competitors(self, matched_items):
        """Checks which competitors also make these products"""
        if not isinstance(self.competitors, list): return []
        
        comp_report = []
        for item in matched_items:
            sku_id = item["matched_sku_id"]
            for comp in self.competitors:
                if sku_id in comp.get("colliding_internal_skus", []):
                    comp_report.append({
                        "lot_id": item["lot_id"],
                        "competitor": comp.get("name"),
                        "risk": "High",
                        "comment": f"Direct competitor for {sku_id}"
                    })
        return comp_report

    def calculate_testing_costs(self, matched_items):
        """Identifies required tests and estimates costs"""
        total_cost = 0.0
        details = []
        all_test_codes = set()
        
        # Ensure tests is a list
        test_list = self.tests if isinstance(self.tests, list) else []

        for item in matched_items:
            sku_name = item.get("matched_sku_name", "").upper()
            desc = item.get("rfp_description", "").upper()
            qty = float(item.get("quantity") or 0)
            drums = max(1, qty / 500) # Estimate drums

            # Determine Category
            is_ht = "11KV" in sku_name or "33KV" in sku_name or "HT" in sku_name
            is_lt = not is_ht
            is_armoured = "ARMOURED" in sku_name or "ARMORED" in sku_name
            is_frls = "FRLS" in sku_name
            
            item_cost = 0
            
            for test in test_list:
                applies = False
                criteria = test.get("mandatory_for", [])
                
                if "All Cables" in criteria: applies = True
                if is_ht and "HT Cables" in str(criteria): applies = True
                if is_lt and "LT Cables" in str(criteria): applies = True
                if is_armoured and "Armoured Cables" in str(criteria): applies = True
                if is_frls and ("FRLS" in str(criteria) or "LSZH" in str(criteria)): applies = True
                
                if applies:
                    all_test_codes.add(test.get("test_id"))
                    
                    # Estimate cost (Pricing Agent handles this precisely, but we give an estimate)
                    c = test.get("base_test_cost", 0)
                    if "Routine" in test.get("test_category", ""):
                        c *= drums 
                    item_cost += c

            details.append({"lot_id": item["lot_id"], "test_cost": item_cost})
            total_cost += item_cost
            
        return total_cost, details, list(all_test_codes)

    def generate_html_report(self, matches):
        """Generates a simple HTML table of compliance"""
        html = "<h3>Technical Compliance Matrix</h3><table border='1' style='border-collapse: collapse; width: 100%;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>Lot ID</th><th>Requested</th><th>Matched Product</th><th>Score</th><th>Status</th></tr>"
        
        for m in matches:
            color = "green" if m["match_score"] >= 80 else "orange" if m["match_score"] >= 50 else "red"
            html += f"<tr><td>{m['lot_id']}</td><td>{m['rfp_description']}</td><td>{m['matched_sku_name']}</td>"
            html += f"<td style='color:{color}; font-weight:bold;'>{m['match_score']}%</td>"
            html += f"<td>{'Compliant' if m['match_score'] == 100 else 'Deviation'}</td></tr>"
        
        html += "</table>"
        return html

    # ================= PUBLIC API =================
    def process_rfp_data(self, sales_output):
        """
        Main function called by MainAgent.
        Takes sales_agent_output, returns tech_agent_output.
        """
        line_items = sales_output.get("line_items_extracted", [])
        
        # 1. Match Products
        matches = self.find_best_matches(line_items)
        
        # 2. Competitor Check
        competitors = self.analyze_competitors(matches)
        
        # Extract unique codes for Pricing Agent
        comp_codes = list(set([c.get('competitor') for c in competitors if c.get('competitor')]))

        # 3. Testing Costs
        cost, cost_details, test_codes = self.calculate_testing_costs(matches)
        
        # 4. HTML Report
        html_report = self.generate_html_report(matches)
        
        return {
            "status": "Completed",
            "matched_line_items": matches,
            "competitor_analysis": competitors,
            "competitor_codes": comp_codes,
            "required_test_codes": test_codes,
            "testing_cost_estimate": cost,
            "compliance_report_html": html_report
        }