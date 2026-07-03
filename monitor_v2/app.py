from __future__ import annotations

from pathlib import Path
from datetime import timedelta
import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).parent
DEFAULT_FILE = APP_DIR / "recording_test_setupbox.xlsx"
STEPS = [
    "fw_download", "bootloader", "kernel", "rootfs", "secure_boot", "mac_write",
    "wifi_cal", "bluetooth", "cable_scan", "hdmi_edid", "dvb_tuner", "drm_keys", "final_check"
]

st.set_page_config(page_title="Anomalias de Gravação - Setupbox", layout="wide")

@st.cache_data(show_spinner=False)
def load_data(path_or_bytes):
    rec = pd.read_excel(path_or_bytes, sheet_name="recordings")
    stops = pd.read_excel(path_or_bytes, sheet_name="line_stops")
    dictionary = pd.read_excel(path_or_bytes, sheet_name="data_dictionary")
    rec["timestamp"] = pd.to_datetime(rec["timestamp"])
    rec["date"] = pd.to_datetime(rec["date"]).dt.date
    rec["hour"] = rec["timestamp"].dt.floor("h")
    stops["stop_start"] = pd.to_datetime(stops["stop_start"])
    stops["stop_end"] = pd.to_datetime(stops["stop_end"])
    return rec, stops, dictionary


def option_filter(label, series):
    values = sorted([x for x in series.dropna().unique()])
    return st.sidebar.multiselect(label, values, default=values)


def filter_data(df):
    st.sidebar.header("Filtros de auditoria")
    date_min, date_max = df["timestamp"].min().date(), df["timestamp"].max().date()
    date_range = st.sidebar.date_input("Período", value=(date_min, date_max), min_value=date_min, max_value=date_max)
    if len(date_range) == 2:
        start = pd.Timestamp(date_range[0])
        end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    else:
        start, end = pd.Timestamp(date_min), pd.Timestamp(date_max) + pd.Timedelta(days=1)

    lines = option_filter("Linha", df["line"])
    stations = option_filter("Estação", df["station"])
    jigs = option_filter("Jig", df["jig_id"])
    models = option_filter("Modelo", df["model"])
    firmwares = option_filter("Firmware", df["firmware_version"])
    shifts = option_filter("Turno", df["shift"])
    dispositions = option_filter("Disposition", df["disposition"])
    errors = st.sidebar.multiselect("Erro", sorted(df["error_code"].dropna().unique()))

    mask = (
        (df["timestamp"] >= start) & (df["timestamp"] < end) &
        df["line"].isin(lines) & df["station"].isin(stations) & df["jig_id"].isin(jigs) &
        df["model"].isin(models) & df["firmware_version"].isin(firmwares) &
        df["shift"].isin(shifts) & df["disposition"].isin(dispositions)
    )
    if errors:
        mask &= df["error_code"].isin(errors)
    return df[mask].copy(), start, end


def metrics(df, stops, start, end):
    serials = df["serial_number"].nunique()
    attempts = len(df)
    first_attempt = df[df["attempt"] == 1].drop_duplicates("serial_number")
    fpy = (first_attempt["result"].eq("PASS").sum() / serials) if serials else 0
    final_yield = df.groupby("serial_number")["result"].apply(lambda s: s.eq("PASS").any()).mean() if serials else 0
    rework_rate = df["disposition"].eq("REWORK").sum() / attempts if attempts else 0
    scrap_rate = df["disposition"].eq("SCRAP").sum() / attempts if attempts else 0
    ppm = (1 - fpy) * 1_000_000
    step_failures, opportunities = 0, 0
    for step in STEPS:
        col = f"{step}_ok"
        if col in df:
            applicable = df[col].notna()
            opportunities += applicable.sum()
            step_failures += ((df[col] == False) | (df[col] == 0)).sum()
    dpmo = (step_failures / opportunities * 1_000_000) if opportunities else 0
    hours = max((end - start).total_seconds() / 3600, 0.01)
    uph = serials / hours
    lines = max(df["line"].nunique(), 1)
    stations = max(df["station"].nunique(), 1)
    uph_station = serials / (stations * hours)
    planned_minutes = hours * 60 * lines
    stops_f = stops[(stops["stop_start"] < end) & (stops["stop_end"] >= start) & stops["line"].isin(df["line"].unique())]
    downtime = stops_f["duration_min"].sum()
    availability = (planned_minutes - downtime) / planned_minutes if planned_minutes else 0
    return dict(serials=serials, attempts=attempts, fpy=fpy, final_yield=final_yield, rework_rate=rework_rate,
                scrap_rate=scrap_rate, ppm=ppm, dpmo=dpmo, uph=uph, uph_station=uph_station,
                availability=availability, downtime=downtime, opportunities=opportunities)


