"""
Halaman dashboard: cuaca saat ini, prediksi SVM, dan tren sensor.
"""

from __future__ import annotations

from typing import Any, Dict, List

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import firebase_client
from app_config import HISTORY_LIMIT
from data_service import (
    history_to_series,
    load_prediction_for_station,
    normalize_prediction,
    summarize_current,
)
from station_service import active_stations, station_label_map
from ui_components import (
    COLOR_ACCENT,
    COLOR_PRIMARY,
    fmt,
    footer,
    header,
    info_panel,
    metric_row,
    plotly_chart,
    render_prediction_hero,
    render_weather_probability_chart,
    section,
    status_badge,
    style_figure,
)


def _get_client() -> firebase_client.FirebaseRestClient:
    if "firebase_client" not in st.session_state:
        st.session_state["firebase_client"] = firebase_client.FirebaseRestClient()
    return st.session_state["firebase_client"]


def _current_fan(current: Dict[str, Any]) -> str:
    level = current.get("level")
    if level == "danger":
        return "Nyalakan kipas penuh (100%)"
    if level == "warning":
        return "Nyalakan kipas sedang (50–75%)"
    return "Ventilasi normal / minimal"


def render_dashboard() -> None:
    header(
        "Dashboard Cuaca",
        "Cuaca mikro kandang, THI, dan rekomendasi ventilasi ayam pejantan",
    )

    client = _get_client()
    stations = active_stations()
    if not stations:
        st.warning("Belum ada lokasi pemantauan aktif. Kelola lokasi di menu Manajemen Lokasi.")
        return

    labels = station_label_map(stations)
    station_map = {s["station_id"]: s for s in stations}

    col_select, col_refresh = st.columns([3, 1])
    with col_select:
        selected_id = st.selectbox(
            "Lokasi pemantauan",
            options=list(labels.keys()),
            format_func=lambda sid: labels.get(sid, sid),
            key="dashboard_station",
        )
    with col_refresh:
        if st.button("Muat ulang data", use_container_width=True, type="secondary"):
            st.rerun()

    station = station_map.get(selected_id, {})
    objek = station.get("objek", "Kandang Ayam Pejantan")
    st.caption(f"Objek: {objek}")

    sensor = firebase_client.read_latest_sensor(client, selected_id)
    history = firebase_client.read_sensor_history(client, selected_id, limit=HISTORY_LIMIT)
    prediction_raw = load_prediction_for_station(client, selected_id)
    prediction = normalize_prediction(prediction_raw)
    if prediction is None:
        prediction = normalize_prediction(
            {
                "predicted_class": "-",
                "forecast_values": {},
                "recommendations": ["Prediksi belum tersedia."],
            }
        )

    current = summarize_current(sensor)
    is_vc = selected_id == "AWS_TPST_VC"

    section("Cuaca Saat Ini")
    if not current:
        st.info("Data cuaca terkini belum tersedia untuk lokasi ini.")
    else:
        metrics: List[Dict[str, Any]] = [
            {
                "label": "Suhu",
                "value": fmt(current.get("suhu"), 1),
                "unit": "°C",
                "desc": f"Pembaruan: {current.get('waktu', '-')}",
                "accent": COLOR_PRIMARY,
            },
            {
                "label": "Kelembapan",
                "value": fmt(current.get("kelembapan"), 1),
                "unit": "%RH",
                "desc": "Kelembapan relatif",
                "accent": "#0ea5e9",
            },
            {
                "label": "Tekanan",
                "value": fmt(current.get("tekanan"), 1),
                "unit": "hPa",
                "desc": "Tekanan atmosfer",
                "accent": "#3b82f6",
            },
            {
                "label": "Intensitas Cahaya",
                "value": fmt(current.get("cahaya"), 0),
                "unit": "lux",
                "desc": "Radiasi matahari" if is_vc else "Sensor cahaya",
                "accent": "#60a5fa",
            },
            {
                "label": "Curah Hujan",
                "value": fmt(current.get("hujan"), 2),
                "unit": "mm",
                "desc": "Akumulasi per jam" if is_vc else "Interval pengukuran",
                "accent": "#2563eb",
            },
            {
                "label": "Kecepatan Angin",
                "value": fmt(current.get("kecepatan_angin"), 2),
                "unit": "km/j",
                "desc": "Kecepatan angin",
                "accent": "#64748b",
            },
            {
                "label": "Indeks THI",
                "value": fmt(current.get("thi"), 2),
                "unit": "",
                "desc": f"Status: {current.get('heat_status', '-')}",
                "accent": current.get("warna", COLOR_ACCENT),
            },
        ]
        if not is_vc and current.get("daya_mw") is not None:
            metrics.append(
                {
                    "label": "Konsumsi Daya",
                    "value": fmt(current.get("daya_mw"), 1),
                    "unit": "mW",
                    "desc": f"{fmt(current.get('tegangan_v'), 2)} V • {fmt(current.get('arus_ma'), 1)} mA",
                    "accent": "#f97316",
                }
            )
        metric_row(metrics, columns=4)

        st.markdown("#### Status stres panas")
        status_badge(current.get("heat_status", "-"), current.get("level", "info"))
        st.caption(f"Rekomendasi kipas: **{_current_fan(current)}**")

    st.divider()

    section("Hasil Prediksi Cuaca (t+1 jam)")
    col_a, col_b = st.columns([1.25, 1])
    with col_a:
        render_prediction_hero(prediction)
    with col_b:
        recs = prediction.get("recommendations") or []
        info_panel(
            "Rekomendasi operasional",
            [r.replace("• ", "").strip() for r in recs if r],
        )

    forecast = prediction.get("forecast", {})
    metric_row(
        [
            {"label": "Suhu", "value": fmt(forecast.get("suhu"), 1), "unit": "°C", "accent": COLOR_PRIMARY},
            {"label": "Kelembapan", "value": fmt(forecast.get("kelembapan"), 1), "unit": "%RH", "accent": "#0ea5e9"},
            {"label": "Angin", "value": fmt(forecast.get("kecepatan_angin"), 2), "unit": "km/j", "accent": "#64748b"},
            {"label": "Hujan", "value": fmt(forecast.get("hujan"), 2), "unit": "mm", "accent": "#2563eb"},
            {"label": "THI", "value": fmt(prediction.get("thi_forecast"), 2), "unit": "", "accent": "#f59e0b"},
            {"label": "Status", "value": prediction.get("heat_stress_status", "-"), "unit": "", "accent": prediction.get("warna", COLOR_ACCENT)},
        ],
        columns=3,
    )

    probabilities = prediction.get("probabilities_pct") or {}
    if probabilities:
        section("Distribusi probabilitas kelas cuaca")
        render_weather_probability_chart(probabilities, key=f"prob_{selected_id}")

    st.divider()

    section("Riwayat cuaca")
    if not history:
        st.info("Riwayat cuaca belum tersedia untuk lokasi ini.")
    else:
        series = history_to_series(history)
        tab_suhu, tab_hujan, tab_angin, tab_thi = st.tabs(
            ["Suhu & Kelembapan", "Curah Hujan", "Angin", "Indeks THI"]
        )
        with tab_suhu:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=series["waktu"],
                    y=series["suhu"],
                    name="Suhu (°C)",
                    line=dict(color="#2563eb", width=2.2),
                    mode="lines+markers",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=series["waktu"],
                    y=series["kelembapan"],
                    name="Kelembapan (%RH)",
                    line=dict(color="#0ea5e9", width=2.2),
                    mode="lines+markers",
                    yaxis="y2",
                )
            )
            fig.update_layout(
                yaxis=dict(title="Suhu (°C)", gridcolor="#e8edf4"),
                yaxis2=dict(title="Kelembapan (%RH)", overlaying="y", side="right", showgrid=False),
            )
            style_figure(fig, height=360)
            plotly_chart(fig, key=f"suhu_{selected_id}")

        with tab_hujan:
            fig = px.bar(
                x=series["waktu"],
                y=series["hujan"],
                labels={"waktu": "Waktu", "hujan": "Curah Hujan (mm)"},
                color_discrete_sequence=["#3b82f6"],
            )
            style_figure(fig, height=330)
            plotly_chart(fig, key=f"hujan_{selected_id}")

        with tab_angin:
            fig = px.line(
                x=series["waktu"],
                y=series["kecepatan_angin"],
                labels={"waktu": "Waktu", "kecepatan_angin": "Kecepatan Angin (km/j)"},
                markers=True,
            )
            fig.update_traces(line=dict(color="#64748b", width=2.2))
            style_figure(fig, height=330)
            plotly_chart(fig, key=f"angin_{selected_id}")

        with tab_thi:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=series["waktu"],
                    y=series["thi"],
                    name="THI",
                    line=dict(color="#f59e0b", width=2.2),
                    mode="lines+markers",
                )
            )
            fig.add_hline(y=78.0, line_dash="dash", line_color="#f59e0b", annotation_text="Waspada (78)")
            fig.add_hline(y=82.0, line_dash="dash", line_color="#dc2626", annotation_text="Bahaya (82)")
            style_figure(fig, height=330)
            plotly_chart(fig, key=f"thi_{selected_id}")

    footer()
