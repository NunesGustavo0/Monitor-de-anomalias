from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os
import pandas as pd
import requests

OUTPUT = Path("outputs")
OUTPUT.mkdir(exist_ok=True)


def salvar_alertas(alertas: list[dict]) -> None:
    if not alertas:
        return

    registros = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for alerta in alertas:
        item = alerta.copy()
        item["data_envio"] = agora
        registros.append(item)

    path = OUTPUT / "alerts.csv"
    novo = pd.DataFrame(registros)

    if path.exists():
        antigo = pd.read_csv(path)
        novo = pd.concat([antigo, novo], ignore_index=True)

    novo.to_csv(path, index=False, encoding="utf-8-sig")


def enviar_telegram(alertas: list[dict]) -> None:
    """Envio opcional por Telegram.

    Para ativar, defina as variáveis de ambiente:
    TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.
    Se não existirem, o monitor continua funcionando só com CSV.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id or not alertas:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for alerta in alertas:
        texto = (
            "🚨 ALERTA SETUPBOX\n\n"
            f"Tipo: {alerta.get('tipo')}\n"
            f"Onde: {alerta.get('onde')}\n"
            f"Severidade: {alerta.get('severidade')}\n"
            f"Evidência: {alerta.get('evidencia')}\n"
            f"Ação: {alerta.get('acao')}\n"
            f"Janela: {alerta.get('janela', 'N/A')}"
        )
        try:
            requests.post(url, data={"chat_id": chat_id, "text": texto}, timeout=15)
        except Exception as exc:
            print(f"Falha ao enviar Telegram: {exc}")
