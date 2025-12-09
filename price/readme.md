# 🤖 Pricing Agent Logic Documentation

## Overview
This agent determines the B2B Tender Price by analyzing 3 core layers: **Cost**, **Risk**, and **Strategy**.

## 📊 Factors & Decision Matrix

### 1. Base Costing Factors (The "Technical" Layer)
| Factor | Source | Logic Applied |
| :--- | :--- | :--- |
| **Material Recipe** | `product_recipes.csv` | Sum of raw materials (Copper, Steel, PVC) needed per unit. |
| **Real-Time Volatility** | Simulated Feed | If LME Commodity Index is "Rising", add volatility buffer (e.g., +8%). |
| **Factory Inventory** | `factory_inventory.csv` | If Stock > Demand → Use Standard Cost. <br> If Stock < Demand → Trigger "Make-to-Order" mode. |
| **Setup Costs** | `product_master.csv` | If "Make-to-Order" mode is active, add Amortized Setup Fee + Rush Surcharge. |

### 2. Surcharge Factors (The "Risk" Layer)
| Factor | Source | Logic Applied |
| :--- | :--- | :--- |
| **Logistics Zone** | `logistics_rules.csv` | Maps Delivery City to Zone (Hill/Plain/Coastal). <br> *Example:* Hilly Remote = +15% Transport Cost. |
| **Payment Terms** | Input JSON | Cost of Capital calculation. <br> *Example:* "90 Days Credit" = +3% Finance Surcharge. |

### 3. Strategic Factors (The "Profit" Layer)
| Factor | Source | Logic Applied |
| :--- | :--- | :--- |
| **Competitor Intel** | `competitor_intelligence.csv` | Checks who is bidding. <br> *Rule:* If "Aggressive Rival" detected, drop margin to match their historical undercut. |
| **Client Tier** | `client_master.csv` | Checks Relationship Status. <br> *Rule:* Gold Tier clients get automatic Loyalty Discounts (e.g., -2%). |
| **Win/Loss History** | `past_tender_history.csv` | (ML Simulation) If we historically lose high-margin bids against this rival, the agent forces a lower margin. |