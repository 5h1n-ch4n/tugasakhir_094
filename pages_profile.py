"""Halaman profil pengguna."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import streamlit as st

from profile_service import (
    age_from_birth_date,
    avatar_color,
    clear_photo,
    decode_photo,
    encode_photo,
    initials,
    load_profile,
    profile_summary,
    save_profile,
)
from ui_components import footer, header, metric_row, section

WIB_OFFSET = timezone(timedelta(hours=7))


def _avatar_html(profile: dict, size: int = 120) -> str:
    photo = decode_photo(profile.get("photo_b64", ""))
    name = profile.get("full_name") or profile.get("display_name") or "?"
    color = avatar_color(name)

    if photo:
        encoded = base64.b64encode(photo).decode("ascii")
        inner = (
            f'<img src="data:image/jpeg;base64,{encoded}" '
            f'style="width:100%;height:100%;object-fit:cover;display:block;" />'
        )
    else:
        label = initials(name)
        inner = (
            f'<div style="width:100%;height:100%;display:flex;align-items:center;'
            f'justify-content:center;font-size:{max(28, size // 2)}px;font-weight:800;'
            f'color:#ffffff;letter-spacing:.02em;">{label}</div>'
        )

    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;overflow:hidden;'
        f'background:{color};box-shadow:0 10px 30px rgba(37,99,235,.12);'
        f'border:3px solid #ffffff;flex-shrink:0;">{inner}</div>'
    )


def _identity_card(profile: dict) -> None:
    name = profile.get("full_name") or profile.get("display_name") or "Pengguna"
    place = profile.get("birth_place") or "-"
    birth = profile.get("birth_date") or ""
    age = age_from_birth_date(str(birth))

    birth_line = "-"
    if birth:
        age_text = f" · {age} tahun" if age is not None else ""
        birth_line = f"{birth}{age_text}"

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#ffffff 0%,#f0f9ff 100%);
            border:1px solid #e8edf4;border-radius:16px;padding:1.8rem 1.4rem;
            text-align:center;box-shadow:0 4px 24px rgba(37,99,235,.06);">
            <div style="display:flex;justify-content:center;margin-bottom:1rem;">
                {_avatar_html(profile, 120)}
            </div>
            <div style="font-size:1.2rem;font-weight:700;color:#1e3a8a;margin-bottom:.25rem;">
                {name}
            </div>
            <div style="font-size:.85rem;color:#64748b;margin-bottom:1rem;">
                {profile.get('display_name', '-')}
            </div>
            <div style="border-top:1px solid #e8edf4;padding-top:.9rem;font-size:.83rem;
                color:#475569;line-height:1.65;text-align:left;">
                <div>Tempat lahir: {place}</div>
                <div>Tanggal lahir: {birth_line}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_profile_page() -> None:
    header("Profil", "Kelola identitas dan preferensi akun Anda")

    user = st.session_state.get("user", {})
    email = user.get("email", "")
    profile = load_profile(email, user.get("display_name", ""))

    left, right = st.columns([1, 1.6], gap="large")

    with left:
        _identity_card(profile)

        st.markdown("##### Foto profil")
        uploaded = st.file_uploader(
            "Unggah foto (JPG/PNG, maks. 5 MB)",
            type=["jpg", "jpeg", "png", "webp"],
            key="avatar_upload",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Simpan foto", use_container_width=True, key="btn_save_photo"):
                if uploaded is None:
                    st.warning("Pilih berkas foto terlebih dahulu.")
                else:
                    encoded, error = encode_photo(uploaded.getvalue())
                    if error:
                        st.error(error)
                    else:
                        save_profile(email, {"photo_b64": encoded})
                        st.success("Foto profil berhasil disimpan.")
                        st.rerun()
        with col_b:
            if profile.get("photo_b64"):
                if st.button("Hapus foto", use_container_width=True, key="btn_clear_photo"):
                    clear_photo(email)
                    st.success("Foto profil dihapus.")
                    st.rerun()

    with right:
        section("Ubah identitas")
        with st.form("form_profile", clear_on_submit=False):
            col_name, col_display = st.columns(2)
            with col_name:
                new_full_name = st.text_input(
                    "Nama lengkap",
                    value=profile.get("full_name", ""),
                    max_chars=64,
                    placeholder="Contoh: Haikal Karim",
                )
            with col_display:
                new_display_name = st.text_input(
                    "Nama tampilan",
                    value=profile.get("display_name", ""),
                    max_chars=32,
                    placeholder="Contoh: Haikal",
                )

            col_place, col_date = st.columns(2)
            with col_place:
                new_place = st.text_input(
                    "Tempat lahir",
                    value=profile.get("birth_place", ""),
                    max_chars=64,
                    placeholder="Contoh: Semarang",
                )
            with col_date:
                new_birth = st.text_input(
                    "Tanggal lahir",
                    value=str(profile.get("birth_date", "")),
                    max_chars=10,
                    placeholder="YYYY-MM-DD",
                    help="Format: Tahun-Bulan-Hari",
                )

            submitted = st.form_submit_button(
                "Simpan perubahan", type="primary", use_container_width=True
            )

        if submitted:
            birth = new_birth.strip()
            if birth:
                try:
                    datetime.strptime(birth, "%Y-%m-%d")
                except ValueError:
                    st.error("Format tanggal lahir tidak valid. Gunakan YYYY-MM-DD.")
                    birth = None

            if birth is not None:
                saved = save_profile(
                    email,
                    {
                        "full_name": new_full_name.strip(),
                        "display_name": new_display_name.strip() or new_full_name.strip(),
                        "birth_place": new_place.strip(),
                        "birth_date": birth,
                    },
                )
                st.session_state["user"] = {
                    **user,
                    "display_name": saved.get("display_name", user.get("display_name")),
                }
                st.success("Profil berhasil diperbarui.")
                st.rerun()

    st.divider()

    section("Ringkasan akun")
    age = age_from_birth_date(str(profile.get("birth_date", "")))
    metric_row(
        [
            {"label": "Nama lengkap", "value": profile.get("full_name", "-"), "unit": ""},
            {"label": "Nama tampilan", "value": profile.get("display_name", "-"), "unit": ""},
            {"label": "Tempat lahir", "value": profile.get("birth_place", "-"), "unit": ""},
            {
                "label": "Usia",
                "value": f"{age}" if age is not None else "-",
                "unit": " tahun" if age is not None else "",
            },
            {"label": "Surel", "value": user.get("email", "-"), "unit": ""},
        ],
        columns=3,
    )
    summary = profile_summary(profile)
    if summary:
        st.caption(summary)

    st.divider()

    section("Sesi")
    st.caption(
        f"Terakhir diperbarui: {datetime.now(WIB_OFFSET).strftime('%d %b %Y, %H:%M')} WIB"
    )
    if st.button("Keluar dari akun", type="secondary", use_container_width=True):
        for key in ("user", "auth_ok"):
            st.session_state.pop(key, None)
        st.rerun()

    footer()
