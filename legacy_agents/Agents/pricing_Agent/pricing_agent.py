import json
import os
import math
import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ==============================================================================
# 1. CFO-LEVEL CONFIGURATION (The "Brain" Settings)
# ==============================================================================
CONFIG = {
    "FINANCIAL": {
        "ANNUAL_COST_OF_CAPITAL": 0.12,    # 12% Interest Rate for Credit Days calc
        "TARGET_NET_MARGIN": 0.22,         # We want 22% profit ideally
        "MIN_SURVIVAL_MARGIN": 0.04,       # Walk away if profit < 4%
        "HEDGING_BUFFER_PCT": 0.02         # 2% buffer for volatile raw materials
    },
    "OPERATIONAL": {
        "FACTORY_OVERHEAD_RATE": 0.12,     # 12% Standard Mfg Overhead
        "OVERLOAD_PREMIUM": 0.05,          # Charge 5% more if factory > 90% utilization
        "IDLE_DISCOUNT": 0.03              # Discount 3% if factory < 30% utilization
    },
    "PACKAGING": {
        "STEEL_DRUM_COST": 12000,
        "WOODEN_DRUM_COST": 4500,
        "SPECIAL_CRATE_COST": 2500
    },
    "TESTING": {
        "HV_BASE_COST": 15000,
        "LV_BASE_COST": 5000
    }
}

# ==============================================================================
# 2. INTELLIGENT DATA LOADER
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Smart path detection: Checks local first, then database/ subfolder
DB_PATHS = [BASE_DIR, os.path.join(BASE_DIR, "database")]

FILES = {
    "INPUT": "input.json",
    "OUTPUT": "output_priced.json",
    "PRODUCTS": "product_master.json",
    "MATERIALS": "material_master.json",
    "COMPETITORS": "competitors.json",
    "LOGISTICS": "logistic_master.json",
    "CLIENTS": "client_master.json",
    "FACTORY": "factory_production_schedule.json",
    "TESTS": "test_master.json"
}

class Database:
    def __init__(self):
        self.data = {}
        print(">>> [INIT] Connecting to Enterprise Data Warehouse...")
        for key, fname in FILES.items():
            loaded = False
            for path in DB_PATHS:
                full_path = os.path.join(path, fname)
                if os.path.exists(full_path):
                    try:
                        if os.path.getsize(full_path) == 0:
                            print(f"   [!] WARNING: {fname} is empty. Skipping.")
                            loaded = False
                            continue
                            
                        with open(full_path, 'r') as f:
                            self.data[key] = json.load(f)
                        print(f"   [+] Loaded {key} ({len(self.data[key])} records)")
                        loaded = True
                        break
                    except json.JSONDecodeError:
                        print(f"   [!] ERROR: Could not decode {fname}. File might be corrupted.")
                        loaded = False
                    except Exception as e:
                         print(f"   [!] ERROR: Failed to load {fname}: {e}")
                         loaded = False
            if not loaded:
                print(f"   [!] WARNING: Could not find {fname}. Using Empty List.")
                self.data[key] = []

