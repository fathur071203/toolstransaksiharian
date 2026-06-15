"""Halaman Ekspor — 3 section: Word (Laporan Harian), Excel per Entitas, Excel Transaksi.
Halaman ini TIDAK memakai filter bar global; kontrol seperlunya ada di dalam tab.
Saat ini yang aktif: Laporan Word Harian (periode dikunci Harian otomatis)."""
import pandas as pd
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth, page_header, no_data_card, section_title

require_auth()
page_header("📄", "Ekspor Laporan",
            "Susun & unduh laporan pengawasan KUPVA — Word & Excel")

data = E.get_data()
if data is None:
    no_data_card()
    st.stop()

cb = data["combine"]
hari_tersedia = E.daftar_tanggal(cb)
vals_all = E.daftar_valuta(cb)
pts_all = E.daftar_pt(cb)

tab_word, tab_entitas, tab_trx = st.tabs(
    ["📄 Word — Laporan Harian", "📊 Excel — Per Entitas", "📑 Excel — Transaksi"]
)

# ============================================================================
# SECTION 1 — Laporan Word Harian (AKTIF). Periode selalu 'Harian'.
# ============================================================================
with tab_word:
    st.caption("Laporan **Monitoring Harian Transaksi KUPVA** (.docx) sesuai template KPwDN BI. "
               "Periode laporan **otomatis Harian** — cukup pilih tanggal & cakupannya.")

    with st.container(border=True):
        section_title("Pengaturan laporan harian")
        r1 = st.columns([1.4, 1.3, 1.3])
        tgl = r1[0].selectbox("📅 Tanggal laporan (harian)", options=hari_tersedia,
                              index=len(hari_tersedia) - 1, format_func=E.fmt_tgl, key="lap_tgl")
        provinsi = r1[1].text_input("KPwDN Provinsi", value="DKI Jakarta", key="lap_prov")
        kota = r1[2].text_input("Kota pengesahan", value="Jakarta", key="lap_kota")

        st.caption("**Lembar pengesahan** (opsional) — peran = teks bebas; nama & jabatan = dropdown.")
        NAMA_OPTS = ["—"] + [
            "A'thinih Sufiyati", "Achnesia Frans", "Adhityas Ghaniyya Tejo", "Akmal",
            "Alya Q.D. Susanto", "Anindya Aldora Nahar Mahsun", "Argi Muhammad Seto",
            "Arif Waluyo Birowo", "Astri Apriliani", "Cici Amelia Azwen", "Dini Agustini",
            "Dyas Wicaksono", "Fathya Annasya Yuzrin", "Fikri Mauli Utomo", "Hafidh Afif Ardhi",
            "Hanan Qisthina Sindi", "Ivan Aprianto", "Leni Resti Purwanti",
            "Mahesti Ayu Indira Harahap", "Maritza Aulia S Silitonga", "Muhammad Fathurrahman",
            "Nur Anisa Junus", "Otto Iskandar Winata", "Saadiah Ludmilla", "Salma Athira Rahman",
            "Sarwoto", "Tatag Budiarto A", "Vita Cahyaningtyas", "Yudhistira Tegar Setiawan",
        ]
        JABATAN_OPTS = ["Staf", "Asisten Manajer", "Manajer", "Asisten Direktur",
                        "Deputi Direktur", "Direktur", "Kepala Perwakilan"]
        _roles = [("Dipersiapkan oleh", "Pelaksana", "Staf"),
                  ("Diperiksa oleh", "Pengawas Senior", "Asisten Direktur"),
                  ("Didukung oleh", "Pengawas Senior", "Asisten Direktur"),
                  ("Disetujui oleh", "Pengawas Eksekutif", "Deputi Direktur")]
        cps = st.columns(4)
        pengesahan = []
        for i, (hdr, peran_def, jab_def) in enumerate(_roles):
            with cps[i]:
                st.markdown(f"**{hdr}**")
                peran = st.text_input("Peran", value=peran_def, key=f"lap_peran_{i}")
                nm = st.selectbox("Nama", NAMA_OPTS, key=f"lap_nm_{i}")
                jb = st.selectbox("Jabatan", JABATAN_OPTS,
                                  index=JABATAN_OPTS.index(jab_def), key=f"lap_jb_{i}")
            pengesahan.append((hdr, peran, "" if nm == "—" else nm, jb))

        # Laporan bersifat UMUM → seluruh valuta, tanpa valuta fokus/dipantau.
        valutas = list(vals_all)
        valuta_fokus = "USD" if "USD" in vals_all else (vals_all[0] if vals_all else "USD")
        st.caption("Laporan bersifat **umum**: mencakup **seluruh valuta** yang ditransaksikan "
                   "(tanpa valuta dipantau/fokus). Pembanding = hari transaksi sebelumnya (otomatis); "
                   "cakupan = seluruh KUPVA BB. Field pengesahan opsional (untuk Lembar Pengesahan).")

    # ---- Konteks HARIAN (tanpa filter bar global) ----
    opsi_p = [d for d in hari_tersedia if pd.Timestamp(d) < pd.Timestamp(tgl)] or hari_tersedia
    ctx_harian = E.Konteks(
        data=data, tgl_h=pd.Timestamp(tgl), tgl_p=pd.Timestamp(opsi_p[-1]),
        tgl_awal=pd.Timestamp(hari_tersedia[0]), valutas=valutas, pts=pts_all,
        ambang_rasio=E.AMBANG_RASIO_DEFAULT, ambang_dtd=E.AMBANG_DTD_DEFAULT,
        valuta_fokus=valuta_fokus, nama_map=data["nama_map"], granularitas="Harian",
    )

    # ---- pratinjau ----
    absn = E.tabel_absensi(data, ctx_harian.tgl_h, ctx_harian.pts, gran="Harian")
    n_lapor = int((absn["Status"] == "Lengkap").sum())
    mtx = E.matriks_per_kupva(data, ctx_harian.valuta_fokus, ctx_harian.valutas,
                              ctx_harian.tgl_h, ctx_harian.tgl_p, ctx_harian.pts,
                              ctx_harian.ambang_rasio, ctx_harian.ambang_dtd, gran="Harian")
    tot_vol = E.volume_total(cb, ctx_harian.tgl_h, valutas=None, pts=ctx_harian.pts, gran="Harian")

    with st.container(border=True):
        section_title(f"Pratinjau · {E.fmt_tgl(tgl)}")
        k = st.columns(4)
        k[0].metric("KUPVA lapor", f"{n_lapor}/{len(absn)}")
        k[1].metric("Total volume H", E.rupiah(tot_vol))
        k[2].metric("Waspada kurs", int((mtx["Status Kurs"] == "Waspada").sum()))
        k[3].metric("Waspada volume", int((mtx["Status Volume"] == "Waspada").sum()))
        st.markdown("Struktur (4 halaman): **Bagian 1** Objek Monitoring & Absensi (donat + Tabel "
                    "1.1/1.2) · **Bagian 2** Kurs (Grafik 2.1/2.2 + Tabel 2.1) · **Bagian 3** Jumlah "
                    "Transaksi (Grafik 3.1/3.2 + Tabel 3.1) · **Bagian 4** Supervisory Action (Tabel 4.1 "
                    "+ tindakan) · **Lembar Pengesahan** (4 peran).")

    if st.button("🛠️ Susun laporan Word", type="primary", use_container_width=True, key="lap_build"):
        try:
            import importlib
            import core.report as _rpt
            importlib.reload(_rpt)  # pastikan memakai versi terbaru report.py
            with st.spinner("Menyusun laporan & grafik…"):
                st.session_state["laporan_bytes"] = _rpt.build_report(
                    ctx_harian, provinsi=provinsi, kota=kota, pengesahan=pengesahan)
                st.session_state["laporan_nama"] = (
                    f"Laporan_Monitoring_Harian_KUPVA_{E.fmt_tgl(tgl)}.docx".replace(" ", "_")
                )
            st.success("✅ Laporan siap diunduh.")
        except Exception as e:  # noqa
            st.error(f"Gagal menyusun laporan: {e}")

    if st.session_state.get("laporan_bytes"):
        st.download_button(
            "⬇️ Unduh laporan (.docx)",
            data=st.session_state["laporan_bytes"],
            file_name=st.session_state.get("laporan_nama", "Laporan_Monitoring_Harian_KUPVA.docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.caption("Jika tanggal/cakupan diubah, klik **Susun laporan Word** lagi.")

# ============================================================================
# SECTION 2 — Excel per Entitas (KERANGKA, segera)
# ============================================================================
with tab_entitas:
    st.info("📊 **Laporan Excel Setiap Entitas** — sedang disiapkan. "
            "Akan mengekspor satu workbook berisi ringkasan per KUPVA BB "
            "(volume, kurs, status) pada periode terpilih.", icon="🚧")

# ============================================================================
# SECTION 3 — Excel Transaksi (KERANGKA, segera)
# ============================================================================
with tab_trx:
    st.info("📑 **Excel Transaksi** — sedang disiapkan. "
            "Akan mengekspor data transaksi mentah (sheet Combine) terfilter sesuai "
            "tanggal, valuta, dan KUPVA terpilih.", icon="🚧")
