"""Halaman monitoring PLTS off-grid."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from app_config import PLTS_PIPELINE_DIR
from plts_service import load_plts_prediction, plts_status_summary
from ui_components import (
    COLOR_ACCENT,
    COLOR_PRIMARY,
    fmt,
    footer,
    header,
    metric_row,
    plotly_chart,
    section,
    status_badge,
    style_figure,
)


def _run_local_predict() -> bool:
    try:
        import subprocess
        import sys

        predict_py = PLTS_PIPELINE_DIR / "predict.py"
        if not predict_py.exists():
            return False
        result = subprocess.run(
            [sys.executable, str(predict_py)],
            cwd=str(PLTS_PIPELINE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def render_plts_page() -> None:
    header(
        "Monitoring PLTS",
        "Kondisi operasional panel surya dan baterai 12V di lokasi off-grid",
    )

    col_a, _ = st.columns([1, 2])
    with col_a:
        if st.button("Perbarui data", use_container_width=True, type="secondary"):
            if _run_local_predict():
                st.success("Data PLTS berhasil diperbarui.")
            else:
                st.warning("Data belum dapat diperbarui. Coba lagi beberapa saat.")
            st.rerun()

    payload = load_plts_prediction()
    if payload is None:
        st.info(
            "Data monitoring PLTS belum tersedia. "
            "Pastikan modul PLTS telah dijalankan dan data sudah masuk ke sistem."
        )
        footer()
        return

    section("Kondisi operasional")
    alarm = bool(payload.get("alarm"))
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#eff6ff 0%,#ffffff 55%);
            border:1px solid #bfdbfe;border-radius:16px;padding:1.2rem 1.4rem;margin-bottom:.6rem">
            <div style="font-size:.75rem;color:#1d4ed8;text-transform:uppercase;letter-spacing:.05em">
                Status saat ini
            </div>
            <div style="font-size:2rem;font-weight:700;color:#1e3a8a;line-height:1.2">
                {payload.get('icon', '')} {payload.get('predicted_class', '-')}
            </div>
            <div style="font-size:.85rem;color:#64748b">
                Pembaruan: {payload.get('timestamp_wib', '-')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    status_badge(
        "Perhatian diperlukan" if alarm else "Operasi normal",
        "danger" if alarm else "success",
    )
    st.caption(plts_status_summary(payload))

    tele = payload.get("telemetry") or {}
    section("Parameter listrik")
    metric_row(
        [
            {"label": "Tegangan", "value": fmt(tele.get("V"), 2), "unit": "V", "accent": COLOR_PRIMARY},
            {"label": "Arus", "value": fmt(tele.get("I"), 3), "unit": "A", "accent": "#0ea5e9"},
            {"label": "Daya", "value": fmt(tele.get("P"), 2), "unit": "W", "accent": "#3b82f6"},
            {
                "label": "Rata-rata daya",
                "value": fmt(tele.get("P_mean_w"), 2),
                "unit": "W",
                "accent": COLOR_ACCENT,
            },
            {
                "label": "Variabilitas daya",
                "value": fmt(tele.get("P_std_w"), 4),
                "unit": "W",
                "accent": "#60a5fa",
            },
        ],
        columns=3,
    )

    probs = payload.get("probabilities_pct") or {}
    if probs:
        section("Tingkat keyakinan per kondisi")
        fig = px.bar(
            x=list(probs.keys()),
            y=list(probs.values()),
            labels={"x": "Kondisi", "y": "Probabilitas (%)"},
            color=list(probs.values()),
            color_continuous_scale=["#dbeafe", "#2563eb"],
        )
        fig.update_layout(showlegend=False, coloraxis_showscale=False)
        style_figure(fig, height=320)
        plotly_chart(fig, key="plts_prob_bar")

    if payload.get("disclaimer"):
        st.caption(payload["disclaimer"])

    footer()
