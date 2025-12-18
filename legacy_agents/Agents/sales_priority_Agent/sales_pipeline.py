# ============================================================
# SALES PIPELINE (FINAL, BULLETPROOF)
# ============================================================

# Execution order:
# 1) json_in_csv.py
# 2) betterproductscorecalculator.py
# 3) relationship_score.py
# 4) add_days_left.py
# 5) normalize_columns.py
# 6) predict_and_queue.py   (ML inference only)

# Model training is done separately (manual)
# ============================================================

print("\n[PIPELINE STARTED] Sales → Pricing Agent (Prediction Only)\n")

# ============================================================
# STEP 1: JSON → CSV
# ============================================================

print("[1/6] Converting RFP JSON to CSV...")
exec(open("json_in_csv.py", encoding="utf-8").read())

# Output:
# → rfp_summary.csv

# ============================================================
# STEP 2: PRODUCT SCORE CALCULATION
# ============================================================

print("\n[2/6] Calculating product scores...")
exec(open("betterproductscorecalculator.py", encoding="utf-8").read())

# Output:
# → rfp_summary.csv (product_score added)

# ============================================================
# STEP 3: RELATIONSHIP SCORE
# ============================================================

print("\n[3/6] Adding relationship scores...")
exec(open("relationship_score.py", encoding="utf-8").read())

# Output:
# → rfp_summary.csv (relationship_score added)

# ============================================================
# STEP 4: DAYS LEFT (URGENCY)
# ============================================================

print("\n[4/6] Computing days_left from submission deadlines...")
exec(open("add_days_left.py", encoding="utf-8").read())

# Output:
# → rfp_summary.csv (days_left added)

# ============================================================
# STEP 5: NORMALIZE COLUMN NAMES
# ============================================================

print("\n[5/6] Normalizing column names...")
exec(open("normalize_columns.py", encoding="utf-8").read())

# Output:
# → rfp_summary.csv (lowercase, safe schema)

# ============================================================
# STEP 6: ML PREDICTION + PRIORITY QUEUE
# ============================================================

print("\n[6/6] Running ML prediction and building priority queue...")
exec(open("predict_and_queue.py", encoding="utf-8").read())

# Output:
# → rfp_priority_queue.txt

# ============================================================
# DONE
# ============================================================

print("\n✔ Sales → Pricing pipeline completed successfully.")
