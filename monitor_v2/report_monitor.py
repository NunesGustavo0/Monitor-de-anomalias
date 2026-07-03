from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

OUTPUT = Path("outputs")
RELATORIO = OUTPUT / "relatorio_monitor.md"


def _value_counts_text(df: pd.DataFrame, coluna: str) -> str:
    if coluna not in df.columns or df.empty:
        return "- Sem dados\n"
    linhas = []
    for valor, qtd in df[coluna].value_counts().items():
        linhas.append(f"- {valor}: {qtd}")
    return "\n".join(linhas) + "\n"


def gerar_relatorio() -> None:
    OUTPUT.mkdir(exist_ok=True)
    alerts_path = OUTPUT / "alerts.csv"
    audit_path = OUTPUT / "auditoria_alertas.csv"
    hitl_path = OUTPUT / "hitl_pendentes.csv"
    processados_path = OUTPUT / "processados.txt"

    if not alerts_path.exists():
        print("Nenhum alerta encontrado para gerar relatório.")
        return

    alertas = pd.read_csv(alerts_path)
    auditoria = pd.read_csv(audit_path) if audit_path.exists() else pd.DataFrame()
    hitl = pd.read_csv(hitl_path) if hitl_path.exists() else pd.DataFrame()
    processados = processados_path.read_text(encoding="utf-8").splitlines() if processados_path.exists() else []

    total_alertas = len(alertas)
    total_hitl = len(hitl)
    taxa_hitl = total_hitl / total_alertas if total_alertas else 0

    texto = "# Relatório do Monitor de Anomalias SetupBox\n\n"
    texto += f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"

    texto += "## Resumo Geral\n\n"
    texto += f"- Arquivos processados: {len(processados)}\n"
    texto += f"- Total de alertas emitidos: {total_alertas}\n"
    texto += f"- Eventos registrados em auditoria: {len(auditoria)}\n"
    texto += f"- Alertas enviados para revisão humana HITL: {total_hitl}\n"
    texto += f"- Taxa de revisão humana: {taxa_hitl:.2%}\n\n"

    texto += "## Alertas por Severidade\n\n"
    texto += _value_counts_text(alertas, "severidade")

    texto += "\n## Tipos de Anomalia\n\n"
    texto += _value_counts_text(alertas, "tipo")

    texto += "\n## Ações Sugeridas\n\n"
    texto += _value_counts_text(alertas, "acao")

    texto += "\n## Governança e Auditoria\n\n"
    texto += (
        "O monitor processa arquivos da pasta `logs`, evita reprocessamento por meio de `processados.txt`, "
        "gera alertas estruturados em `alerts.csv`, registra trilha de auditoria em `auditoria_alertas.csv` "
        "e encaminha alertas de severidade Alta ou Crítica para revisão humana em `hitl_pendentes.csv`.\n\n"
    )

    texto += "## Métricas de Avaliação\n\n"
    texto += (
        "As métricas de precisão, recall, latência e falso-alarme devem ser calculadas quando o arquivo de gabarito "
        "de incidentes do período for disponibilizado. Sem o gabarito, o relatório apresenta métricas operacionais "
        "do monitor e a trilha de alertas gerados.\n"
    )

    RELATORIO.write_text(texto, encoding="utf-8")
    print(f"Relatório gerado em: {RELATORIO}")


if __name__ == "__main__":
    gerar_relatorio()
