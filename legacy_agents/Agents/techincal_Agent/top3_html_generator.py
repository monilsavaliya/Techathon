import json
import pandas as pd
import re

# ============================================================
# LOAD INPUTS
# ============================================================

top3_df = pd.read_csv("rfp_top3_oem_matches.csv")

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
# SCORING (EXPLANATION MODE)
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
        return max(0.0, round(1 - abs(float(sku) - float(rfp)) / float(rfp), 3))
    except:
        return 0.0

def score_standards(rfp_list, sku_list):
    if not rfp_list:
        return 1.0
    rfp_norm = set(normalize_standard(x) for x in rfp_list)
    sku_norm = set(normalize_standard(x) for x in (sku_list or []))
    return 1.0 if rfp_norm & sku_norm else 0.0

# ============================================================
# BUILD HTML
# ============================================================

html = ["""
<html>
<head>
<style>
body { font-family: Arial, sans-serif; background-color: #f6f7f9; }
.lot-header {
    background-color: #2c3e50;
    color: white;
    padding: 12px;
    font-size: 16px;
    margin-top: 30px;
}
.sku-header {
    background-color: #ecf0f1;
    padding: 10px;
    font-weight: bold;
    border-left: 5px solid #2980b9;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}
th {
    background-color: #34495e;
    color: white;
    padding: 8px;
    text-align: left;
}
td {
    padding: 8px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) {
    background-color: #f2f6f9;
}
.score {
    text-align: center;
    font-weight: bold;
}
</style>
</head>
<body>

<h2 style="text-align:center;">
Top 3 Technical Match – Detailed Comparison
</h2>
"""]

# ============================================================
# GENERATE CONTENT
# ============================================================

for lot_id, lot_group in top3_df.groupby("lot_id"):

    html.append(f"""
    <div class="lot-header">
        RFP Lot: {lot_id}
    </div>
    """)

    for _, row in lot_group.sort_values("rank").iterrows():
        sku_id = row["sku_id"]
        rank = int(row["rank"])
        match_pct = row["match_percentage"]

        sku = inventory_map.get(sku_id, {})
        sku_specs = sku.get("technical_specs", {})
        rfp_specs = rfp_items[lot_id]

        html.append(f"""
        <div class="sku-header">
            Rank {rank} | SKU: {sku_id} | Match: {match_pct:.2f}%
        </div>

        <table>
            <tr>
                <th>Specification</th>
                <th>RFP Requirement</th>
                <th>SKU Specification</th>
                <th>Score</th>
            </tr>
        """)

        rows = [
            ("voltage_grade", rfp_specs.get("voltage_grade"), sku_specs.get("voltage_grade"),
             score_value(rfp_specs.get("voltage_grade"), sku_specs.get("voltage_grade"))),

            ("core_count", rfp_specs.get("core_count"), sku_specs.get("core_count"),
             score_value(rfp_specs.get("core_count"), sku_specs.get("core_count"))),

            ("cross_section_sqmm", rfp_specs.get("cross_section_sqmm"), sku_specs.get("cross_section_sqmm"),
             score_cross_section(rfp_specs.get("cross_section_sqmm"), sku_specs.get("cross_section_sqmm"))),

            ("conductor_material", rfp_specs.get("conductor_material"), sku_specs.get("conductor_material"),
             score_material(rfp_specs.get("conductor_material"), sku_specs.get("conductor_material"))),

            ("insulation_type", rfp_specs.get("insulation_type"), sku_specs.get("insulation"),
             score_value(rfp_specs.get("insulation_type"), sku_specs.get("insulation"))),

            ("sheath_type", rfp_specs.get("sheath_type"),
             "armour_type present" if sku_specs.get("armour_type") else "not armoured",
             1.0 if sku_specs.get("armour_type") else 0.0),

            ("standards",
             ", ".join(rfp_specs.get("standards", [])),
             ", ".join(sku_specs.get("standards", [])),
             score_standards(rfp_specs.get("standards"), sku_specs.get("standards")))
        ]

        for spec, rfp_v, sku_v, sc in rows:
            html.append(f"""
            <tr>
                <td>{spec}</td>
                <td>{rfp_v}</td>
                <td>{sku_v}</td>
                <td class="score">{sc:.2f}</td>
            </tr>
            """)

        html.append("</table>")

html.append("</body></html>")

# ============================================================
# SAVE FILE
# ============================================================

out_file = "rfp_top3_technical_breakdown.html"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("".join(html))

print(f"✔ Top-3 technical comparison HTML generated: {out_file}")
