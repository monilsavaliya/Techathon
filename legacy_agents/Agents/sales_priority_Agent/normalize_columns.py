import pandas as pd

CSV_FILE = "rfp_summary.csv"

df = pd.read_csv(CSV_FILE)

# Normalize column names
df.columns = [c.strip().lower() for c in df.columns]

df.to_csv(CSV_FILE, index=False)

print("✔ Column names normalized successfully")
