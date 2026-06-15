"""Halaman Absensi & Kelengkapan (§3) + Supervisory Action (§4).

Dua mode (tab):
  • Per Periode      — satu periode → status penyampaian SELURUH KUPVA.
  • Per Penyelenggara — satu KUPVA → riwayat penyampaian di SELURUH periode.

Periode: Harian/Mingguan/Bulanan/Triwulanan/Tahunan. Data tetap harian; periode
non-Harian mengagregasi 'berapa hari transaksi dilaporkan dari total hari dalam
periode' → status Lengkap / Sebagian / Belum lapor.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth, page_header, no_data_card, section_title

require_auth()
page_header("🗓️", "Absensi & Kelengkapan (§3)",
            "Penyampaian laporan KUPVA — per periode atau per penyelenggara")

data = E.get_data()
if data is None:
    no_data_card()
    st.stop()

cb = data["combine"]
pts_all = E.daftar_pt(cb)
nama = lambda p: data["nama_map"].get(p, p)

ABS_WARNA = {
    "Lengkap": E.STATUS_WARNA["Normal"],     # hijau
    "Sebagian": E.STATUS_WARNA["Perhatian"],  # oranye
    "Belum lapor": E.STATUS_WARNA["Waspada"],  # merah
}


def warna_abs(v):
    c = ABS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 600;" if c else ""


# Periode berlaku untuk kedua tab
gp = st.columns([1.2, 5])
gran = gp[0].selectbox("🗓️ Periode laporan", options=E.GRANULARITAS, index=0, key="abs_gran")
fmt_p = (lambda t: E.fmt_tgl(t)) if gran == "Harian" else (lambda t: E.fmt_periode(t, gran))
opsi = E.daftar_periode(cb, gran)

tab_per, tab_pyl = st.tabs(["📅 Per Periode", "🏦 Per Penyelenggara"])

# ============================================================================
# TAB 1 — PER PERIODE: satu periode → semua KUPVA
# ============================================================================
with tab_per:
    with st.container(border=True):
        section_title("Filter absensi — per periode")
        r1 = st.columns([1.6, 2.6])
        tgl = r1[0].selectbox(f"📅 Periode cek ({gran})", options=opsi,
                              index=len(opsi) - 1, format_func=fmt_p, key="abs_periode")
        tampil = r1[1].radio("Tampilkan", ["Semua", "Lengkap", "Sebagian", "Belum lapor"],
                             horizontal=True, key="abs_tampil")

    ab = E.absensi_periode(data, tgl, gran=gran)
    total = len(ab)
    n_l = int((ab["Status"] == "Lengkap").sum())
    n_s = int((ab["Status"] == "Sebagian").sum())
    n_b = int((ab["Status"] == "Belum lapor").sum())
    n_hari = int(ab["Hari transaksi"].iloc[0]) if total else 0

    k = st.columns(4)
    k[0].metric("Total KUPVA (data)", total)
    k[1].metric("Lengkap", n_l, help="Melapor di semua hari transaksi periode.")
    k[2].metric("Sebagian", n_s, help="Melapor sebagian hari (hanya muncul untuk periode > harian).")
    k[3].metric("Belum lapor", n_b)
    st.caption(f"Periode **{fmt_p(tgl)}** memuat **{n_hari}** hari transaksi. "
               + ("Harian → Lengkap = sudah lapor, Belum lapor = tidak."
                  if gran == "Harian" else
                  "Lengkap = lapor semua hari · Sebagian = lapor sebagian · Belum lapor = nihil."))

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader(f"Daftar penyampaian — {tampil}")
        sub = ab if tampil == "Semua" else ab[ab["Status"] == tampil]
        if sub.empty:
            st.info(f"Tidak ada KUPVA pada kategori '{tampil}'.")
        else:
            view = pd.DataFrame({
                "KUPVA BB": sub["KUPVA BB"],
                "Lapor / Hari": sub["Hari lapor"].astype(str) + " / " + sub["Hari transaksi"].astype(str),
                "Kelengkapan": sub["Kelengkapan"],
                "Volume": sub["Volume (Rp)"],
                "Status": sub["Status"],
            })
            sty = (view.style.map(warna_abs, subset=["Status"])
                   .format({"Kelengkapan": lambda x: E.persen(x, 0), "Volume": lambda x: E.rupiah(x)}))
            st.dataframe(sty, width="stretch", hide_index=True, height=430)

    with c2:
        st.subheader("Komposisi")
        fig = go.Figure(go.Pie(
            labels=["Lengkap", "Sebagian", "Belum lapor"], values=[n_l, n_s, n_b],
            marker=dict(colors=[ABS_WARNA["Lengkap"], ABS_WARNA["Sebagian"], ABS_WARNA["Belum lapor"]],
                        line=dict(color="#fff", width=1.5)),
            hole=0.62, textinfo="value", sort=False))
        fig.update_layout(height=240, margin=dict(t=10, b=8, l=8, r=8),
                          legend=dict(orientation="h", y=-0.18))
        st.plotly_chart(fig, width="stretch")
        st.caption("Proxy ketepatan: ketersediaan baris transaksi pada hari-hari periode. "
                   "Batas H+1 pukul 12.00 dinilai manual oleh KPwDN.")

    belum = ab[ab["Status"] == "Belum lapor"]["KUPVA BB"].tolist()
    sebagian = ab[ab["Status"] == "Sebagian"]["KUPVA BB"].tolist()
    st.subheader("Narasi asesmen otomatis (§3 & §4)")
    st.info(
        f"Pada periode {fmt_p(tgl)} ({gran}), dari **{total}** KUPVA BB: "
        f"**{n_l}** Lengkap, **{n_s}** Sebagian, **{n_b}** Belum lapor "
        f"(ketepatan {E.persen((n_l) / total if total else 0, 1)} lapor penuh). "
        + (f"Belum lapor: {', '.join(belum)}. " if belum else "")
        + (f"Lapor sebagian: {', '.join(sebagian)}. " if sebagian else "")
        + "Penilaian batas H+1 pukul 12.00 dilakukan manual oleh KPwDN.",
        icon="📝")

# ============================================================================
# TAB 2 — PER PENYELENGGARA: satu KUPVA → semua periode
# ============================================================================
with tab_pyl:
    with st.container(border=True):
        section_title("Filter absensi — per penyelenggara")
        pid = st.selectbox("🏦 KUPVA terpilih", options=pts_all, format_func=nama, key="abs_pyl_pt")

    ap = E.absensi_penyelenggara(data, pid, gran=gran)
    tp = len(ap)
    p_l = int((ap["Status"] == "Lengkap").sum())
    p_s = int((ap["Status"] == "Sebagian").sum())
    p_b = int((ap["Status"] == "Belum lapor").sum())

    k = st.columns(4)
    k[0].metric(f"Total periode ({gran})", tp)
    k[1].metric("Lengkap", p_l)
    k[2].metric("Sebagian", p_s)
    k[3].metric("Belum lapor", p_b)

    st.subheader(f"Riwayat penyampaian — {nama(pid)}")
    bar = go.Figure(go.Bar(
        x=ap["Periode"], y=ap["Kelengkapan"],
        marker_color=[ABS_WARNA.get(s, "#888780") for s in ap["Status"]],
        text=[f"{hl}/{ht}" for hl, ht in zip(ap["Hari lapor"], ap["Hari transaksi"])],
        textposition="outside",
        customdata=ap["Status"],
        hovertemplate="%{x}<br>Kelengkapan %{y:.0%}<br>%{customdata}<extra></extra>"))
    bar.update_layout(height=300, margin=dict(t=20, b=8, l=8, r=8),
                      title=dict(text="Kelengkapan penyampaian per periode", font=dict(size=15)),
                      yaxis=dict(tickformat=".0%", range=[0, 1.08]))
    st.plotly_chart(bar, width="stretch")

    view2 = pd.DataFrame({
        "Periode": ap["Periode"],
        "Lapor / Hari": ap["Hari lapor"].astype(str) + " / " + ap["Hari transaksi"].astype(str),
        "Kelengkapan": ap["Kelengkapan"],
        "Volume": ap["Volume (Rp)"],
        "Status": ap["Status"],
    })
    sty2 = (view2.style.map(warna_abs, subset=["Status"])
            .format({"Kelengkapan": lambda x: E.persen(x, 0), "Volume": lambda x: E.rupiah(x)}))
    st.dataframe(sty2, width="stretch", hide_index=True)

    miss = ap[ap["Status"] != "Lengkap"]["Periode"].tolist()
    st.subheader("Narasi asesmen otomatis")
    st.info(
        f"{nama(pid)} pada {tp} periode {gran.lower()}: {p_l} Lengkap, {p_s} Sebagian, "
        f"{p_b} Belum lapor. "
        + (f"Periode belum lengkap: {', '.join(miss)}. " if miss else "Penyampaian konsisten penuh. ")
        + "Tindak lanjut atas kelengkapan/penyampaian laporan untuk periode yang belum lengkap.",
        icon="📝")

# ============================================================================
# Supervisory action (umum)
# ============================================================================
st.markdown("#### Supervisory action")
st.markdown(
    "- Apabila transaksi **Kategori Normal**: pengawasan offsite melalui pemantauan transaksi "
    "harian terhadap KUPVA BB selama adanya gejolak nilai tukar.\n"
    "- Untuk KUPVA BB **belum/sebagian lapor**: tindak lanjut atas kelengkapan/penyampaian laporan.\n"
    "- Untuk KUPVA BB **Kategori Waspada** (lihat halaman Kurs/Volume): pendalaman penyebab "
    "dengan menginformasikan nama KUPVA BB, jenis valuta, serta kurs yang digunakan."
)
