import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import heapq

# ============================================================
# 1. TRAINING PHASE – MODEL TO PREDICT P(WIN)
# ============================================================

# Historical training data
# Must contain: rfp_id, product_score, relationship_score, won_flag
train_df = pd.read_csv("rfp_win_history.csv")

feature_cols = ["product_score", "relationship_score"]

X = train_df[feature_cols]
y = train_df["won_flag"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

win_model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

win_model.fit(X_train, y_train)

# ============================================================
# 2. INFERENCE PHASE – CURRENT RFPS (YOUR CSV)
# ============================================================

# Must contain:
# rfp_id, product_score, relationship_score, days_left
rfps = pd.read_csv("rfp_summary.csv")

X_new = rfps[feature_cols]
rfps["p_win"] = win_model.predict_proba(X_new)[:, 1]

# ============================================================
# 3. URGENCY FUNCTION
# ============================================================

D_MAX = 90

def urgency_score(days_left, d_max=D_MAX):
    d = max(0, min(days_left, d_max))
    return 1.0 - (d / d_max)

# ============================================================
# 4. FINAL PRIORITY SCORE
# ============================================================

def compute_priority(row, gamma=0.5):
    urg = urgency_score(row["days_left"])
    return row["p_win"] * (1.0 + gamma * urg)

rfps["PriorityScore"] = rfps.apply(compute_priority, axis=1)

# ============================================================
# 5. BUILD PRIORITY QUEUE (MAX-HEAP)
# ============================================================

pq = []

for _, row in rfps.iterrows():
    heapq.heappush(
        pq,
        (-row["PriorityScore"], row["rfp_id"])
    )

# ============================================================
# 6. WRITE QUEUE TO TXT FILE
# ============================================================

output_txt = "rfp_priority_queue.txt"

with open(output_txt, "w", encoding="utf-8") as f:
    rank = 1
    while pq:
        neg_score, rfp_id = heapq.heappop(pq)
        f.write(f"{rank}. {rfp_id}\n")
        rank += 1

print(f"✔ Priority queue written successfully to: {output_txt}")
