from __future__ import annotations
from pathlib import Path
import time
import pandas as pd

from alerts import salvar_alertas, enviar_telegram
from audit import salvar_auditoria
from baseline import calcular_baseline
from hitl import enviar_para_hitl
from rules import detectar_anomalias

PASTA_LOGS = Path("../logs")
OUTPUT = Path("outputs")
PROCESSADOS = OUTPUT / "processados.txt"
INTERVALO_SEGUNDOS = 60
TAMANHO_JANELA = 100

PASTA_LOGS.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)


def carregar_processados() -> set[str]:
    if not PROCESSADOS.exists():
        return set()
    return set(PROCESSADOS.read_text(encoding="utf-8").splitlines())


def salvar_processado(nome_arquivo: str) -> None:
    with open(PROCESSADOS, "a", encoding="utf-8") as f:
        f.write(nome_arquivo + "\n")


def carregar_dados(arquivo: Path) -> pd.DataFrame:
    if arquivo.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(arquivo, sheet_name="recordings")
    elif arquivo.suffix.lower() == ".csv":
        df = pd.read_csv(arquivo)
    else:
        raise ValueError(f"Formato não suportado: {arquivo.name}")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def executar_monitor() -> None:
    print("Monitor iniciado...")

    processados = carregar_processados()
    arquivos = sorted(list(PASTA_LOGS.glob("*.xlsx")) + list(PASTA_LOGS.glob("*.csv")))
    novos = [arq for arq in arquivos if arq.name not in processados]

    if not novos:
        print("Nenhum arquivo novo para processar.")
        return

    for arquivo in novos:
        print(f"\nProcessando: {arquivo.name}")

        try:
            df = carregar_dados(arquivo)
        except Exception as exc:
            print(f"Erro ao carregar {arquivo.name}: {exc}")
            salvar_processado(arquivo.name)
            continue

        if "timestamp" in df.columns:
            janela = df.sort_values("timestamp").tail(TAMANHO_JANELA)
        else:
            janela = df.tail(TAMANHO_JANELA)

        baseline = calcular_baseline(janela)
        print("\n===== BASELINE DA JANELA =====")
        print(f"Média: {baseline['media']:.2%}")
        print(f"Desvio: {baseline['desvio']:.2%}")
        print(f"Limite: {baseline['limite']:.2%}")

        alertas = detectar_anomalias(janela)

        if alertas:
            print(f"\n{len(alertas)} alerta(s) detectado(s).")
            for alerta in alertas:
                print("\n=== ALERTA DETECTADO ===")
                print(f"Tipo: {alerta.get('tipo')}")
                print(f"Onde: {alerta.get('onde')}")
                print(f"Severidade: {alerta.get('severidade')}")
                print(f"Evidência: {alerta.get('evidencia')}")
                print(f"Ação sugerida: {alerta.get('acao')}")

            salvar_auditoria(alertas)
            salvar_alertas(alertas)
            enviar_para_hitl(alertas)
            enviar_telegram(alertas)
        else:
            print("Nenhuma anomalia detectada.")

        salvar_processado(arquivo.name)


def executar_continuo() -> None:
    print("Monitor automático iniciado. Pressione CTRL + C para parar.")
    while True:
        executar_monitor()
        print("Aguardando novos arquivos...")
        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    executar_continuo()
