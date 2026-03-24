import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
from pathlib import Path

# Load dataset
BASE_DIR = Path(__file__).resolve().parent
df = pd.read_csv(BASE_DIR / "data.csv")

# Convert categorical → numeric
df = pd.get_dummies(df, columns=["type"])

# Split features & target
X = df.drop("settlement", axis=1)
y = df["settlement"]

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = RandomForestRegressor()
model.fit(X_train, y_train)

# Evaluate
preds = model.predict(X_test)
mae = mean_absolute_error(y_test, preds)

print("Model trained!")
print("MAE:", mae)

# Save model
joblib.dump(model, BASE_DIR / "model.pkl")

print("Model saved as model.pkl")