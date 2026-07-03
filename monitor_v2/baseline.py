from __future__ import annotations
import pandas as pd


def calcular_baseline(df: pd.DataFrame) -> dict:
    """Baseline estatístico para taxa de falha por jig.

    Usa média + 3 desvios-padrão da taxa de falha dos jigs na janela.
    O limite mínimo evita que uma janela muito perfeita gere limite zero.
    """
    if df.empty or "jig_id" not in df.columns or "result" not in df.columns:
        return {"media": 0.0, "desvio": 0.0, "limite": 0.08}

    jig = (
        df.groupby("jig_id")
        .agg(
            total=("result", "size"),
            falhas=("result", lambda x: (x.astype(str).str.upper() == "FAIL").sum()),
        )
        .reset_index()
    )

    if jig.empty:
        return {"media": 0.0, "desvio": 0.0, "limite": 0.08}

    jig["taxa"] = jig["falhas"] / jig["total"].replace(0, pd.NA)
    media = float(jig["taxa"].mean() or 0)
    desvio = float(jig["taxa"].std() or 0)
    limite = media + (3 * desvio)

    # Limite mínimo e máximo para evitar valores irreais em janelas pequenas.
    limite = max(limite, 0.05)
    limite = min(limite, 0.50)

    return {"media": media, "desvio": desvio, "limite": limite}
