# Pricing Agent: Logic & Data Calculation Deep Dive

This document details exactly **what inputs** the Pricing Agent takes, **what databases** it consults, **what parameters** it processes, and **how** it calculates the final output.

---

## 1. EXACT INPUTS (What it reads)
The agent reads `input.json`. Specifically, it extracts the following **Code Identifiers** and **Values**:

### A. From Technical Agent (`tech_agent_output`)
*   **`competitor_codes`**: A list of IDs representing active rivals.
    *   *Example*: `["COMP-001", "COMP-003"]`
*   **`matched_product_id`**: The internal SKU ID mapped to the RFP line item.
    *   *Example*: `"PC-33KV-AL-3C-400"`
*   **`confirmed_quantity`**: The exact length of cable required.
    *   *Example*: `15000` (meters)

### B. From Sales Agent (`sales_agent_output`)
*   **`client_name`**: Used to lookup Client Tier/Loyalty.
    *   *Example*: `"Adani Transmission"`
*   **`delivery_location`**: Raw text used for Logistic Zone determination.
    *   *Example*: `"Khavda Desert Zone"`
*   **`distance_from_factory_km`**: Precise distance for freight calculation.
    *   *Example*: `680` (km)
*   **`payment_terms`**: Credit period string.
    *   *Example*: `"90 Days Credit"`

---

## 2. PROCESSING PARAMETERS (Factors & Databases)
The agent uses the input IDs to query **7 Master Databases**. Each query extracts specific **Parameters** for the calculation.

### A. Costing Parameters (The "Hard" Costs)
1.  **Product Master** (`product_master.json`)
    *   *Input*: `product_id`
    *   *Extracts*:
        *   **BOM List**: Array of `material_id` + `quantity_per_meter`.
        *   **Weight**: `weight_kg_per_unit` (e.g., 5.4 kg/m).
        *   **Voltage**: High Voltage vs Low Voltage (determines Testing/Packaging type).

2.  **Material Master** (`material_master.json`)
    *   *Input*: `material_id` (from BOM)
    *   *Extracts*:
        *   **Base Rate**: Current price (INR/kg).
        *   **Volatility Risk**: If "High", adds **Hedging Buffer** (2-5%).

3.  **Test Master** (`test_master.json`)
    *   *Input*: Product Voltage Grade
    *   *Extracts*:
        *   **Mandatory Tests**: Costs for "Routine" or "Type" tests based on compliance rules.

4.  **Logistic Master** (`logistic_master.json`)
    *   *Input*: `delivery_location` (Parsed for keywords like "Desert", "Hilly")
    *   *Extracts*:
        *   **Risk Zone**: e.g., "Z-05 Desert".
        *   **Surcharge**: e.g., 1.2x multiplier.
        *   **Risk %**: e.g., 4% buffer for breakage/theft.

### B. Strategic Parameters (The "Soft" Adjustments)
5.  **Competitor Database** (`competitors.json`)
    *   *Input*: `competitor_codes`
    *   *Extracts*:
        *   **Aggression Score**: (1-10). If > 8 -> **-3% Margin** (Defensive Price War).
        *   **Win Rate**: If > 60% -> **-2% Margin** (To regain market share).

6.  **Factory Schedule** (`factory_production_schedule.json`)
    *   *Input*: `product_id` (Category matching)
    *   *Extracts*:
        *   **Utilization %**:
            *   > 90% (Full) -> **+5% Margin** (Scarcity Premium).
            *   < 30% (Empty) -> **-3% Margin** (Idle Discount).

7.  **Client Master** (`client_master.json`)
    *   *Input*: `client_name`
    *   *Extracts*:
        *   **Loyalty**: "Gold" -> **-3% Discount**. "Silver" -> **-1.5%**.

---

## 3. FINAL OUTPUT CALCULATION (The Formula)

The agent runs a **Waterfall Calculation** to reach the `final_bid_value`.

### Step 1: Base Factory Cost
```text
Material_Cost = Sum(Mat_Qty * Base_Rate * Market_Factor) + Hedging_Buffer
Factory_Cost  = Material_Cost + (Material_Cost * 0.12 Overhead) + Pkg_Cost + Test_Cost
```

### Step 2: Logistics Cost
```text
Total_Weight = Qty_Meters * Weight_per_Meter
Freight = Total_Weight * Distance_km * Base_Rate * Zone_Surcharge_Multiplier
```

### Step 3: Financial Cost
```text
Interest_Cost = (Factory_Cost + Freight) * (12% Annual_Rate * Credit_Days / 365)
```
*> Note: This is an "add-on" cost to recover interest lose due to delayed payment.*

### Step 4: Strategic Margin
```text
Base_Margin = 22%
Adjusted_Margin = 22% + Factory_Load_Adj - Rival_Aggression_Adj - Loyalty_Disc + Zone_Risk_Buffer
```
*(Minimum Floor: 4% Survival Margin)*

### Step 5: Final Price
```text
Total_Cost_Base = Factory_Cost + Freight + Interest_Cost
Final_Bid_Value = Total_Cost_Base * (1 + Adjusted_Margin)
```

---

## 4. EXAMPLE SCENARIO (RFP-2025-101)
*   **Product**: 15km of 33kV Cable
*   **Loc**: Khavda Desert (680km)
*   **Rival**: Polycab (Aggression 6)
*   **Client**: Gold Status (90 Days Credit)

**The Math:**
1.  **Material**: 29.9M (Includes High Volatility Buffer for Aluminum).
2.  **Logistics**: 0.9M (Desert Zone Surcharge).
3.  **Finance**: +1.05M (Cost of giving 90 days credit).
4.  **Margin Adjustment**:
    *   Base: 22%
    *   Loyalty: -3%
    *   Zone Risk: +4%
    *   **Final Margin**: **23%**
5.  **Final Price**: (35.4M Base + 1.05M Interest) * 1.23 = **~44.8 Million INR**
