"""Halaman Data — unggah workbook Excel transaksi (menggantikan upload di sidebar)."""
import streamlit as st

import saksi_engine as E
from core.ui_helpers import page_header, require_auth, section_title

require_auth()
page_header("📁", "Data", "Muat workbook Excel transaksi harian untuk mengisi seluruh dashboard")

# ---- Info format ----
with st.container(border=True):
    section_title("Format file yang diterima")
    st.markdown(
        "File **.xlsx** dengan **3 sheet wajib**:\n"
        "- `Combine` — baris transaksi harian per KUPVA\n"
        "- `Kurs Tengah` — acuan Kurs Tengah BI (valuta non-USD)\n"
        "- `Kurs Jisdor` — acuan Jisdor (USD)\n\n"
        "Begitu file termuat, seluruh halaman langsung terisi otomatis dan filter "
        "di atas tiap halaman berlaku lintas halaman."
    )

# ---- Uploader ----
with st.container(border=True):
    section_title("Pilih file Excel")
    up = st.file_uploader("Unggah Excel transaksi (.xlsx)", type=["xlsx"],
                          key="upl", label_visibility="collapsed")
    if up is not None:
        st.session_state["raw_bytes"] = up.getvalue()
        st.session_state["raw_name"] = up.name

# ---- Status data ----
data = E.get_data()
if data is not None:
    cb = data["combine"]
    n_pt = len(E.daftar_pt(cb))
    n_val = len(E.daftar_valuta(cb))
    n_tgl = len(E.daftar_tanggal(cb))
    st.success(f"✅ **{st.session_state.get('raw_name', 'data.xlsx')}** termuat.", icon="✅")
    k = st.columns(4)
    k[0].metric("Baris transaksi", f"{len(cb):,}".replace(",", "."))
    k[1].metric("KUPVA BB", n_pt)
    k[2].metric("Valuta", n_val)
    k[3].metric("Tanggal", n_tgl)
    st.caption("Lanjutkan ke menu **🛡️ Ringkasan** di navbar atas untuk mulai menganalisis.")
elif E.ada_data():
    st.error("File termuat tapi gagal dibaca. Pastikan sheet **Combine**, "
             "**Kurs Tengah**, dan **Kurs Jisdor** tersedia.", icon="⚠️")
else:
    st.info("Belum ada data. Unggah workbook di atas untuk memulai.", icon="📂")
