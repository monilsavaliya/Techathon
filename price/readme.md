# 💰 Smart Pricing Agent - Logic & Architecture

## Overview
The Pricing Agent is not a simple calculator. It is a **Strategic Commercial Bot** that simulates a human Commercial Manager. It calculates the "Winning Price" by balancing **Cost**, **Competition**, **Factory Capacity**, and **Risk**.

---

## 🧠 The "Smart" Pricing Formula

The final bid is calculated using a Multi-Factor Weighted Algorithm:

$$\text{Final Price} = (\text{Base Cost} + \text{Logistics} + \text{Testing}) \times (1 + \text{Dynamic Margin})$$

### 1. Dynamic Margin Logic
The agent starts with a **Base Margin (18%)** and adjusts it in real-time:

| Factor | Logic Source | Impact on Price |
| :--- | :--- | :--- |
| **Competitor Threat** | `competitors.json` | **Drops Margin** if fighting a "Predatory" rival (e.g., V-Flow Tech) or if historical Win Rate < 40%. |
| **Factory Load** | `production_schedule.json` | **Raises Price (+5%)** if factory is full (Scarcity Premium). <br> **Drops Price (-3%)** if lines are idle (Contribution Margin). |
| **Financial Risk** | `commercial_terms` | **Discounts (-2%)** for "100% Advance". <br> **Penalizes (+3%)** for "90 Days Credit" (Cost of Capital). |
| **Project Risk** | `rfp_summary` | **Adds Buffer (+4%)** for keywords like "Metro", "Hazardous", "Hilly Terrain". |
| **Inventory** | `inventory_master.csv` | **Clearance Discount (-5%)** if matching dead stock is found. |

---

## 🏭 Costing Engine Breakdown

### A. Material Costing (Real-Time)
Instead of static prices, the agent calculates the **Live BOM Cost**:
> *Cost = (Copper Wt × LME Rate × Market Factor) + (XLPE Wt × Index) + Process Cost*
* **Market Factor:** Reads `material_master.json` to check if Copper is bullish (1.15x) or bearish.

### B. Testing Charges (Granular)
The agent reads the specific standards (e.g., `IS 7098`) identified by the Technical Agent and builds a "Bill of Tests":
* **Routine Tests:** Charged per drum (e.g., High Voltage).
* **Type Tests:** Charged once per lot (e.g., Impulse Test).
* **Source:** `test_master.json`

### C. Logistics Engine
Calculates freight based on **Weight x Distance**:
* **Step 1:** Calculates total cable weight (e.g., 5km x 4.5kg/m = 22.5 Tons).
* **Step 2:** Maps Delivery Location to a Zone (North/South/East/West).
* **Step 3:** Applies LTL (Less-than-Truckload) or FTL rates from `logistic_master.json`.

---

## 📂 Data Flow
1. **Input:** `central_rfp_database.json` (Consumed from Tech/Sales Agents).
2. **Processing:** Matches SKU -> Calculates BOM -> Applies Strategy.
3. **Output:** Generates a detailed **Cost Sheet** and updates the Central DB.