# ==============================================================================
# 3. THE PRICING ENGINE (Logic Core)
# ==============================================================================
class PricingEngine:
    def __init__(self, db):
        self.db = db

    def calculate_micro_bom_cost(self, product_id, total_qty_mtr):
        """Explodes BOM to calculate exact material cost + risk buffer."""
        prod = next((p for p in self.db["PRODUCTS"] if p['product_id'] == product_id), None)
        
        # Fallback if product not in master
        if not prod:
            return total_qty_mtr * 1500, total_qty_mtr * 2.5, ["Product Master Missing - Using Estimate"], 0, 0

        mat_cost_total = 0
        risk_buffer_total = 0
        breakdown = []

        if 'bill_of_materials' in prod:
            for item in prod['bill_of_materials']:
                mat_id = item['material_id']
                qty_per_meter = item['quantity']
                
                # Lookup Material
                mat = next((m for m in self.db["MATERIALS"] if m['material_id'] == mat_id), None)
                if mat:
                    base_rate = mat.get('base_cost_per_unit', 0)
                    mkt_factor = mat.get('current_market_factor', 1.0)
                    final_rate = base_rate * mkt_factor
                    
                    line_cost = qty_per_meter * final_rate * total_qty_mtr
                    mat_cost_total += line_cost
                    
                    # Volatility Check
                    if mat.get('volatility_risk_level') == 'High':
                        risk_val = line_cost * CONFIG["FINANCIAL"]["HEDGING_BUFFER_PCT"]
                        risk_buffer_total += risk_val
                        breakdown.append(f"   - {mat['material_name']}: {qty_per_meter} units/m (High Volatility Risk +{int(risk_val)})")
                    else:
                        breakdown.append(f"   - {mat['material_name']}: {qty_per_meter} units/m @ {final_rate:.2f}")
                else:
                    breakdown.append(f"   - {mat_id}: Price Not Found")

        # Factory Overhead
        mfg_overhead = mat_cost_total * CONFIG["OPERATIONAL"]["FACTORY_OVERHEAD_RATE"]
        
        # Weight Calculation (Critical for Logistics)
        weight_per_km = prod.get('performance_data', {}).get('approx_weight_kg_km', 1000)
        total_weight_kg = (weight_per_km / 1000) * total_qty_mtr

        total_mfg_cost = mat_cost_total + mfg_overhead + risk_buffer_total
        
        return total_mfg_cost, total_weight_kg, breakdown, risk_buffer_total, mfg_overhead

    def analyze_factory_load(self, product_id):
        """Determines Scarcity Premium or Idle Discount based on production schedule."""
        category = "HV" if "33KV" in str(product_id).upper() else "LT"
        
        # Filter relevant lines from factory schedule
        relevant_batches = [b for b in self.db["FACTORY"] if category in b.get('production_line_id', '')]
        if not relevant_batches: 
            return 0.0, "Standard Capacity Load"

        avg_util = sum(b['utilization_percent'] for b in relevant_batches) / len(relevant_batches)
        
        if avg_util > 90:
            return CONFIG["OPERATIONAL"]["OVERLOAD_PREMIUM"], f"Factory Overload ({avg_util:.1f}%) - Scarcity Premium Added"
        elif avg_util < 30:
            return -CONFIG["OPERATIONAL"]["IDLE_DISCOUNT"], f"Factory Idle ({avg_util:.1f}%) - Efficiency Discount Applied"
        
        return 0.0, f"Factory Load Normal ({avg_util:.1f}%)"

    def determine_logistics_zone(self, location_name):
        """Maps a location string to a specific Logistics Zone from the Master."""
        # 1. Fuzzy Logic Matching
        loc_lower = location_name.lower()
        
        best_zone = None
        
        # Keywords mapping to Zone Types in logistic_master.json
        keywords = {
            "hilly": "Hilly", "mountain": "Hilly", "remote": "Hilly",
            "coastal": "Coastal", "port": "Coastal", "sea": "Coastal",
            "desert": "Desert", "rajasthan": "Desert", "kutch": "Desert",
            "island": "Island", "andaman": "Island",
            "urban": "Urban", "city": "Urban", "metro": "Urban"
        }
        
        detected_type = "Plains_Highway" # Default
        
        for k, v in keywords.items():
            if k in loc_lower:
                detected_type = v
                break
        
        # 2. Find Zone in Master
        for zone in self.db["LOGISTICS"]:
            if detected_type.lower() in zone['zone_type'].lower():
                best_zone = zone
                break
        
        # Fallback to Z-01 if not found
        if not best_zone:
            best_zone = next((z for z in self.db["LOGISTICS"] if z['zone_code'] == "Z-01"), None)
            
        return best_zone

    def calculate_logistics(self, weight_kg, distance_km, location_name):
        """Calculates freight using Zone-Specific rates and surcharges."""
        zone = self.determine_logistics_zone(location_name)
        
        rate = zone['transport_rate_per_ton_km']
        surcharge = zone['surcharge_multiplier']
        risk_pct = zone['risk_factor_percent']
        
        tons = weight_kg / 1000
        base_freight = tons * distance_km * rate
        total_freight = base_freight * surcharge
        
        formula = f"({tons:.2f}T x {distance_km}km x {rate} Rate x {surcharge} Zone ({zone['zone_code']}))"
        return total_freight, formula, risk_pct, zone['zone_type']

    def analyze_financials(self, client_name, total_value):
        """Calculates Cost of Capital based on Credit Days and Loyalty Status."""
        client = next((c for c in self.db["CLIENTS"] if c['client_name'].lower() in client_name.lower()), None)
        
        credit_days = 30
        loyalty_disc = 0.0
        
        if client:
            terms = client.get('payment_terms', '30 Days')
            if "90" in terms: credit_days = 90
            elif "60" in terms: credit_days = 60
            elif "Advance" in terms: credit_days = 0
            
            if client.get('loyalty_status') == 'Gold': loyalty_disc = -0.03
            if client.get('loyalty_status') == 'Silver': loyalty_disc = -0.015

        # Interest Calculation: Principal * Rate * (Days/365)
        interest_cost = total_value * (CONFIG["FINANCIAL"]["ANNUAL_COST_OF_CAPITAL"] * credit_days / 365)
        
        return interest_cost, credit_days, loyalty_disc

    def solve_game_theory(self, competitor_names):
        """Analyzes rivals to adjust margin dynamically."""
        margin_adj = 0.0
        reasons = []
        
        for comp_input in competitor_names:
            rival = next((c for c in self.db["COMPETITORS"] if c['name'].lower() in comp_input.lower() or c['competitor_id'] == comp_input), None)
            
            if rival:
                aggression = rival['pricing_intelligence']['aggression_score']
                win_rate = rival['performance_metrics']['win_rate_against_us']
                
                if aggression >= 8:
                    margin_adj -= 0.03
                    reasons.append(f"Price War Alert: {rival['name']} (Aggressive)")
                elif win_rate > 0.6:
                    margin_adj -= 0.02
                    reasons.append(f"High Threat: {rival['name']} (High Win Rate)")
                elif "Tier-3" in rival['tier']:
                    margin_adj -= 0.04
                    reasons.append(f"Low-Cost Rival: {rival['name']}")
                
        return margin_adj, reasons

