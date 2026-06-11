"""Halaman 4 — Absensi & Kelengkapan (§3) + Supervisory Action (§4)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()
ctx = E.bootstrap("Absensi & Kelengkapan (§3)", "🗓️",
                  "Ketepatan & kelengkapan pelaporan + supervisory action")
data, cb = ctx.data, ctx.data["combine"]
g = ctx.granularitas

ab = E.tabel_absensi(data, ctx.tgl_h, ctx.pts, gran=g)
ab_sel = ab[ab["ID"].isin(ctx.pts)]
n_lapor = int((ab_sel["Status"] == "Lengkap").sum())
n_belum = int((ab_sel["Status"] == "Belum lapor").sum())
total = len(ab_sel)

k = st.columns(4)
k[0].metric("KUPVA terpilih", total)
k[1].metric(f"Telah lapor · {ctx.lbl_h}", n_lapor)
k[2].metric("Belum lapor", n_belum)
k[3].metric("Ketepatan", E.persen(n_lapor / total if total else 0, 1))

st.divider()
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("Daftar penyampaian laporan")
    view = pd.DataFrame({
        "KUPVA BB": ab_sel["KUPVA BB"],
        "Lapor H": ab_sel["Lapor H"].map({True: "✓", False: "—"}),
        "Jml baris": ab_sel["Jml baris"],
        "Volume H": ab_sel["Volume H (Rp)"],
        "Status": ab_sel["Status"],
    })

    def warna(v):
        c = E.STATUS_WARNA["Normal"] if v == "Lengkap" else E.STATUS_WARNA["Waspada"]
        return f"background-color: {c}22; color: {c}; font-weight: 500;"

    sty = (view.style.map(warna, subset=["Status"])
           .format({"Volume H": lambda x: E.rupiah(x)}))
    st.dataframe(sty, width='stretch', hide_index=True, height=430)

with c2:
    st.subheader("Komposisi penyampaian")
    fig = go.Figure(go.Pie(
        labels=["Telah lapor", "Belum lapor"], values=[n_lapor, n_belum],
        marker=dict(colors=[E.STATUS_WARNA["Normal"], E.STATUS_WARNA["Waspada"]],
                    line=dict(color="#fff", width=1.5)),
        hole=0.62, textinfo="value", sort=False))
    fig.update_layout(height=240, margin=dict(t=10, b=8, l=8, r=8),
                      legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig, width='stretch')
    st.caption("Proxy ketepatan: ketersediaan baris transaksi pada tanggal cek. "
               "Data sumber tidak memuat cap waktu penyampaian sehingga batas H+1 pukul 12.00 "
               "dinilai manual oleh KPwDN.")

# ---- narasi §3 & §4 ----
belum = ab_sel[ab_sel["Status"] == "Belum lapor"]["KUPVA BB"].tolist()
st.subheader("Narasi asesmen otomatis (§3 & §4)")
st.info(
    f"Jumlah KUPVA BB dipantau pada periode {ctx.lbl_h} ({g}): {n_lapor} dari {total} terpilih. "
    "Objek monitoring mencerminkan minimum 50% dari total transaksi jual & beli KUPVA BB di "
    f"KPwDN (mayoritas transaksi). "
    + (f"Sebanyak {n_belum} KUPVA BB belum/tidak menyampaikan data: {', '.join(belum)}. "
       if belum else "Seluruh KUPVA BB terpilih telah menyampaikan data. ")
    + "Penilaian ketepatan terhadap batas H+1 pukul 12.00 dilakukan manual oleh KPwDN.",
    icon="📝")

st.markdown("#### Supervisory action")
st.markdown(
    "- Apabila transaksi **Kategori Normal**: pengawasan offsite melalui pemantauan transaksi "
    "harian terhadap KUPVA BB selama adanya gejolak nilai tukar.\n"
    "- Untuk KUPVA BB **belum lapor**: tindak lanjut atas kelengkapan/penyampaian laporan.\n"
    "- Untuk KUPVA BB **Kategori Waspada** (lihat halaman Kurs/Volume): pendalaman penyebab "
    "dengan menginformasikan nama KUPVA BB, jenis valuta, serta kurs yang digunakan."
)
