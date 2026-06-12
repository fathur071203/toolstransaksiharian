"""Halaman Tarik Kurs BI — unduh Kurs Transaksi BI & JISDOR langsung dari
web service Bank Indonesia (wskursbi) untuk rentang tanggal & mata uang pilihan,
lalu ekspor ke satu workbook Excel.

Halaman ini berdiri sendiri (tidak memakai data unggahan/filter bar global) —
sumber datanya adalah web service BI secara langsung."""
from datetime import date

import pandas as pd
import streamlit as st

import core.bi_kurs as BI
from core.ui_helpers import require_auth, page_header, section_title

require_auth()
page_header("🌐", "Tarik Kurs BI",
            "Unduh Kurs Transaksi BI & JISDOR dari web service Bank Indonesia")

# ----------------------------------------------------------------------------
# Pengaturan penarikan
# ----------------------------------------------------------------------------
with st.container(border=True):
    section_title("Pengaturan penarikan")

    r1 = st.columns([1, 1, 2])
    thn = date.today().year
    tgl_mulai = r1[0].date_input("📅 Tanggal mulai", value=date(thn, 1, 1),
                                 format="DD/MM/YYYY", key="bi_mulai")
    tgl_akhir = r1[1].date_input("📅 Tanggal akhir", value=date.today(),
                                 format="DD/MM/YYYY", key="bi_akhir")
    jenis = r1[2].multiselect(
        "📦 Jenis kurs",
        options=["Kurs Transaksi BI", "JISDOR"],
        default=["Kurs Transaksi BI", "JISDOR"],
        help="Kurs Transaksi BI = kurs beli/jual per valuta. "
             "JISDOR = kurs referensi (USD/IDR & valuta lain).",
        key="bi_jenis",
    )

    semua = st.checkbox("💱 Semua mata uang", value=True, key="bi_semua",
                        help=f"Tarik seluruh {len(BI.CURRENCIES)} mata uang yang disediakan BI.")
    if semua:
        codes = list(BI.CURRENCIES)
        st.caption(f"Akan menarik **semua** {len(codes)} mata uang: {', '.join(codes)}")
    else:
        _def = [c for c in ["USD", "SGD", "EUR"] if c in BI.CURRENCIES]
        codes = st.multiselect("Pilih mata uang", options=BI.CURRENCIES,
                               default=_def, key="bi_codes")

# ---- validasi ----
errs = []
if tgl_mulai > tgl_akhir:
    errs.append("Tanggal mulai tidak boleh setelah tanggal akhir.")
if not jenis:
    errs.append("Pilih minimal satu jenis kurs.")
if not codes:
    errs.append("Pilih minimal satu mata uang.")
for e in errs:
    st.warning(e, icon="⚠️")

tarik = st.button("⬇️ Tarik data dari BI", type="primary",
                  use_container_width=True, disabled=bool(errs), key="bi_tarik")

# ----------------------------------------------------------------------------
# Eksekusi penarikan
# ----------------------------------------------------------------------------
if tarik:
    s = tgl_mulai.strftime("%Y-%m-%d")
    e = tgl_akhir.strftime("%Y-%m-%d")
    sheets: dict[str, pd.DataFrame] = {}
    bar = st.progress(0.0, text="Menyiapkan…")

    def mk_progress(label: str):
        def _p(i: int, total: int, code: str):
            bar.progress(i / total, text=f"{label} — {code} ({i}/{total})")
        return _p

    try:
        if "Kurs Transaksi BI" in jenis:
            sheets["Kurs Transaksi"] = BI.tarik_kurs_transaksi(
                codes, s, e, progress=mk_progress("Kurs Transaksi"))
        if "JISDOR" in jenis:
            sheets["JISDOR"] = BI.tarik_jisdor(
                codes, s, e, progress=mk_progress("JISDOR"))
        bar.progress(1.0, text="Selesai.")

        st.session_state["bi_sheets"] = sheets
        st.session_state["bi_xlsx"] = BI.build_excel(sheets)
        st.session_state["bi_nama"] = (
            f"kurs_bi_{s}_sd_{e}.xlsx".replace("-", "")
        )
        st.success("✅ Data berhasil ditarik dari Bank Indonesia.")
    except Exception as exc:  # noqa: BLE001
        bar.empty()
        st.error(f"Gagal menarik data: {exc}")
        st.caption("Pastikan `curl` tersedia dan koneksi ke bi.go.id tidak terblokir.")

# ----------------------------------------------------------------------------
# Hasil & unduhan
# ----------------------------------------------------------------------------
sheets = st.session_state.get("bi_sheets")
if sheets:
    section_title("Hasil")

    metr = st.columns(len(sheets) + 1)
    for col, (nama, df) in zip(metr, sheets.items()):
        n_val = df["Kode"].nunique() if not df.empty else 0
        col.metric(nama, f"{len(df):,} baris", f"{n_val} valuta")
    metr[-1].download_button(
        "⬇️ Unduh Excel",
        data=st.session_state.get("bi_xlsx", b""),
        file_name=st.session_state.get("bi_nama", "kurs_bi.xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    tabs = st.tabs(list(sheets.keys()))
    for tab, (nama, df) in zip(tabs, sheets.items()):
        with tab:
            if df is None or df.empty:
                st.info(f"Tidak ada data {nama} pada rentang/valuta terpilih "
                        "(BI tidak menerbitkan kurs di akhir pekan/hari libur).")
            else:
                st.dataframe(df, width="stretch", hide_index=True, height=420)
else:
    st.caption("Atur rentang tanggal & mata uang di atas, lalu klik "
               "**Tarik data dari BI** untuk mengunduh kurs.")
