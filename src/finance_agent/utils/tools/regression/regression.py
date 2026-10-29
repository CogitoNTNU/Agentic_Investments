import numpy as np
import pandas as pd
from io import StringIO
from langchain.tools import tool
from sklearn.linear_model import LinearRegression 
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

@tool 
def regression(data_json: str, selected_features: list[str]) -> str: 
    """Train and evaluate a stock_return regression model.
    
    data_json must contain historical observations and a future_return_3m target column. selected_features must contain apporved numeric feature names.
    """

    try:
        data = pd.read_json(StringIO(data_json), orient="records")
    except (ValueError, TypeError) as exc:
        return f"Invalid regression dataset: {exc}"
    target = "future_return_3m"

    if target not in data.columns: 
        return f"Missing target column: {target}"

    # Never allow the AI to introduce arbitrary columns.
    allowed = {
        "revenue_growth", "gross_margin", "operating_margin", 
        "net_margin", "return_on_equity", "debt_to_equity",
        "current_ratio", "free_cash_flow", "free_cash_flow_margin", "earnings_growth"
    }

    features = [
        f for f in selected_features 
        if f in allowed and f in data.columns 
    ]

    if not features: 
        return "No selected features are available in the dataset."

    usable_features = [
        feature for feature in features if data[feature].notna().any()
    ]
    if not usable_features:
        return "Selected features contain no usable historical values."
    features = usable_features

    # Preserve chronology: never randomly shuffle financial observations.

    if "date" not in data.columns:
        return "Missing date column."

    data = data.sort_values("date").dropna(subset=[target])

    if len(data) < 30 : 
        return "Not enough historical observations to evaluate the model."

    split = int(len(data) * 0.8)
    train = data.iloc[:split]
    test = data.iloc[split:]

    if train.empty or test.empty: 
        return "Insufficient data for chronological split."

    X_train = train[features].replace([np.inf, -np.inf], np.nan)
    X_test = test[features].replace([np.inf, -np.inf], np.nan)
    y_train = train[target]
    y_test = test[target]

    model = make_pipeline(
        SimpleImputer(strategy="median"), 
        StandardScaler(),
        LinearRegression()
    )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    return (
        f"Features: {features}\n"
        f"Test MAE: {mean_absolute_error(y_test, predictions):.4f}\n"
        f"Test R2: {r2_score(y_test, predictions):.4f}\n"
        f"Test observations: {len(test)}"
    )