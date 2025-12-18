import pandas as pd

# ============================================================
# LOAD CSV
# ============================================================

df = pd.read_csv("rfp_top1_sku_technical_breakdown.csv")

# Sort properly
df = df.sort_values(by=["lot_id", "sku_id"])

# ============================================================
# BUILD CUSTOM HTML (GROUPED BY LOT)
# ============================================================

html_parts = []

html_parts.append("""
<html>
<head>
<style>
body {
    font-family: Arial, sans-serif;
    background-color: #f8f9fa;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 30px;
}

th {
    background-color: #2c3e50;
    color: white;
    padding: 8px;
    text-align: left;
}

td {
    padding: 8px;
    border-bottom: 1px solid #ddd;
}

.spec-row:nth-child(even) {
    background-color: #eef3f7;
}

.lot-header {
    background-color: #34495e;
    color: white;
    font-weight: bold;
    padding: 10px;
    font-size: 15px;
}

.score {
    font-weight: bold;
    text-align: center;
}

</style>
</head>
<body>

<h2 style="text-align:center;">
Technical Compliance Breakdown (Top SKU per RFP Product)
</h2>
""")

# Group by lot
for (lot_id, sku_id), group in df.groupby(["lot_id", "sku_id"]):

    html_parts.append(f"""
    <div class="lot-header">
        RFP Lot: {lot_id} &nbsp; | &nbsp; Selected SKU: {sku_id}
    </div>

    <table>
        <tr>
            <th>Specification</th>
            <th>RFP Requirement</th>
            <th>SKU Specification</th>
            <th>Score</th>
        </tr>
    """)

    for _, row in group.iterrows():
        html_parts.append(f"""
        <tr class="spec-row">
            <td>{row['spec_name']}</td>
            <td>{row['rfp_value']}</td>
            <td>{row['sku_value']}</td>
            <td class="score">{row['spec_score']:.2f}</td>
        </tr>
        """)

    html_parts.append("</table>")

html_parts.append("""
</body>
</html>
""")

# ============================================================
# SAVE HTML
# ============================================================

output_file = "rfp_technical_breakdown_grouped.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("".join(html_parts))

print(f"✔ Improved readable HTML generated: {output_file}")

