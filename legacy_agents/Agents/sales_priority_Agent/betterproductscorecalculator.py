import pandas as pd
import re
import os

# ---------- similarity utils ----------
def tokenize(text: str):
    if pd.isna(text):
        return set()
    return set(re.findall(r"\w+", str(text).lower()))

def similarity(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def similarity_to_score(sim: float) -> float:
    if sim >= 0.65:
        return 1.0
    elif sim >= 0.40:
        return 0.7
    elif sim >= 0.20:
        return 0.4
    else:
        return 0.0

# ---------- helpers ----------
def split_products(cell: str):
    if pd.isna(cell):
        return []
    return [p.strip() for p in str(cell).split(",") if p.strip()]

def find_inventory_name_column(inv_df):
    for c in ["product_name", "name", "description"]:
        if c in inv_df.columns:
            return c
    return inv_df.columns[0]

# ---------- main logic ----------
def update_product_score(
    rfp_csv="rfp_summary.csv",
    inventory_csv="factory_inventory_master.csv",
    output_csv=None,
    products_col="Product_Names"
):
    rfp_df = pd.read_csv(rfp_csv, dtype=str)
    inv_df = pd.read_csv(inventory_csv, dtype=str)

    inv_name_col = find_inventory_name_column(inv_df)
    inventory_names = inv_df[inv_name_col].fillna("").tolist()

    product_scores = []

    for _, row in rfp_df.iterrows():
        products = split_products(row.get(products_col, ""))

        scores = []
        for p in products:
            sims = [similarity(p, inv) for inv in inventory_names]
            best_sim = max(sims) if sims else 0.0
            scores.append(similarity_to_score(best_sim))

        final_score = sum(scores) / len(scores) if scores else 0.0
        product_scores.append(round(final_score, 3))

    rfp_df["product_score"] = product_scores

    out_path = output_csv if output_csv else rfp_csv
    rfp_df.to_csv(out_path, index=False)

    # ✅ Clear confirmation message
    print(f"✔ RFP CSV updated successfully: {out_path}")

# ---------- usage ----------
if __name__ == "__main__":
    update_product_score(
        rfp_csv="rfp_summary.csv",
        inventory_csv="factory_inventory_master (2).csv"
    )
