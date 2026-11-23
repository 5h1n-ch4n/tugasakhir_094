"""
Komponen antarmuka yang dipakai bersama seluruh halaman aplikasi.

Berisi: tema warna, kartu metrik, grafik, lencana status, dan utilitas
tampilan tabel serta pesan.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Palet warna
# ---------------------------------------------------------------------------
COLOR_PRIMARY = "#1e40af"
COLOR_ACCENT = "#0ea5e9"
COLOR_BG_SOFT = "#f0f9ff"
COLOR_TEXT = "#1e293b"
COLOR_MUTED = "#64748b"

STATUS_COLOR = {
    "success": "#16a34a",
    "warning": "#f59e0b",
    "danger": "#dc2626",
    "unknown": "#6b7280",
    "info": "#2563eb",
}


def inject_style() -> None:
    """Sisipkan CSS kustom untuk tampilan yang konsisten."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp {
            background: #f4f7fb;
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e8edf4;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.25rem;
        }
        .block-container {
            padding-top: 1.5rem;
            max-width: 1200px;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
        }
        .coop-header, .haikal-header {
            background: transparent;
            padding: 0 0 1.25rem 0;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid #e8edf4;
        }
        .coop-header h1, .haikal-header h1 {
            margin: 0;
            font-size: 1.45rem;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.02em;
        }
        .coop-header p, .haikal-header p {
            margin: 0.35rem 0 0 0;
            font-size: 0.88rem;
            color: #64748b;
        }
        .sidebar-brand {
            text-align: center;
            padding: 0.25rem 0.5rem 1rem 0.5rem;
            border-bottom: 1px solid #eef2f7;
            margin-bottom: 1rem;
        }
        .sidebar-brand .logo { font-size: 2rem; line-height: 1; }
        .sidebar-brand .title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #1e3a8a;
            margin: 0.35rem 0 0.15rem 0;
        }
        .sidebar-brand .tagline {
            font-size: 0.72rem;
            color: #64748b;
            line-height: 1.35;
            margin: 0;
        }
        .sidebar-user-card {
            background: #f8fafc;
            border: 1px solid #e8edf4;
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin: 0 0 1rem 0;
        }
        .sidebar-user-card .name { font-weight: 600; color: #0f172a; font-size: 0.92rem; }
        .sidebar-user-card .email { font-size: 0.75rem; color: #64748b; margin-top: 0.15rem; }
        .sidebar-nav-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #94a3b8;
            margin: 0.5rem 0 0.35rem 0.25rem;
            font-weight: 600;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            background: transparent !important;
            border-radius: 10px !important;
            padding: 0.45rem 0.65rem !important;
            margin: 2px 0 !important;
            border: 1px solid transparent !important;
            font-weight: 500 !important;
            color: #334155 !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #eff6ff !important;
            border-color: #bfdbfe !important;
            color: #1d4ed8 !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {
            display: none !important;
        }
        .sidebar-footer {
            font-size: 0.7rem;
            color: #94a3b8;
            text-align: center;
            margin-top: 1.5rem;
            padding: 0.5rem 0;
            line-height: 1.4;
        }
        .metric-card {
            background: #ffffff;
            border: 1px solid #e8edf4;
            border-left: 4px solid #2563eb;
            border-radius: 12px;
            padding: 1rem 1.1rem;
            height: 100%;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }
        .metric-card .label {
            font-size: 0.75rem;
            color: #64748b;
            font-weight: 500;
            margin-bottom: 0.35rem;
        }
        .metric-card .value {
            font-size: 1.55rem;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.15;
        }
        .metric-card .unit {
            font-size: 0.88rem;
            color: #64748b;
            margin-left: 0.15rem;
            font-weight: 500;
        }
        .metric-card .desc {
            font-size: 0.74rem;
            color: #94a3b8;
            margin-top: 0.35rem;
        }
        .status-badge {
            display: inline-block;
            padding: 0.32rem 0.85rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #ffffff;
        }
        .info-panel {
            background: #f8fafc;
            border: 1px solid #e8edf4;
            border-radius: 12px;
            padding: 1rem 1.15rem;
            margin-bottom: 0.8rem;
        }
        .info-panel h4 {
            margin: 0 0 0.5rem 0;
            font-size: 0.92rem;
            color: #0f172a;
            font-weight: 600;
        }
        .info-panel p {
            margin: 0.25rem 0;
            font-size: 0.86rem;
            color: #475569;
            line-height: 1.5;
        }
        .pred-hero {
            background: #ffffff;
            border: 1px solid #e8edf4;
            border-radius: 14px;
            padding: 1.25rem 1.35rem;
        }
        .pred-hero .eyebrow {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            font-weight: 600;
        }
        .pred-hero .class-name {
            font-size: 2rem;
            font-weight: 700;
            color: #1e40af;
            margin: 0.35rem 0 0.5rem 0;
        }
        .pred-hero .meta {
            font-size: 0.82rem;
            color: #64748b;
            line-height: 1.55;
        }
        div[data-testid="stMetricValue"] { font-size: 1.45rem; }
        .block-container h1, .block-container h2, .block-container h3 { color: #0f172a; }
        .block-container h3 { font-size: 1.05rem; font-weight: 600; margin-top: 1.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand(title: str, subtitle: str, logo: str = "🐔") -> None:
    """Blok branding di sidebar (seperti referensi desain Coop Master)."""
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="logo">{logo}</div>
            <div class="title">{title}</div>
            <p class="tagline">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_user_card(name: str, email: str, avatar_html: str = "") -> None:
    """Kartu pengguna ringkas di sidebar."""
    avatar = avatar_html or (
        '<div style="width:42px;height:42px;border-radius:50%;background:#dbeafe;'
        'display:flex;align-items:center;justify-content:center;color:#1e40af;'
        'font-weight:700;font-size:.85rem;">H</div>'
    )
    st.sidebar.markdown(
        f"""
        <div class="sidebar-user-card">
            <div style="display:flex;align-items:center;gap:0.65rem">
                {avatar}
                <div style="min-width:0;">
                    <div class="name">{name}</div>
                    <div class="email">{email}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_footer(text: str = "v1.0 • Cuaca AWS + PLTS Off-Grid") -> None:
    """Teks versi di bagian bawah sidebar."""
    st.sidebar.markdown(f'<div class="sidebar-footer">{text}</div>', unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    """Tampilkan headergradient di bagian atas halaman."""
    st.markdown(
        f"""
        <div class="coop-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: Any, unit: str = "", desc: str = "", accent: str = COLOR_PRIMARY) -> None:
    """Tampilkan satu kartu metrik kustom."""
    st.markdown(
        f"""
        <div class="metric-card" style="border-left-color:{accent}">
            <div class="label">{label}</div>
            <div class="value">{value}<span class="unit">{unit}</span></div>
            <div class="desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_row(items: List[Dict[str, Any]], columns: int = 4) -> None:
    """Tampilkan sekumpulan kartu metrik dalam jumlah kolom tertentu."""
    if not items:
        return
    cols = st.columns(columns)
    for index, item in enumerate(items):
        with cols[index % columns]:
            metric_card(
                label=item.get("label", "-"),
                value=item.get("value", "-"),
                unit=item.get("unit", ""),
                desc=item.get("desc", ""),
                accent=item.get("accent", COLOR_PRIMARY),
            )


def status_badge(status: str, level: str = "info") -> None:
    """Tampilkan lencana status berwarna."""
    color = STATUS_COLOR.get(level, COLOR_ACCENT)
    st.markdown(
        f'<span class="status-badge" style="background:{color}">{status}</span>',
        unsafe_allow_html=True,
    )


def info_panel(title: str, paragraphs: Iterable[str]) -> None:
    """Tampilkan panel informasi berisi paragraf singkat."""
    body = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    st.markdown(
        f'<div class="info-panel"><h4>{title}</h4>{body}</div>',
        unsafe_allow_html=True,
    )


def footer() -> None:
    """Footer minimal (disembunyikan agar tampilan lebih bersih)."""
    return


def fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    """Format angka dengan jumlah desimal tertentu."""
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def section(title: str, icon: str = "") -> None:
    """Judul bagian; ikon opsional (default tanpa ikon untuk tampilan bersih)."""
    if icon:
        st.markdown(f"### {icon} {title}")
    else:
        st.markdown(f"### {title}")


def plotly_chart(fig, key: Optional[str] = None) -> None:
    """Tampilkan grafik plotly dengan konfigurasi seragam."""
    st.plotly_chart(fig, use_container_width=True, key=key)


def style_figure(fig, height: int = 380):
    """Terapkan tema plotly default aplikasi."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=40, r=20, t=40, b=35),
        font=dict(family="Inter, Segoe UI, Arial", size=12, color=COLOR_TEXT),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


CLASS_PROB_COLORS = ["#2563eb", "#0ea5e9", "#93c5fd", "#f59e0b", "#dc2626", "#64748b"]


def render_prediction_hero(prediction: Dict[str, Any]) -> None:
    """Kartu prediksi cuaca bergaya dashboard (tanpa detail teknis)."""
    icon = prediction.get("icon", "")
    cls = prediction.get("predicted_class", "-")
    obs = prediction.get("observation_time", "-")
    fc = prediction.get("forecast_time", "-")
    st.markdown(
        f"""
        <div class="pred-hero">
            <div class="eyebrow">Prediksi Cuaca</div>
            <div class="class-name">{icon} {cls}</div>
            <div class="meta">
                Observasi: {obs}<br/>
                Perkiraan: {fc}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_weather_probability_chart(
    probabilities: Dict[str, float],
    key: Optional[str] = None,
    title: str = "",
) -> None:
    """Grafik batang horizontal probabilitas kelas cuaca (label tidak bertumpuk)."""
    import plotly.express as px

    if not probabilities:
        return

    items = sorted(((k, float(v)) for k, v in probabilities.items()), key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    bar_height = max(280, 62 * len(labels))

    fig = px.bar(
        x=values,
        y=labels,
        orientation="h",
        labels={"x": "Probabilitas (%)", "y": ""},
        text=[f"{v:.2f}%" for v in values],
        title=title or None,
    )
    fig.update_traces(
        marker_color=[CLASS_PROB_COLORS[i % len(CLASS_PROB_COLORS)] for i in range(len(labels))],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
    )
    xmax = max(values) if values else 100.0
    fig.update_layout(
        xaxis=dict(range=[0, max(xmax * 1.28, 8)], title="Probabilitas (%)", gridcolor="#e5e7eb"),
        yaxis=dict(categoryorder="total ascending"),
        showlegend=False,
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        margin=dict(l=40, r=48, t=50 if title else 36, b=35),
    )
    style_figure(fig, height=bar_height)
    plotly_chart(fig, key=key)
