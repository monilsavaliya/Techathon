# 🤖 Agentic AI Pricing Engine (B2B Tender Automation)

## 📌 Project Overview
This project implements an autonomous **Pricing Agent** designed for the manufacturing sector (e.g., Asian Paints / Polycab). It automates the complex process of generating financial bids for B2B RFPs (Request for Proposals).

Unlike a simple calculator, this Agent uses **Heuristic AI Logic** to determine the optimal price by analyzing:
1.  **Real-Time Costs:** Raw material volatility (LME Copper Index).
2.  **Factory Constraints:** Inventory levels vs. Production schedules (Stock vs. Make-to-Order).
3.  **Logistics:** Weight-based transport costs mapped to geographical terrain zones.
4.  **Game Theory:** Competitor aggression levels and historical win/loss rates.

---

## 🚀 Key Features

### 1. Dynamic Manufacturing Logic
The agent checks the `factory_inventory_master.csv` and `factory_production_schedule.csv` before pricing.
* **Scenario A (Stock Available):** Uses standard cost.
* **Scenario B (Incoming Batch):** Allocates "unclaimed" future stock (No setup fee).
* **Scenario C (Make-to-Order):** Automatically adds **Setup Costs** and **Rush Surcharges** if manufacturing lines must be interrupted.

### 2. Intelligent Logistics Engine
Instead of a flat % fee, the agent calculates precise transport costs:
* **Formula:** `Weight (Tons) × Distance (km) × Rate/Ton/km × Terrain Multiplier`
* **Intelligence:** Automatically maps cities to zones (e.g., "Shimla" → **Hilly_Remote** → 2.5x Cost Multiplier).

### 3. Strategic Margin Optimization (The "AI Brain")
The Agent determines the profit margin dynamically using a **Waterfall Strategy**:
* **Base Margin:** Starts at 20%.
* **Competitor Check:** If a rival like *RivalCables* is detected, the agent drops the margin to match their historical undercut % (e.g., -5%).
* **Win Rate Analysis:** If we historically lose >70% of bids against this rival, the agent applies a "Panic Drop" (-5%) to ensure a win.
* **Client Loyalty:** Applies automatic discounts for Gold/Platinum tier clients.

### 4. Volatility Protection
The agent reads `material_master.csv` to identify high-risk materials (e.g., Copper). It applies a **Real-Time Market Factor** (e.g., 1.15x) to the raw material cost to protect against inflation during the tender validity period.

---

## 📂 System Architecture & Data Composition

The logic is powered by a relational CSV database organized into three layers:

### A. Base Cost Layer (`database/base cost/`)
| File | Purpose |
| :--- | :--- |
| **`product_master.csv`** | Base manufacturing cost (Labor/Machine) and Weight per unit. |
| **`product_recipes.csv`** | Bill of Materials (BOM) linking Products to Ingredients. |
| **`material_master.csv`** | Live raw material costs & Volatility Risk Flags. |
| **`factory_inventory_master.csv`** | Live warehouse stock levels. |
| **`factory_production_schedule.csv`** | Future batch visibility for capacity planning. |

### B. Strategic Layer (`database/strategic factors/`)
| File | Purpose |
| :--- | :--- |
| **`client_master.csv`** | Client Tiers (Gold/Silver), Payment Terms, and Strategic Value. |
| **`competitor_intelligence.csv`** | Profiles of rivals (Aggressive vs. Premium) and Undercut %. |
| **`past_tender_history.csv`** | Historical Win/Loss data used to calculate Win Rates. |

### C. Surcharge Layer (`database/surcharge factor/`)
| File | Purpose |
| :--- | :--- |
| **`logistics_rules.csv`** | Zone-based multipliers (Hilly, Coastal, Urban) and freight rates. |

---

## ⚙️ How It Works (The Execution Flow)

1.  **Input:** The agent receives a JSON payload (`input.json`) containing the RFP details (Client ID, Delivery Zone, Competitor ID, Requested Items).
2.  **Factory Check:** It loops through requested items. If `Qty > Stock`, it triggers "Make-to-Order" logic.
3.  **Cost Buildup:**
    * *Material Cost* = Sum(Ingredient Cost × Qty × Market Factor)
    * *Production Cost* = Material + Labor + (Setup / Qty)
4.  **Overheads Calculation:**
    * *Transport* = Weight × Distance × Zone Rate
    * *Finance* = Cost × Interest Rate (if Payment Terms > 90 Days)
5.  **Strategic Pricing:** The AI adjusts the margin based on the Rival + Client analysis.
6.  **Output:** Generates a detailed financial breakdown in `output.json` including a **Strict Accounting Ledger** (Production vs. Overheads vs. Profit).

---

## 💻 Usage Instructions

### Prerequisites
* Python 3.x
* Pandas Library (`pip install pandas`)

### Running the Agent
1.  Ensure the `database/` folder is populated with the CSV files.
2.  Configure your scenario in `input.json`.
3.  Run the script:
    ```bash
    python pricing_agent_final.py
    ```
4.  Check the results in `output.json`.

---

## 📊 Example Output Snippet

```json
"tender_summary": {
    "client": "Sharma Infra",
    "logistics_param": "1250 km to Hilly_Remote",
    "total_production_cost": 22840875.0,
    "total_overheads_cost": 10247726.25,
    "total_project_cost": 33088601.25,
    "estimated_net_profit": 4301518.16,
    "grand_total_bid": 37390119.41,
    "final_margin_percentage": "13.0%"
},
"margin_composition_report": {
    "standard_company_margin": "20.0%",
    "adjustments_applied": [
        { "reason": "Competitor Aggression (RivalCables Ltd)", "value": "-5.0%" },
        { "reason": "Client Loyalty Discount (Gold)", "value": "-2.0%" }
    ],
    "final_effective_margin": "13.0%"
}
