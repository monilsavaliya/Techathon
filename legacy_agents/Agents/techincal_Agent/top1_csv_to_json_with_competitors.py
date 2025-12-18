import pandas as pd
import json

# ============================================================
# LOAD INPUT FILES
# ============================================================

CSV_FILE = "rfp_top1_sku_technical_breakdown.csv"
PRODUCT_MASTER_FILE = "product_master_enriched.json"
COMPETITORS_FILE = "competitors.json"

df = pd.read_csv(CSV_FILE)

with open(PRODUCT_MASTER_FILE, "r", encoding="utf-8") as f:
    product_master = json.load(f)

with open(COMPETITORS_FILE, "r", encoding="utf-8") as f:
    competitors_data = json.load(f)

# Normalize product master
inventory_map = {
    p["product_id"]: p
    for p in product_master
    if isinstance(p, dict) and "product_id" in p
}

# ============================================================
# LIGHTWEIGHT COMPETITOR LOOKUP
# ============================================================

def find_competitors_for_sku(sku_id):
    result = []
    for comp in competitors_data:
        if sku_id in comp.get("colliding_internal_skus", []):
            result.append({
                "competitor_id": comp.get("competitor_id"),
                "name": comp.get("name")
            })
    return result

# ============================================================
# BUILD FINAL JSON STRUCTURE
# ============================================================

final_output = []

for (lot_id, sku_id), group in df.groupby(["lot_id", "sku_id"]):

    product = inventory_map.get(sku_id, {})

    specs = []
    for _, row in group.iterrows():
        specs.append({
            "spec_name": row["spec_name"],
            "rfp_value": row["rfp_value"],
            "sku_value": row["sku_value"],
            "spec_score": float(row["spec_score"])
        })

    final_output.append({
        "lot_id": lot_id,
        "selected_sku": {
            "sku_id": sku_id,
            "sku_name": product.get("product_name"),
            "technical_breakdown": specs
        },
        "competitors": find_competitors_for_sku(sku_id)
    })

# ============================================================
# SAVE OUTPUT JSON
# ============================================================

OUTPUT_FILE = "rfp_top1_with_competitors.json"

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_output, f, indent=2)

print(f"✔ Lightweight JSON generated successfully: {OUTPUT_FILE}")
