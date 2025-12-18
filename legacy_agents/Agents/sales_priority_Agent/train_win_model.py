import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

# Load training data
df = pd.read_csv("rfp_win_history.csv")

X = df[["product_score", "relationship_score"]]
y = df["won_flag"]

# Train model
model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X, y)

# Save model
joblib.dump(model, "win_model.joblib")

print("✔ Model trained and saved as win_model.joblib")
