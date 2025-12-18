import json
import pandas as pd
import re

# ============================================================
# 1. LOAD RFP
# ============================================================

with open("rfp.json", "r", encoding="utf-8") as f:
    rfp_data = json.load(f)

rfp_items = rfp_data["sales_agent_output"]["line_items_extracted"]

# ============================================================
# 2. LOAD PRODUCT MASTER (ROBUST)
# ============================================================

with open("product_master_enriched.json", "r", encoding="utf-8") as f:
    inventory_data = json.load(f)

if isinstance(inventory_data, list):
    inventory = inventory_data
elif isinstance(inventory_data, dict):
    inventory = (
        inventory_data.get("products")
        or inventory_data.get("items")
        or inventory_data.get("data")
        or list(inventory_data.values())
    )
else:
    inventory = []

# ============================================================
# 3. NORMALIZATION HELPERS
# ============================================================

MATERIAL_MAP = {
    "aluminum": "aluminium",
    "aluminium": "aluminium",
    "al": "aluminium",
    "copper": "copper",
    "cu": "copper"
}

def normalize(val):
    if val is None:
        return None
    return str(val).strip().lower()

def normalize_material(val):
    return MATERIAL_MAP.get(normalize(val), normalize(val))

def is_not_specified(val):
    return val is None or val == "NOT SPECIFIED"

def normalize_standard(s):
    if not s:
        return None

    s = normalize(s)

    # remove year info and brackets
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r":\d{4}", "", s)

    # normalize part notation
    s = s.replace("part-", "part ")
    s = s.replace("part i", "part 1")

    s = re.sub(r"\s+", " ", s).strip()
    return s

# ============================================================
# 4. MATCHING FUNCTIONS
# ============================================================

def match_value(rfp_val, inv_val):
    if is_not_specified(rfp_val):
        return 1.0
    return 1.0 if normalize(rfp_val) == normalize(inv_val) else 0.0

def match_material(rfp_val, inv_val):
    if is_not_specified(rfp_val):
        return 1.0
    return 1.0 if normalize_material(rfp_val) == normalize_material(inv_val) else 0.0

def match_cross_section(rfp_val, inv_val):
    if is_not_specified(rfp_val):
        return 1.0
    try:
        r = float(rfp_val)
        i = float(inv_val)
    except (TypeError, ValueError):
        return 0.0

    score = 1.0 - abs(i - r) / r
    return max(0.0, round(score, 3))

def match_armoured(rfp_val, inv_specs):
    # NOT SPECIFIED → FULL POINTS
    if is_not_specified(rfp_val):
        return 1.0

    if normalize(rfp_val) == "armoured":
        return 1.0 if inv_specs.get("armour_type") else 0.0

    return 0.0

# ============================================================
# 5. STANDARDS — FINAL CORRECT LOGIC
# ============================================================

def match_standards(rfp_list, inv_list):
    """
    - Total standards weight = 1.0
    - Divided equally among all RFP standards
    - Each standard checked independently
    - 'ISI marked' always scores its own share only
    """

    if not rfp_list:
        return 1.0

    rfp_norm = [normalize_standard(s) for s in rfp_list]
    inv_norm = set(normalize_standard(s) for s in (inv_list or []))

    total = len(rfp_norm)
    if total == 0:
        return 1.0

    per_std_weight = 1.0 / total
    score = 0.0

    for std in rfp_norm:
        if std == "isi marked":
            score += per_std_weight
        elif std in inv_norm:
            score += per_std_weight
        # else: 0 contribution

    return round(score, 3)

# ============================================================
# 6. FINAL MATCH PERCENTAGE (7 LOGICAL SPECS)
# ============================================================

def compute_match_percentage(rfp_attrs, inv_specs):
    scores = [
        match_value(rfp_attrs.get("voltage_grade"), inv_specs.get("voltage_grade")),
        match_value(rfp_attrs.get("core_count"), inv_specs.get("core_count")),
        match_cross_section(rfp_attrs.get("cross_section_sqmm"), inv_specs.get("cross_section_sqmm")),
        match_material(rfp_attrs.get("conductor_material"), inv_specs.get("conductor_material")),
        match_value(rfp_attrs.get("insulation_type"), inv_specs.get("insulation")),
        match_armoured(rfp_attrs.get("sheath_type"), inv_specs),
        match_standards(rfp_attrs.get("standards"), inv_specs.get("standards"))
    ]

    return round((sum(scores) / len(scores)) * 100, 2)

# ============================================================
# 7. MATCH EACH RFP PRODUCT → TOP 3 SKUS
# ============================================================

rows = []

for item in rfp_items:
    lot_id = item["lot_id"]
    raw_desc = item["raw_description"]
    rfp_attrs = item["technical_attributes"]

    matches = []

    for sku in inventory:
        if not isinstance(sku, dict):
            continue

        inv_specs = sku.get("technical_specs")
        if not inv_specs:
            continue

        score = compute_match_percentage(rfp_attrs, inv_specs)

        matches.append({
            "sku_id": sku.get("product_id", "UNKNOWN"),
            "sku_name": sku.get("product_name", "UNKNOWN"),
            "match_percentage": score
        })

    top_3 = sorted(matches, key=lambda x: x["match_percentage"], reverse=True)[:3]

    for rank, m in enumerate(top_3, start=1):
        rows.append({
            "lot_id": lot_id,
            "rfp_description": raw_desc,
            "rank": rank,
            "sku_id": m["sku_id"],
            "sku_name": m["sku_name"],
            "match_percentage": m["match_percentage"]
        })

# ============================================================
# 8. SAVE OUTPUT
# ============================================================

output_file = "rfp_top3_oem_matches.csv"
pd.DataFrame(rows).to_csv(output_file, index=False)

print(f"✔ Technical matching completed successfully: {output_file}")
