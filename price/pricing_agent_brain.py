import pandas as pd
import json
import os

class PricingAgent:
    def __init__(self, db_folder="database"):
        print("🤖 PRICING AGENT: Loading Knowledge Base...")
        try:
            # 1. LOAD BASE COST FILES
            base_path = f"{db_folder}/base cost"
            self.products = pd.read_csv(f"{base_path}/product_master.csv")
            self.recipes = pd.read_csv(f"{base_path}/product_recipes.csv")
            self.materials = pd.read_csv(f"{base_path}/material_master.csv")
            self.inventory = pd.read_csv(f"{base_path}/factory_inventory_master.csv")
            self.schedule = pd.read_csv(f"{base_path}/factory_production_schedule.csv")

            # 2. LOAD STRATEGIC FACTOR FILES
            strat_path = f"{db_folder}/strategic factors"
            self.clients = pd.read_csv(f"{strat_path}/client_master.csv")
            self.competitors = pd.read_csv(f"{strat_path}/competitor_intelligence.csv")
            self.history = pd.read_csv(f"{strat_path}/past_tender_history.csv")

            # 3. LOAD SURCHARGE FACTOR FILES
            sur_path = f"{db_folder}/surcharge factor"
            self.logistics = pd.read_csv(f"{sur_path}/logistics_rules.csv")

            print("✅ SYSTEM READY: Databases loaded.")
        except FileNotFoundError as e:
            print(f"❌ CRITICAL ERROR: Database missing. {e}")

    def _check_factory_status(self, product_id, qty_needed):
        """ Checks Inventory vs Schedule """
        stock_row = self.inventory[self.inventory['product_id'] == product_id]
        if stock_row.empty: return "Make-to-Order", 0
        
        available_stock = stock_row.iloc[0]['qty_available_for_sale']
        if available_stock >= qty_needed:
            return "Stock", 0
        
        if 'unallocated_qty' in self.schedule.columns:
            incoming = self.schedule[(self.schedule['product_id'] == product_id) & (self.schedule['unallocated_qty'] > 0)]
            if (available_stock + incoming['unallocated_qty'].sum()) >= qty_needed:
                return "Incoming-Batch", 0
        
        return "Make-to-Order", 1 

    def _calculate_cost_components_per_unit(self, product_id, qty, mode, market_factor):
        """ Breakdown: Material, Labor, Setup """
        prod_row = self.products[self.products['product_id'] == product_id]
        if prod_row.empty: return {"material": 0, "labor": 0, "setup": 0, "total": 0}
        prod_info = prod_row.iloc[0]
        
        setup_fee = prod_info['setup_cost'] if mode == "Make-to-Order" else 0
        setup_per_unit = setup_fee / qty
        
        my_recipe = self.recipes[self.recipes['product_id'] == product_id]
        total_mat_cost = 0
        for _, row in my_recipe.iterrows():
            mat_info = self.materials[self.materials['material_id'] == row['material_id']].iloc[0]
            cost = mat_info['base_cost_per_unit']
            if "LME" in str(mat_info.get('linked_commodity_index', '')):
                cost = cost * market_factor
            total_mat_cost += (cost * row['quantity_required'])
            
        labor_cost = prod_info['base_mfg_cost']
        
        return {
            "material": total_mat_cost,
            "labor": labor_cost,
            "setup": setup_per_unit,
            "total_production_unit": total_mat_cost + labor_cost + setup_per_unit
        }

    def _calculate_transport_cost_per_unit(self, product_id, zone, distance_km):
        """ Distance * Weight * Rate """
        prod_row = self.products[self.products['product_id'] == product_id]
        if prod_row.empty: return 0
        weight_kg = prod_row.iloc[0].get('weight_kg_per_unit', 1.0)
        weight_tons = weight_kg / 1000.0

        zone_data = self.logistics[self.logistics['zone_type'] == zone].iloc[0]
        rate = zone_data['transport_rate_per_ton_km']
        multiplier = zone_data['surcharge_multiplier']

        return weight_tons * distance_km * rate * multiplier

    def _get_margin_composition(self, client_id, competitor_name):
        base_margin = 0.20 
        adjustments = []
        if competitor_name:
            comp_data = self.competitors[self.competitors['competitor_name'] == competitor_name]
            if not comp_data.empty:
                undercut = comp_data.iloc[0]['avg_undercut_percent']
                if undercut > 0:
                    base_margin -= undercut
                    adjustments.append({"reason": f"Competitor Impact ({competitor_name})", "value": f"-{round(undercut*100, 1)}%"})
        client_data = self.clients[self.clients['client_id'] == client_id]
        if not client_data.empty:
            tier = client_data.iloc[0]['tier']
            if tier == 'Gold':
                base_margin -= 0.02
                adjustments.append({"reason": "Client Loyalty Discount (Gold)", "value": "-2.0%"})
        return base_margin, adjustments

    def generate_tender_quote(self, input_rfp, simulation_params):
        print(f"\n💡 PROCESSING TENDER FOR: {input_rfp['client_name']}")
        
        acc_material = 0
        acc_labor = 0
        acc_setup = 0
        acc_transport = 0
        acc_finance = 0
        acc_total_bid = 0
        
        line_items = []
        
        client_row = self.clients[self.clients['client_name'] == input_rfp['client_name']]
        client_id = client_row.iloc[0]['client_id'] if not client_row.empty else None
        final_margin_pct, margin_breakdown = self._get_margin_composition(client_id, input_rfp.get('competitor_detected'))

        for item in input_rfp['requested_items']:
            sku = item['sku']
            qty = item['qty']
            
            mode, _ = self._check_factory_status(sku, qty)
            cost_comps = self._calculate_cost_components_per_unit(sku, qty, mode, simulation_params['copper_market_factor'])
            
            distance = input_rfp.get('distance_km', 500)
            unit_transport = self._calculate_transport_cost_per_unit(sku, input_rfp['delivery_zone'], distance)
            
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
                "final_unit_price": round(unit_final_price, 2),
                "line_total_value": round(unit_final_price * qty, 2)
            })

        total_production = acc_material + acc_labor + acc_setup
        total_overheads = acc_transport + acc_finance
        total_project_cost = total_production + total_overheads
        estimated_profit = acc_total_bid - total_project_cost

        # GRAB RFP ID SAFELY
        rfp_id_tag = input_rfp.get('rfp_id', 'UNKNOWN-RFP')

        output_data = {
            "tender_summary": {
                "rfp_processing_id": rfp_id_tag, # <--- HERE IT IS
                "client": input_rfp['client_name'],
                "logistics_param": f"{input_rfp.get('distance_km')} km to {input_rfp['delivery_zone']}",
                
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
        quote = agent.generate_tender_quote(data['rfp_details'], data['simulation_params'])
        
        with open("output.json", "w") as f:
            json.dump(quote, f, indent=4)
        print(f"✅ SUCCESS: Quote generated for {quote['tender_summary']['rfp_processing_id']}.")
    else:
        print("⚠️ 'input.json' not found.")
