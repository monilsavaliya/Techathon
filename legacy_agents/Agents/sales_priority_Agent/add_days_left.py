import pandas as pd
from datetime import datetime

CSV_FILE = "rfp_summary.csv"

df = pd.read_csv(CSV_FILE)

# Parse submission deadline
df["Submission_Deadline"] = pd.to_datetime(df["Submission_Deadline"], errors="coerce")

# Today (date only)
today = pd.Timestamp(datetime.now().date())

# Compute days_left
df["days_left"] = (df["Submission_Deadline"] - today).dt.days

# Clamp negatives to 0
df["days_left"] = df["days_left"].apply(lambda x: max(0, int(x)) if pd.notna(x) else 0)

df.to_csv(CSV_FILE, index=False)

print("✔ days_left column added successfully")
