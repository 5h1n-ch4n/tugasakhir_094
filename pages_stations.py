"""Halaman manajemen lokasi pemantauan cuaca (AWS)."""

from __future__ import annotations

import streamlit as st

from station_service import (
    delete_station,
    load_stations,
    toggle_station,
    upsert_station,
)
from ui_components import footer, header, section


def render_stations_page() -> None:
    header(
        "Manajemen Lokasi",
        "Kelola lokasi pemantauan cuaca mikro di kandang ayam pejantan",
    )

    stations = load_stations()

    section("Lokasi terdaftar")
    if not stations:
        st.info("Belum ada lokasi. Tambahkan melalui formulir di bawah.")
    else:
        st.dataframe(
            [
                {
                    "Nama": station.get("nama") or station.get("station_id", "-"),
                    "Lokasi": station.get("lokasi", "-"),
                    "Objek": station.get("objek", "-"),
                    "Status": "Aktif" if station.get("aktif", True) else "Nonaktif",
                    "Diperbarui": station.get("updated_at", "-"),
                }
                for station in stations
            ],
            use_container_width=True,
            hide_index=True,
        )

        for station in stations:
            station_id = station.get("station_id", "")
            label = station.get("nama") or station_id
            with st.expander(f"Pengaturan — {label}"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    aktif = station.get("aktif", True)
                    btn_label = "Nonaktifkan" if aktif else "Aktifkan"
                    if st.button(
                        btn_label,
                        key=f"toggle_{station_id}",
                        use_container_width=True,
                    ):
                        toggle_station(station_id)
                        st.rerun()
                with col_b:
                    if st.button(
                        "Hapus",
                        key=f"del_{station_id}",
                        use_container_width=True,
                    ):
                        delete_station(station_id)
                        st.rerun()
                with col_c:
                    st.caption(f"Status: {'Aktif' if aktif else 'Nonaktif'}")

    st.divider()

    section("Tambah atau ubah lokasi")
    default_id = stations[0]["station_id"] if stations else "AWS_TPST_VC"
    with st.form("form_station", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            kode = st.text_input(
                "Kode lokasi",
                value=default_id,
                help="Gunakan kode unik, contoh: AWS_TPST_VC",
            )
            nama = st.text_input("Nama tampilan", value="")
            lokasi = st.text_input("Alamat / lokasi", value="")
        with col2:
            objek = st.text_input("Objek pemantauan", value="Kandang Ayam Pejantan")
            deskripsi = st.text_area("Catatan", value="", placeholder="Opsional")
            aktif = st.checkbox("Aktif", value=True)

        submitted = st.form_submit_button(
            "Simpan lokasi", type="primary", use_container_width=True
        )

    if submitted:
        kode = kode.strip()
        if not kode:
            st.error("Kode lokasi wajib diisi.")
        else:
            try:
                upsert_station(
                    {
                        "station_id": kode,
                        "nama": nama.strip() or kode,
                        "lokasi": lokasi.strip() or "-",
                        "objek": objek.strip() or "Kandang Ayam Pejantan",
                        "deskripsi": deskripsi.strip() or "-",
                        "aktif": aktif,
                    }
                )
                st.success(f"Lokasi {nama.strip() or kode} berhasil disimpan.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    footer()
