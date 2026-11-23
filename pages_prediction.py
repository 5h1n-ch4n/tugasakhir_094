"""
Halaman prediksi: kelas cuaca, probabilitas, ambang batas, dan rekomendasi.
"""

from __future__ import annotations

import streamlit as st

import firebase_client
from data_service import (
    THI_BAHAYA,
    THI_WASPADA,
    SUHU_PANAS_BAHAYA,
    SUHU_PANAS_WASPADA,
    load_prediction_for_station,
    normalize_prediction,
)
from station_service import active_stations, station_label_map
from ui_components import (
    COLOR_PRIMARY,
    fmt,
    footer,
    header,
    info_panel,
    metric_row,
    render_prediction_hero,
    render_weather_probability_chart,
    section,
    status_badge,
)


def render_prediction_page() -> None:
    header(
        "Prediksi Cuaca",
        "Perkiraan kondisi cuaca mikro satu jam ke depan untuk kandang ayam pejantan",
    )

    stations = active_stations()
    if not stations:
        st.warning("Belum ada lokasi pemantauan aktif.")
        return

    labels = station_label_map(stations)
    selected_id = st.selectbox(
        "Lokasi pemantauan",
        options=list(labels.keys()),
        format_func=lambda sid: labels.get(sid, sid),
        key="prediction_station",
    )

    client = firebase_client.FirebaseRestClient()
    payload = load_prediction_for_station(client, selected_id)
    prediction = normalize_prediction(payload)
    if not prediction:
        st.info("Prediksi cuaca belum tersedia untuk lokasi ini.")
        footer()
        return

    section("Kelas cuaca prediksi")
    col_icon, col_detail = st.columns([1, 2])
    with col_icon:
        render_prediction_hero(prediction)
    with col_detail:
        metric_row(
            [
                {
                    "label": "Suhu prediksi",
                    "value": fmt(prediction.get("forecast", {}).get("suhu"), 1),
                    "unit": "°C",
                    "accent": COLOR_PRIMARY,
                },
                {
                    "label": "Kelembapan prediksi",
                    "value": fmt(prediction.get("forecast", {}).get("kelembapan"), 1),
                    "unit": "%RH",
                    "accent": "#0ea5e9",
                },
                {
                    "label": "THI prediksi",
                    "value": fmt(prediction.get("thi_forecast"), 2),
                    "unit": "",
                    "accent": "#f59e0b",
                },
            ],
            columns=3,
        )
        status_badge(
            prediction.get("heat_stress_status", "-"),
            prediction.get("level", "info"),
        )
        st.caption(f"Rekomendasi kipas: **{prediction.get('fan_recommendation', '-')}**")

    forecast = prediction.get("forecast", {}) or {}
    metric_row(
        [
            {"label": "Angin", "value": fmt(forecast.get("kecepatan_angin"), 2), "unit": "km/j", "accent": "#64748b"},
            {"label": "Hujan", "value": fmt(forecast.get("hujan"), 2), "unit": "mm", "accent": "#2563eb"},
            {
                "label": "Waktu perkiraan",
                "value": (prediction.get("forecast_time", "-") or "-").replace(" WIB", ""),
                "unit": "",
                "accent": "#475569",
            },
        ],
        columns=3,
    )

    section("Probabilitas tiap kelas cuaca")
    probabilities = prediction.get("probabilities_pct") or {}
    if probabilities:
        render_weather_probability_chart(probabilities, key="pred_page_prob")
    else:
        st.info("Probabilitas kelas cuaca belum tersedia.")

    section("Ambang batas & rekomendasi")
    st.markdown(
        f"""
        <div style="background:#ffffff;border:1px solid #e8edf4;border-radius:14px;
                    padding:1rem 1.15rem;box-shadow:0 1px 3px rgba(15,23,42,.04)">
        <table style="width:100%;border-collapse:collapse;font-size:.86rem">
            <thead>
                <tr style="background:#f0f7ff">
                    <th style="text-align:left;padding:.5rem;color:#0f172a">Indikator</th>
                    <th style="text-align:left;padding:.5rem;color:#0f172a">Waspada</th>
                    <th style="text-align:left;padding:.5rem;color:#0f172a">Bahaya</th>
                    <th style="text-align:left;padding:.5rem;color:#0f172a">Nilai prediksi</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">Suhu</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">{SUHU_PANAS_WASPADA} °C</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">{SUHU_PANAS_BAHAYA} °C</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4;font-weight:600;color:#2563eb">
                        {fmt(forecast.get("suhu"), 1)} °C
                    </td>
                </tr>
                <tr>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">Indeks THI</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">{THI_WASPADA}</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4">{THI_BAHAYA}</td>
                    <td style="padding:.45rem;border-top:1px solid #e8edf4;font-weight:600;color:#2563eb">
                        {fmt(prediction.get("thi_forecast"), 2)}
                    </td>
                </tr>
            </tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    info_panel(
        "Rekomendasi yang dihasilkan sistem",
        [item.replace("• ", "").strip() for item in (prediction.get("recommendations") or [])],
    )

    footer()
