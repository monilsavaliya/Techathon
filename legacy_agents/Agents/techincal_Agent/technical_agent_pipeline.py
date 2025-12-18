# ============================================================
# TECHNICAL AGENT – MASTER PIPELINE
# ============================================================

# This script runs the full technical agent flow:
# 1) Top-3 SKU matching (CSV)
# 2) Top-1 SKU technical breakdown (CSV)
# 3) Top-1 HTML report
# 4) Top-3 HTML report
# 5) JSON output with competitors (lightweight)

# ❗ NO LOGIC MODIFIED — ONLY ORCHESTRATION
# ============================================================

# ============================================================
# COMMON IMPORTS
# ============================================================

import json
import pandas as pd
import re

# ============================================================
# STEP 1: TOP-3 SKU MATCHING → CSV
# ============================================================

print("\n[1/5] Generating Top-3 SKU matches...")

exec(open("top3_sku_matcher.py", encoding="utf-8").read())

# Output:
# → rfp_top3_oem_matches.csv

# ============================================================
# STEP 2: TOP-1 SKU TECHNICAL BREAKDOWN → CSV
# ============================================================

print("\n[2/5] Generating Top-1 SKU technical breakdown...")

exec(open("top1_technical_breakdown_csv.py", encoding="utf-8").read())

# Output:
# → rfp_top1_sku_technical_breakdown.csv

# ============================================================
# STEP 3: TOP-1 HTML TECHNICAL REPORT
# ============================================================

print("\n[3/5] Generating Top-1 HTML report...")

exec(open("top1_html_generator.py", encoding="utf-8").read())

# Output:
# → rfp_technical_breakdown_grouped.html

# ============================================================
# STEP 4: TOP-3 HTML TECHNICAL REPORT
# ============================================================

print("\n[4/5] Generating Top-3 HTML report...")

exec(open("top3_html_generator.py", encoding="utf-8").read())

# Output:
# → rfp_top3_technical_breakdown.html

# ============================================================
# STEP 5: CSV → JSON + COMPETITORS (LIGHTWEIGHT)
# ============================================================

print("\n[5/5] Generating JSON output with competitors...")

exec(open("top1_csv_to_json_with_competitors.py", encoding="utf-8").read())

# Output:
# → rfp_top1_with_competitors.json

# ============================================================
# DONE
# ============================================================

print("\n✔ Technical Agent Pipeline completed successfully.")