def make_report(df, stops, start, end):
    m = metrics(df, stops, start, end)
    fails = df[df["result"] == "FAIL"]
    top = fails.groupby(["failed_step", "error_code"]).size().sort_values(ascending=False).head(10).reset_index(name="falhas")
    top_md = top.to_markdown(index=False) if not top.empty else "Sem falhas no filtro atual."
    scrap = df[df["disposition"] == "SCRAP"].groupby(["failed_step", "error_code", "line", "jig_id"]).size().sort_values(ascending=False).head(10).reset_index(name="scrap")
    scrap_md = scrap.to_markdown(index=False) if not scrap.empty else "Sem scrap no filtro atual."
    return f"""# Relatório filtrado - Dashboard Setupbox

Período analisado: {start} até {end - timedelta(seconds=1)}

## KPIs
- Tentativas: {m['attempts']:,}
- Seriais únicos: {m['serials']:,}
- FPY: {m['fpy']:.2%}
- Yield final: {m['final_yield']:.2%}
- Rework: {m['rework_rate']:.2%}
- Scrap: {m['scrap_rate']:.2%}
- PPM: {m['ppm']:,.0f}
- DPMO: {m['dpmo']:,.0f}
- UPH: {m['uph']:.1f}
- UPH por estação: {m['uph_station']:.1f}
- Disponibilidade estimada: {m['availability']:.2%}
- Downtime: {m['downtime']:.0f} min

## Pareto de defeitos no filtro
{top_md}

## Scrap por defeito/local
{scrap_md}

## BPMN/PDD
Consulte a aba BPMN e PDD do dashboard ou o arquivo `relatorio_achados.md` entregue junto ao projeto.
"""

uploaded = st.sidebar.file_uploader("Carregar xlsx ou csv", type=["xlsx", "csv"])
if uploaded is not None and uploaded.name.endswith(".xlsx"):
    rec, stops, dictionary = load_data(uploaded)
elif DEFAULT_FILE.exists():
    rec, stops, dictionary = load_data(DEFAULT_FILE)
else:
    st.error("Arquivo recording_test_setupbox.xlsx não encontrado.")
    st.stop()

st.title("Dashboard de Anomalias de Gravação - IFAM / AxAcademy")
st.caption("Dashboard somente leitura para auditoria de flashing, rework, scrap, downtime e integridade.")

df, start, end = filter_data(rec)
stops_f = stops[(stops["stop_start"] < end) & (stops["stop_end"] >= start) & stops["line"].isin(df["line"].unique())]

aba_kpi, aba_pareto, aba_jig, aba_tempo, aba_cycle, aba_yield, aba_audit, aba_monitor, aba_bpmn = st.tabs([
    "KPIs",
    "Pareto",
    "Jig x Etapa",
    "Falhas no tempo",
    "Cycle time",
    "Yield/Rework/Scrap",
    "Auditoria",
    "📡 Monitor",
    "BPMN e PDD",
])

with aba_kpi:
    m = metrics(df, stops, start, end)
    cols = st.columns(5)
    cols[0].metric("Tentativas", f"{m['attempts']:,}")
    cols[1].metric("Seriais únicos", f"{m['serials']:,}")
    cols[2].metric("FPY", f"{m['fpy']:.2%}")
    cols[3].metric("Yield final", f"{m['final_yield']:.2%}")
    cols[4].metric("PPM", f"{m['ppm']:,.0f}")
    cols = st.columns(5)
    cols[0].metric("DPMO", f"{m['dpmo']:,.0f}")
    cols[1].metric("Rework", f"{m['rework_rate']:.2%}")
    cols[2].metric("Scrap", f"{m['scrap_rate']:.2%}")
    cols[3].metric("UPH", f"{m['uph']:.1f}")
    cols[4].metric("Disponibilidade", f"{m['availability']:.2%}", f"-{m['downtime']:.0f} min")
    st.dataframe(dictionary, use_container_width=True)

