import pandas as pd
import json
import os

class PricingAgent:
    def __init__(self, db_folder="database"):
        print("🤖 PRICING AGENT: Loading Knowledge Base from Subfolders...")
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

            print("✅ SYSTEM READY: All databases loaded successfully.")
        except FileNotFoundError as e:
            print(f"❌ CRITICAL ERROR: Database missing. Check your folder structure. {e}")

    def _check_factory_status(self, product_id, qty_needed):
        """ Checks Inventory vs Schedule to determine Production Mode """
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

    def _calculate_unit_production_cost(self, product_id, qty, mode, market_factor):
        """ 
        Calculates PURE Manufacturing Cost (Material + Labor + Setup).
        Does NOT include Logistics or Finance.
        """
        prod_row = self.products[self.products['product_id'] == product_id]
        if prod_row.empty: return 0
        prod_info = prod_row.iloc[0]
        
        setup_fee = prod_info['setup_cost'] if mode == "Make-to-Order" else 0
        
        my_recipe = self.recipes[self.recipes['product_id'] == product_id]
        total_mat_cost = 0
        
        for _, row in my_recipe.iterrows():
            mat_info = self.materials[self.materials['material_id'] == row['material_id']].iloc[0]
            cost = mat_info['base_cost_per_unit']
            
            if "LME" in str(mat_info.get('linked_commodity_index', '')):
                cost = cost * market_factor
            
            total_mat_cost += (cost * row['quantity_required'])
            
        # Cost per unit derived from (Mfg + Mat) + Amortized Setup
        unit_cost = prod_info['base_mfg_cost'] + total_mat_cost + (setup_fee / qty)
        return unit_cost

    def _get_margin_composition(self, client_id, competitor_name):
        """ Generates the detailed 'Profit Cut' breakdown """
        base_margin = 0.20 # Standard 20%
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
        
        # Accumulators for accounting
        acc_production_cost = 0
        acc_overheads_cost = 0
        acc_total_bid = 0
        
        line_items = []
        
        # A. Determine Strategy
        client_row = self.clients[self.clients['client_name'] == input_rfp['client_name']]
        client_id = client_row.iloc[0]['client_id'] if not client_row.empty else None
        
        final_margin_pct, margin_breakdown = self._get_margin_composition(
            client_id, input_rfp.get('competitor_detected')
        )

        # B. Process Items
        for item in input_rfp['requested_items']:
            sku = item['sku']
            qty = item['qty']
            
            # 1. Calculate PURE Production Cost
            mode, _ = self._check_factory_status(sku, qty)
            unit_prod_cost = self._calculate_unit_production_cost(sku, qty, mode, simulation_params['copper_market_factor'])
            
            # 2. Calculate Overheads (Logistics + Finance)
            # Logistics
            zone_data = self.logistics[self.logistics['zone_type'] == input_rfp['delivery_zone']].iloc[0]
            logistics_pct = (zone_data['surcharge_multiplier'] - 1.0)
            unit_logistics_cost = unit_prod_cost * logistics_pct
            
            # Finance
            finance_pct = 0.03 if "90 Days" in input_rfp['payment_terms'] else 0
            unit_finance_cost = unit_prod_cost * finance_pct
            
            # Total Cost (Production + Overheads)
            unit_total_cost = unit_prod_cost + unit_logistics_cost + unit_finance_cost
            
            # 3. Calculate Final Price
            unit_final_price = unit_total_cost * (1 + final_margin_pct)
            
            # 4. Line Item Totals
            line_prod_cost = unit_prod_cost * qty
            line_overhead_cost = (unit_logistics_cost + unit_finance_cost) * qty
            line_bid_val = unit_final_price * qty
            
            # Accumulate Global Totals
            acc_production_cost += line_prod_cost
            acc_overheads_cost += line_overhead_cost
            acc_total_bid += line_bid_val
            
            line_items.append({
                "sku": sku,
                "qty": qty,
                "mode": mode,
                "unit_breakdown": {
                    "pure_production_cost": round(unit_prod_cost, 2),
                    "overheads_cost": round(unit_logistics_cost + unit_finance_cost, 2)
                },
                "final_unit_price": round(unit_final_price, 2),
                "line_total_value": round(line_bid_val, 2)
            })

        # C. FINAL ACCOUNTING
        total_project_cost = acc_production_cost + acc_overheads_cost
        
        # Calculate Profit as the EXACT residual
        estimated_profit = acc_total_bid - total_project_cost

        # Construct Output (Clean Keys)
        output_data = {
            "tender_summary": {
                "client": input_rfp['client_name'],
                "status": "Generated",
                
                # --- CLEAN ACCOUNTING BREAKDOWN ---
                "total_production_cost": round(acc_production_cost, 2),
                "total_overheads_cost": round(acc_overheads_cost, 2),
                "total_project_cost": round(total_project_cost, 2),
                
                "estimated_net_profit": round(estimated_profit, 2),
                
                "grand_total_bid": round(acc_total_bid, 2),
                
                "final_margin_percentage_applied": f"{round(final_margin_pct*100, 1)}%"
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
            
        print("✅ SUCCESS: Quote generated.")
        
        # Verification Print
        summary = quote['tender_summary']
        check = summary['total_project_cost'] + summary['estimated_net_profit']
        
        print(f"📊 VERIFICATION:")
        print(f"   Total Cost ({summary['total_project_cost']}) + Profit ({summary['estimated_net_profit']}) = {round(check, 2)}")
        print(f"   Matches Bid? {'YES' if round(check, 2) == summary['grand_total_bid'] else 'NO'}")
    else:
        print("⚠️ 'input.json' not found.")