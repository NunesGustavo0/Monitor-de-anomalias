from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

OUTPUT = Path("outputs")
OUTPUT.mkdir(exist_ok=True)


def enviar_para_hitl(alertas: list[dict]) -> None:
    """Envia casos relevantes para revisão humana.

    Regra: severidade Alta ou Crítica precisa de validação humana antes de ação definitiva.
    """
    pendentes = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for alerta in alertas:
        if alerta.get("severidade") in ["Alta", "Crítica"]:
            item = alerta.copy()
            item["status_hitl"] = "Pendente"
            item["data_envio_hitl"] = agora
            item["decisao_humana"] = ""
            item["comentario_humano"] = ""
            pendentes.append(item)

    if not pendentes:
        return

    path = OUTPUT / "hitl_pendentes.csv"
    novo = pd.DataFrame(pendentes)

    if path.exists():
        antigo = pd.read_csv(path)
        novo = pd.concat([antigo, novo], ignore_index=True)

    novo.to_csv(path, index=False, encoding="utf-8-sig")
