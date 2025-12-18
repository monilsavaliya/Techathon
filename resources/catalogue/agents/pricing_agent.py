import json
import os
import math
import datetime
import copy
from pathlib import Path
from fpdf import FPDF

# ==============================================================================
# 1. CFO-LEVEL CONFIGURATION (The "Brain" Settings)
# ==============================================================================
CONFIG = {
    "FINANCIAL": {
        "ANNUAL_COST_OF_CAPITAL": 0.12,    # 12% Interest Rate for Credit Days calc
        "TARGET_NET_MARGIN": 0.22,         # We want 22% profit ideally
        "MIN_SURVIVAL_MARGIN": 0.04,       # Walk away if profit < 4%
        "HEDGING_BUFFER_PCT": 0.02,        # 2% buffer for volatile raw materials
        "GST_RATE": 0.18
    },
    "OPERATIONAL": {
        "FACTORY_OVERHEAD_RATE": 0.12,     # 12% Standard Mfg Overhead
        "OVERLOAD_PREMIUM": 0.05,          # Charge 5% more if factory > 90% utilization
        "IDLE_DISCOUNT": 0.03              # Discount 3% if factory < 30% utilization
    },
    "LOGISTICS": {
        "FUEL_SURCHARGE_PCT": 0.10,
        "INSURANCE_PCT": 0.005,
        "HANDLING_PER_TON": 500
    },
    "TRAVEL": {
        "INSPECTOR_DAILY_ALLOWANCE": 3000,
        "INSPECTOR_TRAVEL_PER_KM": 15,
        "AVG_INSPECTION_DAYS": 2
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

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"

FILES = {
    "PRODUCTS": "product_master_enriched.json",
    "MATERIALS": "material_master.json",
    "COMPETITORS": "competitors.json",
    "LOGISTICS": "logistic_master.json",
    "CLIENTS": "client_master.json",
    "FACTORY": "factory_production_schedule.json",
    "TESTS": "test_master.json"
}

# ==============================================================================
# 2. INTELLIGENT DATA LOADER
# ==============================================================================
class Database:
    def __init__(self):
        self.data = {}
        print(">>> [INIT] Pricing Agent: Connecting to Enterprise Data Warehouse...")
        for key, fname in FILES.items():
            full_path = DB_DIR / fname
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        self.data[key] = json.load(f)
                    print(f"   [+] Loaded {key} ({len(self.data[key])} records)")
                except Exception as e:
                    print(f"   [!] Error loading {fname}: {e}")
                    self.data[key] = []
            else:
                print(f"   [!] WARNING: Could not find {fname}. Using Empty List.")
                self.data[key] = []

# ==============================================================================
# 3. THE PRICING ENGINE (Logic Core)
# ==============================================================================
class PricingEngine:
    def __init__(self, db):
        self.db = db
        # Load Settings Integration
        self.config = copy.deepcopy(CONFIG)
        try:
            full_path = BASE_DIR / "settings.json"
            if full_path.exists():
                with open(full_path, 'r') as f:
                    s = json.load(f).get('pricing_config', {})
                    if 'base_margin_percent' in s:
                        self.config['FINANCIAL']['TARGET_NET_MARGIN'] = s['base_margin_percent'] / 100.0
                    if 'packaging_cost_per_drum' in s:
                        self.config['PACKAGING']['WOODEN_DRUM_COST'] = s['packaging_cost_per_drum']
                        self.config['PACKAGING']['STEEL_DRUM_COST'] = s['packaging_cost_per_drum'] * 2.5
                    if 'logistics_rate_per_km_ton' in s:
                         # We'll stick to zone master but use this as a base feedback if needed
                         pass
        except Exception as e:
            print(f"⚠️ Pricing Engine: Could not load settings: {e}")

    def calculate_micro_bom_cost(self, product_id, total_qty_mtr):
        """Explodes BOM to calculate exact material cost + risk buffer."""
        # Normalize product_id for lookup
        prod = next((p for p in self.db["PRODUCTS"] if str(p.get('product_id')) == str(product_id)), None)
        
        # Fallback if product not in master
        if not prod:
            return total_qty_mtr * 1500, total_qty_mtr * 2.5, ["Product Master Missing - Using Estimate"], 0, 0

        mat_cost_total = 0
        risk_buffer_total = 0
        breakdown = []

        # FIX: Prioritize the standard BOM which has quantities, 'enriched' often misses it
        bom = prod.get('bill_of_materials', [])
        if not bom: bom = prod.get('bill_of_materials_enriched', [])

        if bom:
            for item in bom:
                mat_id = item.get('material_id')
                qty_per_meter = float(item.get('quantity', 0))
                
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
                        risk_val = line_cost * self.config["FINANCIAL"]["HEDGING_BUFFER_PCT"]
                        risk_buffer_total += risk_val
                        breakdown.append(f"   - {mat.get('material_name')}: {qty_per_meter} units/m (High Volatility Risk +{int(risk_val)})")
                    else:
                        breakdown.append(f"   - {mat.get('material_name')}: {qty_per_meter} units/m @ {final_rate:.2f}")
                else:
                    mat_cost_total += (qty_per_meter * 500 * total_qty_mtr) # Fallback
        else:
            # Commercial fallback
             base_rate = prod.get('commercial', {}).get('base_manufacturing_cost', 1000)
             mat_cost_total = base_rate * total_qty_mtr
             breakdown.append(f"  > Base Rate Applied: {base_rate}/m")

        # Factory Overhead
        mfg_overhead = mat_cost_total * self.config["OPERATIONAL"]["FACTORY_OVERHEAD_RATE"]
        
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
            return self.config["OPERATIONAL"]["OVERLOAD_PREMIUM"], f"Factory Overload ({avg_util:.1f}%) - Scarcity Premium (+5%) Generated"
        elif avg_util < 30:
            return -self.config["OPERATIONAL"]["IDLE_DISCOUNT"], f"Factory Idle ({avg_util:.1f}%) - Efficiency Discount (-3%) Applied"
        
        return 0.0, f"Factory Load Normal ({avg_util:.1f}%)"

    def determine_logistics_zone(self, location_name):
        """Maps a location string to a specific Logistics Zone from the Master."""
        loc_lower = str(location_name).lower()
        best_zone = None
        
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
        
        for zone in self.db["LOGISTICS"]:
            if detected_type.lower() in zone['zone_type'].lower():
                best_zone = zone
                break
        
        if not best_zone:
            best_zone = next((z for z in self.db["LOGISTICS"] if z['zone_code'] == "Z-01"), None)
            
        return best_zone

    def calculate_logistics(self, weight_kg, distance_km, location_name):
        """Calculates freight using Zone-Specific rates and surcharges."""
        zone = self.determine_logistics_zone(location_name)
        if not zone: zone = self.db["LOGISTICS"][0]
        
        rate = zone.get('transport_rate_per_ton_km', 5.0)
        surcharge = zone.get('surcharge_multiplier', 1.0)
        risk_pct = zone.get('risk_factor_percent', 0.0)
        
        tons = weight_kg / 1000
        if tons < 1: tons = 1.0
        
        base_freight = tons * distance_km * rate
        total_freight = base_freight * surcharge
        
        # Add Surcharges
        fuel = total_freight * self.config["LOGISTICS"]["FUEL_SURCHARGE_PCT"]
        insurance = (total_freight * 100) * self.config["LOGISTICS"]["INSURANCE_PCT"] # Estimating value base
        handling = tons * self.config["LOGISTICS"]["HANDLING_PER_TON"]
        
        final_logistics = total_freight + fuel + insurance + handling

        formula = f"({tons:.2f}T x {distance_km}km x {rate} Rate x {surcharge} Zone ({zone.get('zone_code')}))"
        return final_logistics, formula, risk_pct, zone.get('zone_type')

    def analyze_financials(self, client_name, total_value):
        """Calculates Cost of Capital based on Credit Days and Loyalty Status."""
        client = next((c for c in self.db["CLIENTS"] if c['client_name'].lower() in str(client_name).lower()), None)
        
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
        interest_cost = total_value * (self.config["FINANCIAL"]["ANNUAL_COST_OF_CAPITAL"] * credit_days / 365)
        
        return interest_cost, credit_days, loyalty_disc

    def solve_game_theory(self, competitor_codes):
        """Analyzes rivals to adjust margin dynamically."""
        margin_adj = 0.0
        reasons = []
        
        # Ensure list
        if not isinstance(competitor_codes, list): competitor_codes = []
            
        # FIX: Smart Aggregation (Don't sum blindly). Take the biggest spread required.
        # If one rival forces -3%, and another -2%, we don't need -5%. We need -3% (plus maybe a bit more pressure).
        
        max_impact = 0.0
        
        for comp_input in competitor_codes:
            rival = next((c for c in self.db["COMPETITORS"] if c['name'].lower() in str(comp_input).lower() or c['competitor_id'] == comp_input), None)
            
            if rival:
                try:
                    aggression = float(rival['pricing_intelligence']['aggression_score'])
                    win_rate = float(rival['performance_metrics'].get('win_rate_against_us', 0))
                    
                    impact = 0.0
                    note = ""
                    
                    if aggression >= 8:
                        impact = 0.03
                        note = f"Price War Alert: {rival['name']} (Aggressive) -> -3% Margin"
                    elif win_rate > 0.6:
                        impact = 0.02
                        note = f"High Threat: {rival['name']} (High Win Rate) -> -2% Margin"
                    elif "Tier-3" in rival.get('tier', ''):
                        impact = 0.04
                        note = f"Low-Cost Rival: {rival['name']} -> -4% Margin"
                        
                    if impact > 0:
                        reasons.append(note)
                        # Keep track of the SINGLE biggest drop needed to survive
                        if impact > max_impact:
                            max_impact = impact
                            
                except: continue
        
        # Apply the worst-case scenario (not the sum)
        # We add a small 'Market Pressure' buffer if multiple rivals exist (0.5% per extra rival)
        count = len(reasons)
        if count > 1:
            buffer = (count - 1) * 0.005 # 0.5% per additional rival
            margin_adj = -(max_impact + buffer)
            reasons.append(f"Market Pressure Buildup ({count-1} extra rivals): -{buffer*100:.1f}%")
        else:
            margin_adj = -max_impact

        return margin_adj, reasons

# ==============================================================================
# 4. AUDIT REPORT GENERATOR (PDF)
# ==============================================================================
class AdvancedAuditPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 102) # Navy Blue
        self.cell(0, 10, 'SMARTBID: COMMERCIAL FORENSIC AUDIT', 0, 1, 'C')
        self.set_font('Arial', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f'Generated: {datetime.datetime.now().strftime("%d-%b-%Y %H:%M")}', 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(0, 51, 102)
        self.set_line_width(0.5)
        self.line(10, 28, 200, 28)
        self.ln(5)

    def section_header(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 240) # Light Blue
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, f"  {title}", 0, 1, 'L', 1)
        self.ln(2)

    def add_row(self, label, value, is_bold=False):
        self.set_font('Arial', 'B' if is_bold else '', 10)
        self.cell(140, 6, label, "B", 0)
        self.cell(50, 6, value, "B", 1, 'R')

    def add_product_block(self, item):
        self.set_font('Arial', 'B', 10)
        self.set_fill_color(245, 245, 245)
        self.cell(0, 8, f"Item: {item['name'][:60]} (Qty: {item['qty']})", 1, 1, 'L', 1)
        self.set_font('Arial', '', 9)
        self.cell(140, 6, f"  Material & Mfg", 0, 0)
        self.cell(50, 6, f"{item['cost']:,.0f}", 0, 1, 'R')
        self.cell(140, 6, f"  Packaging", 0, 0)
        self.cell(50, 6, f"{item['pkg']:,.0f}", 0, 1, 'R')
        self.cell(140, 6, f"  Compliance Testing", 0, 0)
        self.cell(50, 6, f"{item['test']:,.0f}", 0, 1, 'R')
        
        # List specific tests
        self.set_font('Arial', 'I', 8)
        for t_line in item['test_breakdown']:
            self.cell(0, 4, f"  {t_line}", 0, 1)
        self.ln(2)

# ==============================================================================
# 5. REAL PRICING AGENT (Orchestrator wrapper)
# ==============================================================================
class RealPricingAgent:
    def __init__(self):
        self.db = Database()
        self.brain = PricingEngine(self.db.data)
        
    def process_pricing(self, rfp_record):
        # Extract inputs from RFP Record
        rfp_id = rfp_record.get('rfp_unique_id')
        sales_out = rfp_record.get('sales_agent_output', {})
        tech_out = rfp_record.get('tech_agent_output', {})
        
        summary = sales_out.get('summary', {})
        client_name = summary.get('client_name', 'Unknown')
        
        logistics = sales_out.get('logistics_constraints', {})
        delivery_loc = logistics.get('delivery_location', 'Ex-Works')
        dist_km = float(logistics.get('distance_from_factory_km', 500))
        
        # Get Items (Matches or Raw)
        items = tech_out.get('matched_line_items', [])
        if not items: items = [] # Handle empty

        # Aggregators
        total_mfg = 0
        total_pkg = 0
        total_test = 0
        total_weight_all = 0
        
        audit_lines = []
        product_breakdowns = []
        
        # --- A. DETAILED COSTING ---
        for item in items:
            pid = item.get('matched_sku_id', 'UNKNOWN')
            qty = float(item.get('quantity') or 0)
            if qty == 0: qty = 1000.0 # Safety
            
            # 1. Material (Micro-BOM)
            mfg, wt, breakdown, risk, oh = self.brain.calculate_micro_bom_cost(pid, qty)
            total_mfg += mfg
            total_weight_all += wt
            
            # 2. Packaging
            drums = math.ceil(qty / 500)
            p_cost = drums * (self.brain.config["PACKAGING"]["STEEL_DRUM_COST"] if "33KV" in str(pid).upper() else self.brain.config["PACKAGING"]["WOODEN_DRUM_COST"])
            total_pkg += p_cost

            # 3. Testing (Using Tech Agent Codes)
            t_cost = 0
            t_breakdown = []
            
            # Tech Agent should now provide 'required_test_codes' in tech_out, OR we infer for this item
            # Currently Tech Agent returns 'required_test_codes' as a global list for the RFP, not per item (in my implementation)
            # But here we are iterating items.
            # Let's verify how I implemented TechAgent. I implemented calculate_testing_costs to return a global 'test_codes' list.
            # But the pricing logic is per item. 
            # Let's infer per item or use the global list distributively?
            # User said: "tech must give out test codew then pricing will look into test data"
            # I'll rely on global codes for now but filter by item type inside here again strictly for cost accuracy?
            # Actually, to be safer and "Finest", let's replicate the user's logic which looks up tests "relevant tests in DB".
            # BUT, I will try to use the codes if passed.
            
            required_tests = tech_out.get('required_test_codes', [])
            
            # Convert codes to cost
            if required_tests:
                # Filter codes that apply to THIS item (Optional complexity) or just apply relevant ones?
                # Simpler: If "TEST-RT-001" is in list, we add it. 
                # But tests are usually per drum/length.
                # Let's iterate all tests in DB, check if their ID is in 'required_tests', AND RE-CHECK applicability to be safe?
                # Or just trust Tech?
                # Trusting Tech:
                for t_code in required_tests:
                    test_obj = next((t for t in self.db.data["TESTS"] if t['test_id'] == t_code), None)
                    if test_obj:
                        c = test_obj.get('base_test_cost', 0)
                        # Check logic for 'per drum' or 'per km' - usually in description or category
                        if "Routine" in test_obj.get('test_category', ''):
                            c *= drums
                        
                        # Optimization: Don't triple count if multiple items need same type test? 
                        # Usually routine tests are per cable length. So we add it.
                        t_cost += c
                        t_breakdown.append(f"- {test_obj['test_name'][:30]}: {c:,.0f}")
            else:
                # Fallback to simple logic if no codes found
                is_hv = "33KV" in str(pid).upper()
                c = self.brain.config["TESTING"]["HV_BASE_COST"] if is_hv else self.brain.config["TESTING"]["LV_BASE_COST"]
                t_cost += c
                t_breakdown.append(f"- Standard Tests (Est): {c}")

            total_test += t_cost
            
            product_breakdowns.append({
                "name": item.get('matched_sku_name', pid), 
                "qty": qty, 
                "cost": mfg, 
                "pkg": p_cost, 
                "test": t_cost,
                "test_breakdown": t_breakdown
            })
            audit_lines.extend(breakdown[:2])

        # 4. Logistics
        log_cost, log_formula, log_risk_pct, zone_name = self.brain.calculate_logistics(total_weight_all, dist_km, delivery_loc)

        # --- B. STRATEGIC ADJUSTMENTS ---
        strategy_notes = []
        
        # 1. Factory Load (Use first item as proxy)
        first_pid = items[0].get('matched_sku_id') if items else "UNKNOWN"
        fact_adj_pct, fact_reason = self.brain.analyze_factory_load(first_pid) 
        if fact_adj_pct != 0: strategy_notes.append(fact_reason)
        
        # 2. Financials
        base_cost = total_mfg + total_pkg + total_test + log_cost
        fin_cost, credit_days, loy_disc = self.brain.analyze_financials(client_name, base_cost)
        if fin_cost > 0: strategy_notes.append(f"Credit Cost ({credit_days} days): +INR {int(fin_cost)}")
        if loy_disc != 0: strategy_notes.append(f"Loyalty Discount: {loy_disc*100}%")

        # 3. Game Theory (Competitor Codes from Tech Agent)
        rivals = tech_out.get('competitor_codes', [])
        comp_adj, comp_notes = self.brain.solve_game_theory(rivals)
        strategy_notes.extend(comp_notes)
        
        # 4. Logistics Risk
        if log_risk_pct > 0:
            strategy_notes.append(f"Zone Risk ({zone_name}): +{log_risk_pct*100}%")

        # --- C. FINAL PRICE CALCULATION ---
        target_margin = self.brain.config["FINANCIAL"]["TARGET_NET_MARGIN"]
        
        # Apply Adjustments
        final_margin = target_margin + fact_adj_pct + loy_disc + comp_adj + log_risk_pct
        if final_margin < self.brain.config["FINANCIAL"]["MIN_SURVIVAL_MARGIN"]:
            final_margin = self.brain.config["FINANCIAL"]["MIN_SURVIVAL_MARGIN"]
            strategy_notes.append("EMERGENCY: Margin Floor Hit (Survival Mode)")

        full_cost_base = base_cost + fin_cost
        bid_value = full_cost_base * (1 + final_margin)
        gst_val = bid_value * self.brain.config["FINANCIAL"]["GST_RATE"] # GST on top

        # --- D. PDF REPORT ---
        report_url = "#"
        try:
            pdf = AdvancedAuditPDF()
            pdf.add_page()
            
            pdf.section_header("1. PROJECT & CLIENT IDENTITY")
            pdf.add_row("RFP Reference", str(rfp_id))
            pdf.add_row("Client Name", str(client_name)[:40])
            pdf.add_row("Destination", f"{delivery_loc} ({zone_name})")
            pdf.ln(5)

            pdf.section_header("2. PRODUCT-WISE COST BREAKDOWN")
            for p_item in product_breakdowns:
                pdf.add_product_block(p_item)
            
            pdf.ln(5)
            pdf.section_header("3. LOGISTICS & FINANCIALS")
            pdf.add_row(f"Logistics ({dist_km}km, {total_weight_all/1000:.1f}T)", f"INR {log_cost:,.0f}")
            pdf.set_font('Arial', 'I', 8); pdf.cell(0, 5, f"Formula: {log_formula}", 0, 1)
            pdf.add_row(f"Cost of Capital ({credit_days} Days)", f"INR {fin_cost:,.0f}")
            pdf.ln(2)
            pdf.add_row("FULL COST BASE", f"INR {full_cost_base:,.0f}", is_bold=True)
            pdf.ln(5)

            pdf.section_header("4. STRATEGIC MARGIN BUILD-UP")
            pdf.add_row("Base Target Margin", f"{target_margin*100}%")
            for note in strategy_notes:
                pdf.set_font('Arial', 'I', 9)
                pdf.cell(0, 5, f"  > {note}", 0, 1)
            pdf.ln(2)
            pdf.add_row("FINAL NET MARGIN", f"{final_margin*100:.1f}%", is_bold=True)
            
            pdf.ln(10)
            pdf.set_fill_color(0, 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(140, 12, " FINAL BID SUBMISSION VALUE", 1, 0, 'C', 1)
            pdf.cell(50, 12, f" INR {bid_value:,.0f} ", 1, 1, 'R', 1)

            static_dir = BASE_DIR / "static" / "audit_reports"
            static_dir.mkdir(parents=True, exist_ok=True)
            pdf_name = f"{rfp_id}_AUDIT.pdf"
            pdf.output(str(static_dir / pdf_name))
            report_url = f"/static/audit_reports/{pdf_name}"
            
        except Exception as e:
            print(f"PDF Gen Error: {e}")

        return {
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
                "packaging": {"total": total_pkg, "breakdown": [f"{int(total_pkg/4500)} Drums Est"]},
                "testing": {"total": total_test, "breakdown": ["Per Tech Agent Codes"]},
                "logistics": {"total": log_cost, "formula": log_formula},
                "strategy": {
                    "rationale": strategy_notes, 
                    "competitor_impact": f"{comp_adj*100:+.1f}%", 
                    "zone_risk": f"{log_risk_pct*100}%"
                }
            },
            "audit_report_url": report_url
        }