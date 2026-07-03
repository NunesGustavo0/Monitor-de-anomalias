from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

OUTPUT = Path("outputs")
OUTPUT.mkdir(exist_ok=True)


def salvar_auditoria(alertas: list[dict]) -> None:
    if not alertas:
        return

    registros = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for alerta in alertas:
        item = alerta.copy()
        item["data_auditoria"] = agora
        item["evento"] = "ALERTA_GERADO"
        registros.append(item)

    path = OUTPUT / "auditoria_alertas.csv"
    novo = pd.DataFrame(registros)

    if path.exists():
        antigo = pd.read_csv(path)
        novo = pd.concat([antigo, novo], ignore_index=True)

    novo.to_csv(path, index=False, encoding="utf-8-sig")
