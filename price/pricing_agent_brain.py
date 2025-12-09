import pandas as pd
import json
import os

class PricingAgent:
    def __init__(self, db_folder="database"):
        print("🤖 PRICING AGENT: Loading Knowledge Base...")
        try:
            # Helper: Clean headers and data
            def clean_df(df):
                df.columns = df.columns.str.strip()
                df_obj = df.select_dtypes(['object'])
                df[df_obj.columns] = df_obj.apply(lambda x: x.str.strip())
                return df

            # 1. LOAD BASE COST FILES
            base_path = f"{db_folder}/base cost"
            self.products = clean_df(pd.read_csv(f"{base_path}/product_master.csv"))
            self.recipes = clean_df(pd.read_csv(f"{base_path}/product_recipes.csv"))
            self.materials = clean_df(pd.read_csv(f"{base_path}/material_master.csv"))
            self.inventory = clean_df(pd.read_csv(f"{base_path}/factory_inventory_master.csv"))
            self.schedule = clean_df(pd.read_csv(f"{base_path}/factory_production_schedule.csv"))

            # 2. LOAD STRATEGIC FACTOR FILES
            strat_path = f"{db_folder}/strategic factors"
            self.clients = clean_df(pd.read_csv(f"{strat_path}/client_master.csv"))
            self.competitors = clean_df(pd.read_csv(f"{strat_path}/competitor_intelligence.csv"))
            self.history = clean_df(pd.read_csv(f"{strat_path}/past_tender_history.csv"))

            # 3. LOAD SURCHARGE FACTOR FILES
            sur_path = f"{db_folder}/surcharge factor"
            self.logistics = clean_df(pd.read_csv(f"{sur_path}/logistics_rules.csv"))

            print("✅ SYSTEM READY: Databases loaded & Cleaned.")
        except FileNotFoundError as e:
            print(f"❌ CRITICAL ERROR: Database missing. {e}")

    def _check_factory_status(self, product_id, qty_needed):
        stock_row = self.inventory[self.inventory['product_id'] == product_id]
        if stock_row.empty: return "Make-to-Order", 0
        
        available_stock = int(stock_row.iloc[0]['qty_available_for_sale'])
        if available_stock >= qty_needed:
            return "Stock", 0
        
        if 'unallocated_qty' in self.schedule.columns:
            incoming = self.schedule[(self.schedule['product_id'] == product_id) & (self.schedule['unallocated_qty'].astype(float) > 0)]
            if (available_stock + incoming['unallocated_qty'].astype(float).sum()) >= qty_needed:
                return "Incoming-Batch", 0
        
        return "Make-to-Order", 1 

    def _calculate_cost_components_per_unit(self, product_id, qty, mode):
        prod_row = self.products[self.products['product_id'] == product_id]
        if prod_row.empty: return {"material": 0, "labor": 0, "setup": 0, "total": 0, "warnings": []}
        prod_info = prod_row.iloc[0]
        
        setup_fee = float(prod_info['setup_cost']) if mode == "Make-to-Order" else 0
        setup_per_unit = setup_fee / qty
        
        my_recipe = self.recipes[self.recipes['product_id'] == product_id]
        total_mat_cost = 0
        risk_warnings = []

        for _, row in my_recipe.iterrows():
            mat_info = self.materials[self.materials['material_id'] == row['material_id']].iloc[0]
            base_cost = float(mat_info['base_cost_per_unit'])
            
            # Math Factor
            db_factor = float(mat_info.get('current_market_factor', 1.0))
            final_mat_cost = base_cost * db_factor
            total_mat_cost += (final_mat_cost * float(row['quantity_required']))

            # Intelligence Warning
            if mat_info.get('volatility_risk_level') == 'High':
                risk_warnings.append(f"High Volatility: {mat_info['material_name']} ({db_factor}x)")
            
        labor_cost = float(prod_info['base_mfg_cost'])
        
        return {
            "material": total_mat_cost,
            "labor": labor_cost,
            "setup": setup_per_unit,
            "total_production_unit": total_mat_cost + labor_cost + setup_per_unit,
            "risk_log": risk_warnings
        }

    def _calculate_transport_cost_per_unit(self, product_id, zone_code, distance_km):
        prod_row = self.products[self.products['product_id'] == product_id]
        if prod_row.empty: return 0
        weight_kg = float(prod_row.iloc[0].get('weight_kg_per_unit', 1.0))
        weight_tons = weight_kg / 1000.0

        zone_data = self.logistics[self.logistics['zone_code'] == zone_code]
        if zone_data.empty:
            print(f"   ⚠️ Warning: Zone Code '{zone_code}' not found. Defaulting to Z-01.")
            zone_data = self.logistics[self.logistics['zone_code'] == "Z-01"]
            
        zone_rule = zone_data.iloc[0]
        rate = float(zone_rule['transport_rate_per_ton_km'])
        multiplier = float(zone_rule['surcharge_multiplier'])

        return weight_tons * distance_km * rate * multiplier

    def _get_margin_composition(self, client_id, competitor_id):
        """ 
        UPDATED LOGIC: 
        1. Takes the WORST case between 'Undercut' and 'Win Rate' (Avoids double counting).
        2. Hides 'No Change' messages.
        """
        base_margin = 0.20 
        adjustments = []
        
        # --- COMPETITOR STRATEGY ---
        if competitor_id:
            comp_data = self.competitors[self.competitors['competitor_id'] == competitor_id]
            
            if not comp_data.empty:
                comp_info = comp_data.iloc[0]
                comp_name = comp_info['competitor_name']
                
                # A. Undercut Risk
                undercut = float(comp_info['avg_undercut_percent'])
                risk_undercut = undercut if undercut > 0 else 0.0
                
                # B. History Risk (Match ID or Name)
                history_clean = self.history.copy()
                history_clean['competitor_present'] = history_clean['competitor_present'].astype(str).str.strip().str.upper()
                
                search_id = str(competitor_id).strip().upper()
                search_name = str(comp_name).strip().upper()
                
                past_matches = self.history[
                    (history_clean['competitor_present'] == search_id) | 
                    (history_clean['competitor_present'] == search_name)
                ]
                
                risk_history = 0.0
                if not past_matches.empty:
                    wins = past_matches[past_matches['outcome'].str.lower() == 'won']
                    win_rate = len(wins) / len(past_matches)
                    print(f"   📊 AI INSIGHT: Win Rate against {competitor_id} is {int(win_rate*100)}%")
                    
                    if win_rate < 0.30:
                        risk_history = 0.05 # Panic value
                
                # C. DECISION: Take the Max Risk (Don't sum them)
                final_competitor_cut = max(risk_undercut, risk_history)
                
                if final_competitor_cut > 0:
                    base_margin -= final_competitor_cut
                    reason = "Competitor Aggression" if risk_undercut >= risk_history else "Critical Low Win Rate"
                    adjustments.append({"reason": f"{reason} ({comp_name})", "value": f"-{round(final_competitor_cut*100, 1)}%"})
            else:
                adjustments.append({"reason": f"Competitor ID {competitor_id} Not Found", "value": "0.0%"})

        # --- CLIENT STRATEGY ---
        if client_id:
            client_data = self.clients[self.clients['client_id'] == client_id]
            if not client_data.empty:
                tier = client_data.iloc[0]['tier']
                # Check DB discount first
                db_disc = float(client_data.iloc[0].get('default_discount_percent', 0.0))
                
                if db_disc > 0:
                    base_margin -= db_disc
                    adjustments.append({"reason": f"Loyalty Discount ({tier})", "value": f"-{round(db_disc*100, 1)}%"})
                elif tier == 'Gold': # Fallback if DB column is empty
                    base_margin -= 0.02
                    adjustments.append({"reason": "Client Loyalty Discount (Gold)", "value": "-2.0%"})

        return base_margin, adjustments

    def generate_tender_quote(self, input_rfp):
        print(f"\n💡 PROCESSING TENDER FOR: {input_rfp.get('client_name', 'Unknown')}")
        
        acc_material = 0
        acc_labor = 0
        acc_setup = 0
        acc_transport = 0
        acc_finance = 0
        acc_total_bid = 0
        
        line_items = []
        
        # Strategy
        final_margin_pct, margin_breakdown = self._get_margin_composition(
            input_rfp.get('client_id'), 
            input_rfp.get('competitor_id')
        )

        for item in input_rfp['requested_items']:
            sku = item['sku']
            qty = item['qty']
            
            mode, _ = self._check_factory_status(sku, qty)
            cost_comps = self._calculate_cost_components_per_unit(sku, qty, mode)
            
            distance = input_rfp.get('distance_km', 500)
            zone_code = input_rfp.get('delivery_zone_code') or input_rfp.get('delivery_zone')
            unit_transport = self._calculate_transport_cost_per_unit(sku, zone_code, distance)
            
            unit_finance = 0
            if "90 Days" in input_rfp['payment_terms']:
                unit_finance = cost_comps['total_production_unit'] * 0.03
            
            unit_total_cost = cost_comps['total_production_unit'] + unit_transport + unit_finance
            unit_final_price = unit_total_cost * (1 + final_margin_pct)
            
            acc_material += (cost_comps['material'] * qty)
            acc_labor += (cost_comps['labor'] * qty)
            acc_setup += (cost_comps['setup'] * qty)
            acc_transport += (unit_transport * qty)
            acc_finance += (unit_finance * qty)
            acc_total_bid += (unit_final_price * qty)
            
            line_items.append({
                "sku": sku,
                "qty": qty,
                "breakdown_per_unit": {
                    "material": round(cost_comps['material'], 2),
                    "labor_mfg": round(cost_comps['labor'], 2),
                    "transport": round(unit_transport, 2)
                },
                "risk_alerts": cost_comps['risk_log'],
                "final_unit_price": round(unit_final_price, 2),
                "line_total_value": round(unit_final_price * qty, 2)
            })

        total_production = acc_material + acc_labor + acc_setup
        total_overheads = acc_transport + acc_finance
        total_project_cost = total_production + total_overheads
        estimated_profit = acc_total_bid - total_project_cost
        
        rfp_id_tag = input_rfp.get('rfp_id', 'UNKNOWN-RFP')
        zone_display = input_rfp.get('delivery_zone_code') or input_rfp.get('delivery_zone')

        output_data = {
            "tender_summary": {
                "rfp_processing_id": rfp_id_tag,
                "client_id": input_rfp.get('client_id'), 
                "logistics_param": f"{input_rfp.get('distance_km')} km to {zone_display}",
                
                "cost_breakdown_bill": {
                    "1_total_raw_material": round(acc_material, 2),
                    "2_total_labor_mfg": round(acc_labor, 2),
                    "3_total_setup_mto": round(acc_setup, 2),
                    "4_total_transport": round(acc_transport, 2),
                    "5_total_finance": round(acc_finance, 2)
                },

                "internal_accounting_ledger": {
                    "A_total_production_cost": round(total_production, 2),
                    "B_total_overheads_cost": round(total_overheads, 2),
                    "C_total_project_cost_A_plus_B": round(total_project_cost, 2),
                    "D_estimated_net_profit": round(estimated_profit, 2),
                    "E_grand_total_bid_C_plus_D": round(acc_total_bid, 2)
                },
                
                "final_margin_percentage": f"{round(final_margin_pct*100, 1)}%"
            },
            "margin_composition_report": {
                "standard_company_margin": "20.0%",
                "adjustments_applied": margin_breakdown,
                "final_effective_margin": f"{round(final_margin_pct*100, 1)}%"
            },
            "line_items": line_items
        }
        return output_data

if __name__ == "__main__":
    if os.path.exists("input.json"):
        with open("input.json", "r") as f:
            data = json.load(f)
        agent = PricingAgent()
        quote = agent.generate_tender_quote(data['rfp_details'])
        
        with open("output.json", "w") as f:
            json.dump(quote, f, indent=4)
        print(f"✅ SUCCESS: Quote generated for {quote['tender_summary']['rfp_processing_id']}.")
    else:
        print("⚠️ 'input.json' not found.")