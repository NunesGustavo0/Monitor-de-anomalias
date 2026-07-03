#app.py
"""
Aplicação principal, que é responsável por inicializar o projeto, atráves pelo comando: streamlit run app.py
"""
from __future__ import annotations
from pathlib import Path
from services import load_data,filter_data,metrics,make_report, STEPS
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_mermaid import st_mermaid


APP_DIR = Path(__file__).parent
DEFAULT_FILE = APP_DIR / "recording_test_setupbox.xlsx"

st.set_page_config(page_title="Anomalias de Gravação - Setupbox", layout="wide")

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

aba_kpi, aba_pareto, aba_jig, aba_tempo, aba_cycle, aba_yield, aba_audit, aba_bpmn = st.tabs([
    "KPIs", "Pareto", "Jig x Etapa", "Falhas no tempo", "Cycle time", "Yield/Rework/Scrap", "Auditoria", "BPMN e PDD"
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
