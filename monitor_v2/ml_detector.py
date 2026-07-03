from __future__ import annotations
import pandas as pd


def detectar_isolation_forest(df: pd.DataFrame) -> pd.DataFrame:
    """Detector bônus opcional.

    Retorna uma cópia do dataframe com coluna `ml_anomalia`.
    Só roda se scikit-learn estiver instalado e houver colunas numéricas suficientes.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except Exception:
        out = df.copy()
        out["ml_anomalia"] = False
        return out

    numeric = df.select_dtypes(include="number").dropna(axis=1, how="all")
    if numeric.empty or len(numeric) < 20:
        out = df.copy()
        out["ml_anomalia"] = False
        return out

    numeric = numeric.fillna(numeric.median(numeric_only=True))
    model = IsolationForest(contamination=0.05, random_state=42)
    preds = model.fit_predict(numeric)

    out = df.copy()
    out["ml_anomalia"] = preds == -1
    return out
