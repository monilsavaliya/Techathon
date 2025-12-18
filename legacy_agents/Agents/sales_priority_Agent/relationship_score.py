import pandas as pd

# ============================================================
# COMPANY → RELATIONSHIP SCORE MAP
# ============================================================

company_relationship_scores = {
    "NTPC Limited": 0.85,
    "Maharashtra State Electricity Distribution Co Ltd": 0.78,
    "Indian Railways": 0.90,
    "Delhi Metro Rail Corporation": 0.88,
    "Bharat Heavy Electricals Limited": 0.82,
    "Oil and Natural Gas Corporation": 0.80,
    "Larsen & Toubro Limited": 0.92,
    "ITI Limited": 0.75
}

# ============================================================
# FUNCTION
# ============================================================

def update_relationship_score(
    rfp_csv="rfp_summary.csv",
    company_score_map=None,
    output_csv=None,
    company_col="Company_Name",
    default_score=0.7
):
    if company_score_map is None:
        company_score_map = {}

    # Normalize map for safety (case + whitespace)
    company_score_map = {
        k.strip().lower(): v for k, v in company_score_map.items()
    }

    # Load CSV
    df = pd.read_csv(rfp_csv, dtype=str)

    relationship_scores = []

    for _, row in df.iterrows():
        company = str(row.get(company_col, "")).strip().lower()
        score = company_score_map.get(company, default_score)
        relationship_scores.append(float(score))

    # Add / update column
    df["relationship_score"] = relationship_scores

    # Save
    out_path = output_csv if output_csv else rfp_csv
    df.to_csv(out_path, index=False)

    print(f"✔ Relationship scores updated successfully: {out_path}")

# ============================================================
# AUTO-RUN
# ============================================================

update_relationship_score(
    rfp_csv="rfp_summary.csv",
    company_score_map=company_relationship_scores
)