# ==============================================================================
# 4. AUDIT REPORT GENERATOR (PDF)
# ==============================================================================
class AdvancedAuditPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 51, 102) # Navy Blue
        self.cell(0, 10, 'SMARTBID: COMMERCIAL FORENSIC AUDIT', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f'Generated: {datetime.datetime.now().strftime("%d-%b-%Y %H:%M")}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)
        self.set_draw_color(0, 51, 102)
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        self.ln(5)

    def section_header(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_fill_color(230, 230, 240) # Light Blue
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        self.ln(2)

    def add_row(self, label, value, is_bold=False):
        self.set_font('Helvetica', 'B' if is_bold else '', 10)
        self.cell(140, 6, label, "B", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(50, 6, value, "B", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')

    def add_product_block(self, item):
        self.set_font('Helvetica', 'B', 10)
        self.set_fill_color(245, 245, 245)
        self.cell(0, 8, f"Item: {item['name']} (Qty: {item['qty']})", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        self.set_font('Helvetica', '', 9)
        self.cell(140, 6, f"  Material & Mfg", 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(50, 6, f"{item['cost']:,.0f}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        self.cell(140, 6, f"  Packaging", 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(50, 6, f"{item['pkg']:,.0f}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        self.cell(140, 6, f"  Compliance Testing", 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(50, 6, f"{item['test']:,.0f}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        
        # List specific tests
        self.set_font('Helvetica', 'I', 8)
        for t_line in item['test_breakdown']:
            self.cell(0, 4, f"  {t_line}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

# ==============================================================================
# 5. EXECUTION ORCHESTRATOR
# ==============================================================================
def run_brain():
    # 1. Init
    db = Database()
    brain = PricingEngine(db.data)
    
    # 2. Load Input
    rfp_path = os.path.join(BASE_DIR, FILES["INPUT"])
    if not os.path.exists(rfp_path): return print("No Input File.")
    
    with open(rfp_path, 'r') as f: rfps = json.load(f)
    processed_output = []

    for rfp in rfps:
        rfp_id = rfp.get('rfp_unique_id')
        client_name = rfp['sales_agent_output']['summary']['client_name']
        delivery_loc = rfp['sales_agent_output']['logistics_constraints']['delivery_location']
        print(f"\nAnalyzing {rfp_id}...")

        # --- A. DETAILED COSTING ---
        audit_lines = []
        product_breakdowns = []
        total_mfg = 0
        total_pkg = 0
        total_test = 0
        total_weight = 0
        
        # Get Items (Prioritize Tech Matches, Fallback to Sales)
        items = rfp.get('tech_agent_output', {}).get('line_item_matches', [])
        if not items: items = rfp['sales_agent_output']['line_items_extracted']

        for item in items:
            pid = item.get('matched_product_id') or item.get('lot_id')
            qty = float(item.get('confirmed_quantity') or item.get('quantity') or 1000)
            
            # 1. Material (Micro-BOM)
            mfg, wt, breakdown, risk, oh = brain.calculate_micro_bom_cost(pid, qty)
            total_mfg += mfg
            total_weight += wt
            
            # 2. Packaging
            drums = math.ceil(qty / 500)
            p_cost = drums * (CONFIG["PACKAGING"]["STEEL_DRUM_COST"] if "33KV" in str(pid) else CONFIG["PACKAGING"]["WOODEN_DRUM_COST"])
            total_pkg += p_cost

            # 3. Testing (NEW ENGINE)
            # Use calculate_compliance_cost if available, else simple fallback logic for demo
            # Since calculate_compliance_cost was not in previous file content provided in prompt, 
            # I will use the robust logic similar to main PricingEngine block but ensuring variable names align.
            # However, looking at my previous generated code in thoughts, I added calculate_compliance_cost. 
            # I will implement a robust test calc here directly based on Test Master.
            
            t_cost = 0
            t_breakdown = []
            
            # Simple Category Check
            is_hv = "33KV" in str(pid).upper() or "11KV" in str(pid).upper()
            
            # Find relevant tests in DB
            for test in db.data["TESTS"]:
                applies = False
                if "All Cables" in test['mandatory_for']: applies = True
                if is_hv and "HT Cables" in test['mandatory_for']: applies = True
                
                if applies:
                    c = test['base_test_cost']
                    if "Routine" in test['test_category']:
                        c = c * drums
                    t_cost += c
                    t_breakdown.append(f"- {test['test_name']}: {c:,.0f}")
            
            if t_cost == 0: # Fallback
                t_cost = CONFIG["TESTING"]["HV_BASE_COST"] if is_hv else CONFIG["TESTING"]["LV_BASE_COST"]
                t_breakdown.append(f"- Standard Routine Tests: {t_cost}")

            total_test += t_cost

            product_breakdowns.append({
                "name": pid, "qty": qty, "cost": mfg, "pkg": p_cost, "test": t_cost,
                "test_breakdown": t_breakdown
            })
            audit_lines.extend(breakdown[:2]) # Keep top 2 lines for summary

        # 4. Logistics (Zone Based)
        dist = rfp['sales_agent_output']['logistics_constraints'].get('distance_from_factory_km', 500)
        log_cost, log_formula, log_risk_pct, zone_name = brain.calculate_logistics(total_weight, dist, delivery_loc)

        # --- B. STRATEGIC ADJUSTMENTS ---
        strategy_notes = []
        
        # 1. Factory Load
        fact_adj_pct, fact_reason = brain.analyze_factory_load(pid) 
        if fact_adj_pct != 0: strategy_notes.append(fact_reason)
        
        # 2. Financials
        base_cost = total_mfg + total_pkg + total_test + log_cost
        fin_cost, credit_days, loy_disc = brain.analyze_financials(client_name, base_cost)
        if fin_cost > 0: strategy_notes.append(f"Credit Cost ({credit_days} days): +INR {int(fin_cost)}")
        if loy_disc != 0: strategy_notes.append(f"Loyalty Discount: {loy_disc*100}%")

        # 3. Game Theory
        rivals = rfp.get('tech_agent_output', {}).get('competitor_codes', [])
        comp_adj, comp_notes = brain.solve_game_theory(rivals)
        strategy_notes.extend(comp_notes)
        
        # 4. Logistics Risk
        if log_risk_pct > 0:
            strategy_notes.append(f"Zone Risk ({zone_name}): +{log_risk_pct*100}%")

        # --- C. FINAL PRICE CALCULATION ---
        target_margin = CONFIG["FINANCIAL"]["TARGET_NET_MARGIN"]
        
        # Apply Adjustments
        final_margin = target_margin + fact_adj_pct + loy_disc + comp_adj + log_risk_pct
        if final_margin < CONFIG["FINANCIAL"]["MIN_SURVIVAL_MARGIN"]:
            final_margin = CONFIG["FINANCIAL"]["MIN_SURVIVAL_MARGIN"]
            strategy_notes.append("EMERGENCY: Margin Floor Hit (Survival Mode)")

        full_cost_base = base_cost + fin_cost
        bid_value = full_cost_base * (1 + final_margin)

        # --- D. OUTPUT GENERATION ---
        
        # 1. JSON Update
        rfp['pricing_agent_output'] = {
            "status": "Success",
            "financial_summary": {
                "final_bid_value": int(bid_value),
                "margin_percentage": f"{final_margin*100:.1f}%",
                "total_cost_base": int(full_cost_base),
                "total_material_cost": int(total_mfg),
                "total_logistics_cost": int(log_cost),
                "total_packaging_cost": int(total_pkg),
                "total_testing_cost": int(total_test),
                "finance_cost": int(fin_cost)
            },
            "audit_details": {
                "manufacturing": {"total": total_mfg, "breakdown": audit_lines, "formula": "Micro-BOM"},
                "strategy": {"rationale": strategy_notes, "competitor_impact": f"{comp_adj*100:+.1f}%", "zone_risk": f"{log_risk_pct*100}%"}
            },
            "breakdowns": {"strategy_rationale": strategy_notes}
        }
        processed_output.append(rfp)

        # 2. PDF Generation
        pdf = AdvancedAuditPDF()
        pdf.add_page()
        
        # Project Info
        pdf.section_header("1. PROJECT & CLIENT IDENTITY")
        pdf.add_row("RFP Reference", rfp_id)
        pdf.add_row("Client Name", client_name)
        pdf.add_row("Destination", f"{delivery_loc} ({zone_name})")
        pdf.ln(5)

        # Costing Detail
        pdf.section_header("2. PRODUCT-WISE COST BREAKDOWN")
        for p_item in product_breakdowns:
            pdf.add_product_block(p_item)
        
        pdf.ln(5)
        pdf.section_header("3. LOGISTICS & FINANCIALS")
        pdf.add_row(f"Logistics ({dist}km, {total_weight/1000:.1f}T)", f"INR {log_cost:,.0f}")
        pdf.set_font('Helvetica', 'I', 8); pdf.cell(0, 5, f"Formula: {log_formula}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.add_row(f"Cost of Capital ({credit_days} Days)", f"INR {fin_cost:,.0f}")
        pdf.ln(2)
        pdf.add_row("FULL COST BASE", f"INR {full_cost_base:,.0f}", is_bold=True)
        pdf.ln(5)

        # Strategy
        pdf.section_header("4. STRATEGIC MARGIN BUILD-UP")
        pdf.add_row("Base Target Margin", f"{CONFIG['FINANCIAL']['TARGET_NET_MARGIN']*100}%")
        for note in strategy_notes:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 5, f"  > {note}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
        pdf.add_row("FINAL NET MARGIN", f"{final_margin*100:.1f}%", is_bold=True)
        
        # Final
        pdf.ln(10)
        pdf.set_fill_color(0, 0, 0)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(140, 12, " FINAL BID SUBMISSION VALUE", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
        pdf.cell(50, 12, f" INR {bid_value:,.0f} ", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R', fill=True)

        fname = os.path.join(BASE_DIR, "audit_reports", f"{rfp_id}_AUDIT.pdf")
        if not os.path.exists(os.path.dirname(fname)): os.makedirs(os.path.dirname(fname))
        pdf.output(fname)
        rfp['audit_report_url'] = f"/audit_reports/{rfp_id}_AUDIT.pdf"

    # Save
    with open(os.path.join(BASE_DIR, FILES["OUTPUT"]), 'w') as f:
        json.dump(processed_output, f, indent=2)
    print(">>> SUCCESS: Diamond-Tier Pricing Complete.")

if __name__ == "__main__":
    run_brain()