"""
Coop Master — Smart Poultry & Energy Management (Streamlit).

Aplikasi web untuk memantau kondisi cuaca mikro di kandang ayam pejantan
berdasarkan data Automatic Weather Station (ESP32) yang dikirim ke Firebase
Realtime Database, sekaligus menampilkan hasil prediksi Support Vector Machine
yang dihitung otomatis oleh pipeline Python melalui GitHub Actions.

Struktur aplikasi:
    app.py              -> entry point & routing halaman
    app_config.py       -> konfigurasi & path
    firebase_client.py  -> akses Firebase Realtime Database (REST)
    auth_service.py     -> autentikasi (Firebase Auth / lokal)
    data_service.py     -> perhitungan domain (THI, rekomendasi)
    station_service.py  -> manajemen stasiun AWS
    ui_components.py    -> komponen tampilan
    pages_*.py          -> halaman: auth, dashboard, prediksi, riwayat, AWS, profil

Jalankan:
    streamlit run app.py
"""

from __future__ import annotations

import base64

import streamlit as st

from app_config import APP_ICON, APP_SUBTITLE, APP_TITLE
from pages_auth import render_auth_page
from pages_dashboard import render_dashboard
from pages_history import render_history_page
from pages_prediction import render_prediction_page
from pages_plts import render_plts_page
from pages_profile import render_profile_page
from pages_stations import render_stations_page
from profile_service import avatar_color, decode_photo, initials, load_profile
from ui_components import inject_style, sidebar_brand, sidebar_footer, sidebar_user_card

PAGES = {
    "Dashboard": render_dashboard,
    "Prediksi Cuaca": render_prediction_page,
    "Monitoring PLTS": render_plts_page,
    "Riwayat Data": render_history_page,
    "Manajemen Lokasi": render_stations_page,
    "Profil": render_profile_page,
}


def _sidebar_avatar_html(profile: dict, user: dict) -> str:
    """Potongan HTML avatar untuk kartu sidebar."""
    name = profile.get("display_name") or user.get("display_name", "Pengguna")
    color = avatar_color(name)
    photo = decode_photo(profile.get("photo_b64", ""))

    if photo:
        encoded = base64.b64encode(photo).decode("ascii")
        return (
            f'<img src="data:image/jpeg;base64,{encoded}" '
            f'style="width:42px;height:42px;border-radius:50%;object-fit:cover;flex-shrink:0;" />'
        )
    return (
        f'<div style="width:42px;height:42px;border-radius:50%;background:{color};'
        f'display:flex;align-items:center;justify-content:center;color:#fff;'
        f'font-weight:700;font-size:.9rem;flex-shrink:0;">{initials(name)}</div>'
    )


def main() -> None:
    """Titik masuk utama aplikasi."""
    st.set_page_config(
        page_title=f"{APP_TITLE} — Smart Poultry & Energy",
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_style()

    if not st.session_state.get("auth_ok"):
        render_auth_page()
        return

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    user = st.session_state.get("user", {})
    profile = load_profile(user.get("email", ""), user.get("display_name", ""))
    with st.sidebar:
        sidebar_brand(APP_TITLE, APP_SUBTITLE, APP_ICON)
        name = profile.get("display_name") or user.get("display_name", "Pengguna")
        email = user.get("email", "")
        sidebar_user_card(name, email, _sidebar_avatar_html(profile, user))
        st.markdown('<div class="sidebar-nav-label">Menu</div>', unsafe_allow_html=True)
        page_label = st.radio(
            "Menu navigasi",
            options=list(PAGES.keys()),
            key="active_page",
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("Keluar", use_container_width=True, type="secondary"):
            for key in ("user", "auth_ok"):
                st.session_state.pop(key, None)
            st.rerun()
        sidebar_footer()

    PAGES[page_label]()


if __name__ == "__main__":
    main()
