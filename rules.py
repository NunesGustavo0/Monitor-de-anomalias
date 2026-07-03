from __future__ import annotations
import pandas as pd
from baseline import calcular_baseline


def _safe_str(value) -> str:
    if pd.isna(value):
        return "Não informado"
    return str(value)


def detectar_anomalias(df: pd.DataFrame) -> list[dict]:
    """Detecta anomalias sistemáticas na janela atual.

    Regras implementadas:
    - Taxa de falha alta por jig usando baseline média + 3 desvios;
    - PPM alto por firmware;
    - MAC repetido em seriais diferentes;
    - Drift/outlier sistemático de cycle time por jig.
    """
    alertas: list[dict] = []
    if df.empty:
        return alertas

    df = df.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        inicio = df["timestamp"].min()
        fim = df["timestamp"].max()
        janela_txt = f"{inicio} até {fim}"
    else:
        janela_txt = "janela atual"

    baseline = calcular_baseline(df)
    limite_taxa = baseline["limite"]

    # 1) Taxa de falha por jig: exige volume mínimo para não alertar glitch isolado.
    if {"jig_id", "result"}.issubset(df.columns):
        jig = (
            df.groupby("jig_id")
            .agg(
                tentativas=("result", "size"),
                falhas=("result", lambda x: (x.astype(str).str.upper() == "FAIL").sum()),
            )
            .reset_index()
        )
        jig["taxa_falha"] = jig["falhas"] / jig["tentativas"].replace(0, pd.NA)

        for _, row in jig.iterrows():
            if row["tentativas"] >= 20 and row["falhas"] >= 3 and row["taxa_falha"] >= limite_taxa:
                severidade = "Crítica" if row["taxa_falha"] >= 0.20 else "Alta"
                alertas.append({
                    "tipo": "Falha alta por Jig",
                    "onde": _safe_str(row["jig_id"]),
                    "severidade": severidade,
                    "evidencia": f"Taxa de falha {row['taxa_falha']:.2%} acima do limite {limite_taxa:.2%}",
                    "acao": "Parar o Jig e abrir manutenção" if severidade == "Crítica" else "Verificar Jig e acompanhar próxima janela",
                    "janela": janela_txt,
                    "baseline": f"média={baseline['media']:.2%}; desvio={baseline['desvio']:.2%}; limite={limite_taxa:.2%}",
                })

    # 2) PPM por firmware.
    if {"firmware_version", "result"}.issubset(df.columns):
        fw = (
            df.groupby("firmware_version")
            .agg(
                tentativas=("result", "size"),
                falhas=("result", lambda x: (x.astype(str).str.upper() == "FAIL").sum()),
            )
            .reset_index()
        )
        fw["ppm"] = (fw["falhas"] / fw["tentativas"].replace(0, pd.NA)) * 1_000_000

        for _, row in fw.iterrows():
            # Exige volume mínimo e mais de uma falha para reduzir falso alarme.
            if row["tentativas"] >= 30 and row["falhas"] >= 2 and row["ppm"] >= 50_000:
                severidade = "Crítica" if row["ppm"] >= 150_000 else "Alta"
                alertas.append({
                    "tipo": "PPM alto por Firmware",
                    "onde": _safe_str(row["firmware_version"]),
                    "severidade": severidade,
                    "evidencia": f"PPM {row['ppm']:.0f} em {int(row['tentativas'])} tentativas",
                    "acao": "Bloquear lote do firmware e investigar",
                    "janela": janela_txt,
                    "baseline": "Limite operacional: PPM >= 50.000 com volume mínimo de 30 tentativas",
                })

    # 3) MAC repetido em seriais diferentes.
    if {"mac_address", "serial_number"}.issubset(df.columns):
        mac_df = df.dropna(subset=["mac_address", "serial_number"])
        mac = mac_df.groupby("mac_address")["serial_number"].nunique().reset_index(name="seriais")
        mac = mac[mac["seriais"] > 1]

        for _, row in mac.iterrows():
            alertas.append({
                "tipo": "MAC duplicado",
                "onde": _safe_str(row["mac_address"]),
                "severidade": "Crítica",
                "evidencia": f"MAC usado em {int(row['seriais'])} seriais diferentes",
                "acao": "Revisar provisionamento imediatamente",
                "janela": janela_txt,
                "baseline": "Regra fixa: MAC deve ser único por serial",
            })

    # 4) Drift de cycle time por jig.
    if {"jig_id", "total_cycle_s"}.issubset(df.columns):
        valid = df.dropna(subset=["total_cycle_s"])
        if len(valid) >= 30:
            media = valid["total_cycle_s"].mean()
            desvio = valid["total_cycle_s"].std() or 0
            limite_cycle = media + (3 * desvio)
            cyc = valid.groupby("jig_id")["total_cycle_s"].agg(media_jig="mean", tentativas="size").reset_index()
            for _, row in cyc.iterrows():
                if row["tentativas"] >= 10 and row["media_jig"] > limite_cycle:
                    alertas.append({
                        "tipo": "Drift de Cycle Time",
                        "onde": _safe_str(row["jig_id"]),
                        "severidade": "Média",
                        "evidencia": f"Cycle médio {row['media_jig']:.1f}s acima do limite {limite_cycle:.1f}s",
                        "acao": "Verificar gargalo, equipamento e operador na estação",
                        "janela": janela_txt,
                        "baseline": f"média={media:.1f}s; desvio={desvio:.1f}s; limite={limite_cycle:.1f}s",
                    })

    return alertas
