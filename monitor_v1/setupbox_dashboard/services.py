#services.py

"""
Processamentos, leituras dos relatório e análise de tabela usando o PANDAS
"""
import streamlit as st
import pandas as pd
from datetime import timedelta

STEPS = [
    "fw_download", "bootloader", "kernel", "rootfs", "secure_boot", "mac_write",
    "wifi_cal", "bluetooth", "cable_scan", "hdmi_edid", "dvb_tuner", "drm_keys", "final_check"
]

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