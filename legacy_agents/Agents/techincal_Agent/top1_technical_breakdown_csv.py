import json
import pandas as pd
import re

# ============================================================
# LOAD INPUTS
# ============================================================

rfp_df = pd.read_csv("rfp_top3_oem_matches.csv")

# 🔒 KEEP ONLY TOP-1 SKU PER RFP PRODUCT
rfp_df = rfp_df[rfp_df["rank"] == 1]

with open("rfp.json", "r", encoding="utf-8") as f:
    rfp_data = json.load(f)

with open("product_master_enriched.json", "r", encoding="utf-8") as f:
    inventory_data = json.load(f)

# inventory normalization
if isinstance(inventory_data, list):
    inventory = inventory_data
else:
    inventory = (
        inventory_data.get("products")
        or inventory_data.get("items")
        or inventory_data.get("data")
        or list(inventory_data.values())
    )

inventory_map = {
    sku["product_id"]: sku
    for sku in inventory
    if isinstance(sku, dict) and "product_id" in sku
}

rfp_items = {
    item["lot_id"]: item["technical_attributes"]
    for item in rfp_data["sales_agent_output"]["line_items_extracted"]
}

# ============================================================
# NORMALIZATION HELPERS
# ============================================================

MATERIAL_MAP = {
    "aluminum": "aluminium",
    "aluminium": "aluminium",
    "al": "aluminium",
    "copper": "copper",
    "cu": "copper"
}

def normalize(v):
    if v is None:
        return None
    return str(v).strip().lower()

def normalize_material(v):
    return MATERIAL_MAP.get(normalize(v), normalize(v))

def is_not_specified(v):
    return v is None or v == "NOT SPECIFIED"

def normalize_standard(s):
    if not s:
        return None
    s = normalize(s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r":\d{4}", "", s)
    s = s.replace("part-", "part ")
    s = s.replace("part i", "part 1")
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ============================================================
# PER-SPEC SCORING (FINAL LOGIC)
# ============================================================

def score_value(rfp, sku):
    if is_not_specified(rfp):
        return 1.0
    return 1.0 if normalize(rfp) == normalize(sku) else 0.0

def score_material(rfp, sku):
    if is_not_specified(rfp):
        return 1.0
    return 1.0 if normalize_material(rfp) == normalize_material(sku) else 0.0

def score_cross_section(rfp, sku):
    if is_not_specified(rfp):
        return 1.0
    try:
        return max(
            0.0,
            round(1 - abs(float(sku) - float(rfp)) / float(rfp), 3)
        )
    except:
        return 0.0

def score_armoured(rfp_sheath, sku_specs):
    # 🔥 HARD FIX
    if is_not_specified(rfp_sheath):
        return 1.0

    if normalize(rfp_sheath) == "armoured":
        return 1.0 if sku_specs.get("armour_type") else 0.0

    return 0.0

def score_standards(rfp_list, sku_list):
    if not rfp_list:
        return 1.0

    rfp_norm = [normalize_standard(s) for s in rfp_list]
    sku_norm = set(normalize_standard(s) for s in (sku_list or []))

    total = len(rfp_norm)
    if total == 0:
        return 1.0

    per_std_weight = 1.0 / total
    score = 0.0

    for std in rfp_norm:
        if std == "isi marked":
            score += per_std_weight
        elif std in sku_norm:
            score += per_std_weight

    return round(score, 3)

# ============================================================
# BUILD TECHNICAL BREAKDOWN (TOP-1 ONLY)
# ============================================================

rows = []

for _, row in rfp_df.iterrows():
    lot_id = row["lot_id"]
    sku_id = row["sku_id"]

    rfp_specs = rfp_items[lot_id]
    sku = inventory_map.get(sku_id, {})
    sku_specs = sku.get("technical_specs", {})

    rows.extend([
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "voltage_grade",
            "rfp_value": rfp_specs.get("voltage_grade"),
            "sku_value": sku_specs.get("voltage_grade"),
            "spec_score": score_value(
                rfp_specs.get("voltage_grade"),
                sku_specs.get("voltage_grade")
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "core_count",
            "rfp_value": rfp_specs.get("core_count"),
            "sku_value": sku_specs.get("core_count"),
            "spec_score": score_value(
                rfp_specs.get("core_count"),
                sku_specs.get("core_count")
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "cross_section_sqmm",
            "rfp_value": rfp_specs.get("cross_section_sqmm"),
            "sku_value": sku_specs.get("cross_section_sqmm"),
            "spec_score": score_cross_section(
                rfp_specs.get("cross_section_sqmm"),
                sku_specs.get("cross_section_sqmm")
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "conductor_material",
            "rfp_value": rfp_specs.get("conductor_material"),
            "sku_value": sku_specs.get("conductor_material"),
            "spec_score": score_material(
                rfp_specs.get("conductor_material"),
                sku_specs.get("conductor_material")
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "insulation_type",
            "rfp_value": rfp_specs.get("insulation_type"),
            "sku_value": sku_specs.get("insulation"),
            "spec_score": score_value(
                rfp_specs.get("insulation_type"),
                sku_specs.get("insulation")
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "sheath_type",
            "rfp_value": rfp_specs.get("sheath_type"),
            "sku_value": "armour_type present" if sku_specs.get("armour_type") else "not armoured",
            "spec_score": score_armoured(
                rfp_specs.get("sheath_type"),
                sku_specs
            )
        },
        {
            "lot_id": lot_id,
            "sku_id": sku_id,
            "spec_name": "standards",
            "rfp_value": ", ".join(rfp_specs.get("standards", [])),
            "sku_value": ", ".join(sku_specs.get("standards", [])),
            "spec_score": score_standards(
                rfp_specs.get("standards"),
                sku_specs.get("standards")
            )
        }
    ])

# ============================================================
# SAVE OUTPUT
# ============================================================

out_file = "rfp_top1_sku_technical_breakdown.csv"
pd.DataFrame(rows).to_csv(out_file, index=False)

print(f"✔ Technical breakdown (TOP-1 only) generated successfully: {out_file}")