with aba_pareto:
    fails = df[df["result"] == "FAIL"].copy()
    if fails.empty:
        st.info("Sem falhas no filtro atual.")
    else:
        pareto = fails.groupby(["failed_step", "error_code"]).size().reset_index(name="falhas").sort_values("falhas", ascending=False)
        pareto["defeito"] = pareto["failed_step"].astype(str) + " / " + pareto["error_code"].astype(str)
        pareto["pct"] = pareto["falhas"] / pareto["falhas"].sum()
        pareto["pct_acum"] = pareto["pct"].cumsum()
        fig = go.Figure()
        fig.add_bar(x=pareto["defeito"], y=pareto["falhas"], name="Falhas")
        fig.add_scatter(x=pareto["defeito"], y=pareto["pct_acum"]*100, name="% acumulado", yaxis="y2")
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 110]), xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(pareto, use_container_width=True)

with aba_jig:
    rows = []
    for step in STEPS:
        col = f"{step}_ok"
        if col in df:
            tmp = df[df[col].notna()].groupby(["jig_id", "line", "station"])[col].agg(
                tentativas="size", falhas=lambda s: ((s == False) | (s == 0)).sum()
            ).reset_index()
            tmp["etapa"] = step
            tmp["taxa_falha"] = tmp["falhas"] / tmp["tentativas"]
            rows.append(tmp)
    jig_step = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not jig_step.empty:
        pivot = jig_step.pivot_table(index="jig_id", columns="etapa", values="taxa_falha", aggfunc="mean").fillna(0)
        fig = px.imshow(pivot, aspect="auto", labels=dict(color="Taxa de falha"))
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Equipamentos com maior taxa por etapa")
        st.dataframe(jig_step.sort_values("taxa_falha", ascending=False), use_container_width=True)

with aba_tempo:
    fails_hour = df[df["result"] == "FAIL"].groupby(["hour", "line"]).size().reset_index(name="falhas")
    fig = px.line(fails_hour, x="hour", y="falhas", color="line", markers=True)
    for _, r in stops_f.iterrows():
        fig.add_vrect(x0=r["stop_start"], x1=r["stop_end"], opacity=0.18, line_width=0,
                      annotation_text=f"{r['line']} - {r['reason']}", annotation_position="top left")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(stops_f.sort_values("stop_start"), use_container_width=True)

with aba_cycle:
    cycle_cols = [c for c in df.columns if c.endswith("_cycle_s")]
    long = df[["timestamp", "line", "station", "jig_id", "model", "firmware_version", "serial_number"] + cycle_cols].melt(
        id_vars=["timestamp", "line", "station", "jig_id", "model", "firmware_version", "serial_number"],
        value_vars=cycle_cols, var_name="etapa", value_name="cycle_s"
    ).dropna()
    long["etapa"] = long["etapa"].str.replace("_cycle_s", "", regex=False)
    stats = long.groupby("etapa")["cycle_s"].agg(mediana="median", media="mean", p95=lambda s: s.quantile(.95), p99=lambda s: s.quantile(.99), maximo="max").reset_index()
    st.dataframe(stats.sort_values("mediana", ascending=False), use_container_width=True)
    fig = px.box(long, x="etapa", y="cycle_s", points=False)
    st.plotly_chart(fig, use_container_width=True)
    med = long.groupby("etapa")["cycle_s"].transform("median")
    mad = (long["cycle_s"] - med).abs().groupby(long["etapa"]).transform("median").replace(0, np.nan)
    long["outlier"] = long["cycle_s"] > med + 6 * mad
    st.subheader("Outliers de cycle time")
    st.dataframe(long[long["outlier"]].sort_values("cycle_s", ascending=False).head(500), use_container_width=True)

