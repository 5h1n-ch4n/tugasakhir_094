"""
Halaman riwayat: grafik tren cuaca per lokasi pemantauan.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import firebase_client
from app_config import HISTORY_LIMIT
from data_service import history_to_series
from station_service import active_stations, station_label_map
from ui_components import fmt, footer, header, metric_row, plotly_chart, section, style_figure


def render_history_page() -> None:
    header("Riwayat Data", "Tren cuaca mikro kandang ayam pejantan")

    stations = active_stations()
    if not stations:
        st.warning("Belum ada lokasi pemantauan aktif.")
        return

    labels = station_label_map(stations)
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_id = st.selectbox(
            "Lokasi pemantauan",
            options=list(labels.keys()),
            format_func=lambda sid: labels.get(sid, sid),
            key="history_station",
        )
    with col2:
        limit = st.slider(
            "Rentang tampilan",
            min_value=50,
            max_value=min(1000, HISTORY_LIMIT),
            value=200,
            step=50,
        )

    client = firebase_client.FirebaseRestClient()
    with st.spinner("Memuat riwayat..."):
        history = firebase_client.read_sensor_history(client, selected_id, limit=limit)

    if not history:
        st.info("Belum ada riwayat untuk lokasi ini.")
        footer()
        return

    series = history_to_series(history)
    valid_temp = [v for v in series["suhu"] if v is not None]
    valid_hum = [v for v in series["kelembapan"] if v is not None]
    valid_rain = [v for v in series["hujan"] if v is not None]
    valid_thi = [v for v in series["thi"] if v is not None]

    section("Ringkasan")
    metric_row(
        [
            {
                "label": "Suhu rata-rata",
                "value": fmt(sum(valid_temp) / len(valid_temp) if valid_temp else None, 1),
                "unit": "°C",
                "desc": f"min {fmt(min(valid_temp) if valid_temp else None, 1)} / "
                    f"max {fmt(max(valid_temp) if valid_temp else None, 1)}",
                "accent": "#2563eb",
            },
            {
                "label": "Kelembapan rata-rata",
                "value": fmt(sum(valid_hum) / len(valid_hum) if valid_hum else None, 1),
                "unit": "%RH",
                "desc": f"min {fmt(min(valid_hum) if valid_hum else None, 1)} / "
                    f"max {fmt(max(valid_hum) if valid_hum else None, 1)}",
                "accent": "#0ea5e9",
            },
            {
                "label": "Total hujan",
                "value": fmt(sum(valid_rain) if valid_rain else None, 2),
                "unit": "mm",
                "desc": f"{len(history)} titik data",
                "accent": "#3b82f6",
            },
            {
                "label": "THI rata-rata",
                "value": fmt(sum(valid_thi) / len(valid_thi) if valid_thi else None, 2),
                "unit": "",
                "desc": "Indeks stres panas",
                "accent": "#f59e0b",
            },
        ],
        columns=4,
    )

    section("Tren suhu dan kelembapan")
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    style_figure(fig, height=340)
    plotly_chart(fig, key="hist_suhu_kelembapan")

    section("Curah hujan")
    fig = px.bar(
        x=series["waktu"],
        y=series["hujan"],
        labels={"waktu": "Waktu", "hujan": "Curah Hujan (mm)"},
        color_discrete_sequence=["#3b82f6"],
    )
    style_figure(fig, height=300)
    plotly_chart(fig, key="hist_hujan")

    section("Kecepatan angin")
    fig = px.line(
        x=series["waktu"],
        y=series["kecepatan_angin"],
        labels={"waktu": "Waktu", "kecepatan_angin": "Angin (km/j)"},
        markers=True,
    )
    fig.update_traces(line=dict(color="#64748b", width=2.2))
    style_figure(fig, height=280)
    plotly_chart(fig, key="hist_angin")

    footer()
