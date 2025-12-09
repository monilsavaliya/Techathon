import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

# Load historical labelled data
df = pd.read_csv("orders_history.csv")

# Features for ML (do NOT include profit)
numeric_features = ["relationship_score", "deadline_score", "feasibility_score", "risk_score"]
categorical_features = ["client_type"]

X = df[numeric_features + categorical_features]
y = df["won"]   # 1 if order won, 0 if lost

# Preprocess: encode client_type
preprocessor = ColumnTransformer(
    transformers=[
        ("num", "passthrough", numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
    ]
)

# Build model pipeline
model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000))
    ]
)

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model (silent)
model.fit(X_train, y_train)