with aba_yield:
    dim = st.selectbox("Dimensão", ["line", "station", "model", "firmware_version", "jig_id", "operator", "shift"])
    by = df.groupby(dim).agg(tentativas=("serial_number", "size"), seriais=("serial_number", "nunique"), pass_tentativas=("result", lambda s: (s == "PASS").sum()), scrap=("disposition", lambda s: (s == "SCRAP").sum()), rework=("disposition", lambda s: (s == "REWORK").sum())).reset_index()
    by["yield_tentativa"] = by["pass_tentativas"] / by["tentativas"]
    by["scrap_rate"] = by["scrap"] / by["tentativas"]
    by["rework_rate"] = by["rework"] / by["tentativas"]
    fig = px.bar(by.sort_values("yield_tentativa"), x=dim, y="yield_tentativa", text="yield_tentativa")
    fig.update_traces(texttemplate="%{text:.1%}")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(by.sort_values("yield_tentativa"), use_container_width=True)
    st.subheader("Disposition")
    st.plotly_chart(px.pie(df, names="disposition"), use_container_width=True)

with aba_audit:
    cols = ["timestamp", "shift", "line", "station", "jig_id", "operator", "model", "sku", "firmware_version", "serial_number", "mac_address", "api_key", "attempt", "result", "failed_step", "error_code", "disposition", "total_cycle_s", "cable_channels_found"]
    st.dataframe(df[cols].sort_values("timestamp"), use_container_width=True, height=520)
    csv = df[cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("Baixar auditoria filtrada CSV", csv, "auditoria_filtrada.csv", "text/csv")
    report = make_report(df, stops, start, end).encode("utf-8")
    st.download_button("Baixar relatório filtrado Markdown", report, "relatorio_filtrado.md", "text/markdown")
    mac_dup = rec.groupby("mac_address")["serial_number"].nunique().reset_index(name="seriais_diferentes")
    mac_dup = mac_dup[mac_dup["seriais_diferentes"] > 1].sort_values("seriais_diferentes", ascending=False)
    st.subheader("Integridade: MAC em seriais diferentes")
    st.dataframe(mac_dup, use_container_width=True)


def read_output_csv(path: Path) -> pd.DataFrame:
    """Lê CSVs gerados pelo monitor sem quebrar o dashboard se o arquivo estiver vazio ou ausente."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Não foi possível ler {path.name}: {exc}")
        return pd.DataFrame()


with aba_monitor:
    st.header("📡 Monitor de Anomalias - Tarefa 02")
    st.caption("Painel de acompanhamento dos alertas, auditoria e revisão humana gerados pelo monitor automático.")

    output_dir = APP_DIR / "outputs"
    alerts_file = output_dir / "alerts.csv"
    audit_file = output_dir / "auditoria_alertas.csv"
    hitl_file = output_dir / "hitl_pendentes.csv"
    processados_file = output_dir / "processados.txt"
    relatorio_file = output_dir / "relatorio_monitor.md"

    df_alertas = read_output_csv(alerts_file)
    df_auditoria_monitor = read_output_csv(audit_file)
    df_hitl = read_output_csv(hitl_file)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🚨 Alertas", len(df_alertas))
    col2.metric("📋 Auditoria", len(df_auditoria_monitor))
    col3.metric("👨‍💻 HITL pendentes", len(df_hitl))

    arquivos_processados = 0
    if processados_file.exists():
        arquivos_processados = len([linha for linha in processados_file.read_text(encoding="utf-8").splitlines() if linha.strip()])
    col4.metric("📁 Arquivos processados", arquivos_processados)

    st.divider()

    if df_alertas.empty:
        st.info("Nenhum alerta gerado ainda. Rode `python monitor.py` para processar os logs.")
    else:
        st.subheader("🚨 Últimos alertas")

        sort_col = "data_envio" if "data_envio" in df_alertas.columns else df_alertas.columns[-1]
        st.dataframe(
            df_alertas.sort_values(sort_col, ascending=False),
            use_container_width=True,
            height=320,
        )

        csv_alertas = df_alertas.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Baixar alertas CSV", csv_alertas, "alerts.csv", "text/csv")

        if "severidade" in df_alertas.columns:
            st.subheader("📊 Alertas por severidade")
            severidade = df_alertas["severidade"].value_counts().reset_index()
            severidade.columns = ["Severidade", "Quantidade"]
            st.bar_chart(severidade.set_index("Severidade"))

        if "tipo" in df_alertas.columns:
            st.subheader("📌 Tipos de anomalia")
            tipos = df_alertas["tipo"].value_counts().reset_index()
            tipos.columns = ["Tipo", "Quantidade"]
            st.dataframe(tipos, use_container_width=True)

    st.divider()

    st.subheader("👨‍💻 Revisão humana - HITL")
    if df_hitl.empty:
        st.success("Nenhum caso pendente de revisão humana.")
    else:
        st.dataframe(df_hitl, use_container_width=True, height=260)
        csv_hitl = df_hitl.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Baixar pendências HITL CSV", csv_hitl, "hitl_pendentes.csv", "text/csv")

    st.divider()

    st.subheader("📋 Trilha de auditoria do monitor")
    if df_auditoria_monitor.empty:
        st.info("A auditoria do monitor ainda não foi gerada.")
    else:
        st.dataframe(df_auditoria_monitor, use_container_width=True, height=260)
        csv_audit = df_auditoria_monitor.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Baixar auditoria do monitor CSV", csv_audit, "auditoria_alertas.csv", "text/csv")

    st.divider()

    st.subheader("📄 Relatório do monitor")
    if relatorio_file.exists():
        relatorio_texto = relatorio_file.read_text(encoding="utf-8")
        st.markdown(relatorio_texto)
        st.download_button(
            "Baixar relatório Markdown",
            relatorio_texto.encode("utf-8"),
            "relatorio_monitor.md",
            "text/markdown",
        )
    else:
        st.info("Relatório ainda não encontrado. Gere com `python report_monitor.py`.")


with aba_bpmn:
    st.subheader("Textual BPMN")
    st.markdown("""Início → Identificar unidade → Baixar firmware/API key → Validar MD5 → Gravar etapas em sequência → Validar checksums → PASS
    Se falhar na tentativa 1: registrar REWORK → regravar mesmo serial.
    Se falhar novamente: registrar SCRAP → fim.""")

# Adicionando o Diagrama
    st.subheader("BPMN Diagrama")

    codigo_mermaid = """
    flowchart TD
        A([Início: setupbox chega ao jig]) --> B[Identificar modelo, SKU, serial e MAC]
        B --> C[Baixar firmware usando API key remota]
        C --> D{Download OK / MD5 OK?}
        D -- Não --> R[Registrar falha e marcar REWORK]
        D -- Sim --> E[Gravar bootloader]
        E --> F[Gravar kernel]
        F --> G[Gravar rootfs]
        G --> H[Gravar secure boot]
        H --> I[Gravar MAC]
        I --> J[Calibrar Wi-Fi]
        J --> K{Modelo tem Bluetooth?}
        K -- Sim --> L[Calibrar Bluetooth]
        K -- Não --> M{Modelo tem cabo?}
        L --> M
        M -- Sim --> N[Varredura de canais / DVB tuner]
        M -- Não --> O[HDMI EDID]
        N --> O
        O --> P[Gravar DRM keys]
        P --> Q[Final check]
        Q --> S{Todas as etapas com checksum OK?}
        S -- Sim --> T([Fim: PASS])
        S -- Não e tentativa 1 --> R
        R --> U{Já é tentativa 2?}
        U -- Não --> V[Regravar mesmo serial]
        V --> C
        U -- Sim --> W([Fim: SCRAP])
    """
    #Renderizando para o BPMN
    st_mermaid(codigo_mermaid, height="700px")
    st.markdown("Caso apareça algum erro de mermaid, **atualize a página!!!**")
    st.subheader("PDD")
    st.markdown("""
Campo|Conteúdo
:-:|:-:
**Objetivo:**| monitorar o processo de gravação e provar anomalias por quê, onde e quando.  
**Escopo:**|tentativas de flashing, validações MD5, rework, scrap e downtime.  
**Entradas:**| serial, MAC, modelo, SKU, linha, estação, jig, operador, turno, firmware, API key, etapas, MD5s e cycle times.  
**Saídas:**| PASS/REWORK/SCRAP, FPY, yield final, PPM, DPMO, downtime, Pareto, gargalo, outliers e auditoria exportável.  
**Regras:**| tentativa com falha vira rework; falha repetida vira scrap; etapas Bluetooth/cabo só contam quando aplicáveis.  
**Automação:**| alertas por limite de falha, queda de FPY, downtime correlacionado e MAC duplicado.
""")