"""Halaman autentikasi: masuk, daftar, dan reset kata sandi."""

from __future__ import annotations

import streamlit as st

from auth_service import AuthError, AuthService
from ui_components import footer, inject_style


def _init_service() -> AuthService:
    if "auth_service" not in st.session_state:
        st.session_state["auth_service"] = AuthService()
    return st.session_state["auth_service"]


def render_auth_page() -> None:
    inject_style()
    service = _init_service()

    left, center, right = st.columns([1, 1.35, 1])
    with center:
        st.markdown(
            """
            <div style="text-align:center;margin-bottom:1.2rem;padding:1rem 0">
                <div style="width:56px;height:56px;margin:0 auto .75rem;
                    background:linear-gradient(135deg,#2563eb,#60a5fa);
                    border-radius:14px;display:flex;align-items:center;justify-content:center;
                    font-size:1.5rem;color:#fff;font-weight:700">CM</div>
                <h2 style="margin:0;color:#1e3a8a;font-weight:700;font-size:1.65rem">
                    Coop Master
                </h2>
                <p style="color:#64748b;margin:.35rem 0 0 0;font-size:.9rem;line-height:1.5">
                    Pemantauan cuaca mikro kandang<br/>dan energi PLTS off-grid
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_daftar, tab_lupa = st.tabs(["Masuk", "Daftar", "Lupa kata sandi"])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                email = st.text_input("Surel", key="login_email", placeholder="nama@domain.com")
                password = st.text_input(
                    "Kata sandi", type="password", key="login_password"
                )
                submitted = st.form_submit_button("Masuk", type="primary", use_container_width=True)

            if submitted:
                try:
                    ok, message, user = service.sign_in(email, password)
                except AuthError as exc:
                    ok, message, user = False, str(exc), {}
                if ok:
                    st.session_state["user"] = user
                    st.session_state["auth_ok"] = True
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

        with tab_daftar:
            with st.form("form_daftar", clear_on_submit=False):
                email = st.text_input("Surel", key="signup_email", placeholder="nama@domain.com")
                password = st.text_input(
                    "Kata sandi",
                    type="password",
                    key="signup_password",
                    help="Minimal 6 karakter, memuat huruf dan angka.",
                )
                confirm = st.text_input(
                    "Konfirmasi kata sandi", type="password", key="signup_confirm"
                )
                submitted = st.form_submit_button("Daftar", type="primary", use_container_width=True)

            if submitted:
                try:
                    ok, message, user = service.sign_up(email, password, confirm)
                except AuthError as exc:
                    ok, message, user = False, str(exc), {}
                if ok:
                    st.success(message)
                    st.session_state["user"] = user
                    st.session_state["auth_ok"] = True
                    st.rerun()
                else:
                    st.error(message)

        with tab_lupa:
            st.markdown(
                """
                <p style="font-size:.86rem;color:#475569;margin:.1rem 0 .8rem 0;line-height:1.5">
                Masukkan surel terdaftar. Tautan atau token reset akan dikirim ke surel Anda.
                </p>
                """,
                unsafe_allow_html=True,
            )
            with st.form("form_lupa", clear_on_submit=False):
                email = st.text_input("Surel", key="reset_email", placeholder="nama@domain.com")
                submitted = st.form_submit_button(
                    "Kirim instruksi reset", type="primary", use_container_width=True
                )

            if submitted:
                try:
                    ok, message = service.request_password_reset(email)
                except AuthError as exc:
                    ok, message = False, str(exc)
                if ok:
                    st.success(message)
                    st.session_state["reset_email_sent"] = email
                else:
                    st.error(message)

            if st.session_state.get("reset_email_sent"):
                st.divider()
                st.markdown("##### Atur kata sandi baru")
                with st.form("form_reset_baru", clear_on_submit=False):
                    token = st.text_input("Token reset", key="reset_token")
                    baru = st.text_input("Kata sandi baru", type="password", key="reset_new")
                    konfirmasi = st.text_input(
                        "Konfirmasi kata sandi baru", type="password", key="reset_confirm"
                    )
                    submitted = st.form_submit_button(
                        "Perbarui kata sandi", type="primary", use_container_width=True
                    )
                if submitted:
                    try:
                        ok, message = service.reset_password(token, baru, konfirmasi)
                    except AuthError as exc:
                        ok, message = False, str(exc)
                    if ok:
                        st.success(message)
                        st.session_state.pop("reset_email_sent", None)
                    else:
                        st.error(message)

    footer()
