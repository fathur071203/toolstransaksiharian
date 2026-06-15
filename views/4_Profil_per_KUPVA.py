"""Halaman Profil per-KUPVA — Laporan Harian (konsep selaras §1/§2).

Drill-down satu penyelenggara pada satu tanggal: absensi, volume, rincian per
valuta (rasio kurs vs BI + growth volume dtd) dengan status & penanganan no-data,
serta tren kurs 3 hari untuk valuta terpilih. Filter mandiri (tanpa pembanding).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth, page_header, no_data_card, section_title

require_auth()
page_header("🏦", "Profil per-KUPVA — Laporan Harian",
            "Drill-down satu penyelenggara KUPVA BB pada tanggal laporan")

data = E.get_data()
if data is None:
    no_data_card()
    st.stop()

cb = data["combine"]
hari_all = E.daftar_tanggal(cb)
pts_all = E.daftar_pt(cb)
nama = lambda p: data["nama_map"].get(p, p)

# ----------------------------------------------------------------------------
# 1. PERIODE
# ----------------------------------------------------------------------------
gp = st.columns([1.2, 5])
gran = gp[0].selectbox("🗓️ Periode laporan", options=E.GRANULARITAS, index=0, key="pf_gran")
if gran != "Harian":
    st.info(f"Profil **{gran}** sedang dalam pengembangan — saat ini baru **Harian** "
            "yang aktif. Pilih **Harian** untuk melanjutkan.", icon="🚧")
    st.stop()

# ----------------------------------------------------------------------------
# 2. FILTER
# ----------------------------------------------------------------------------
with st.container(border=True):
    section_title("Filter profil harian")
    r1 = st.columns([1.4, 2.4, 0.6])
    tgl_h = r1[0].selectbox("📅 Tanggal laporan (H)", options=hari_all,
                            index=len(hari_all) - 1, format_func=E.fmt_tgl, key="pf_tgl")
    pid = r1[1].selectbox("🏦 KUPVA terpilih", options=pts_all,
                          format_func=lambda p: f"{nama(p)} ({p})", key="pf_pt")
    with r1[2].popover("⚙️", use_container_width=True):
        ambang_r = st.slider("Waspada rasio kurs (≥)", 1.00, 1.20,
                             E.AMBANG_RASIO_DEFAULT, 0.01, key="pf_amb_r")
        ambang_v = st.slider("Waspada growth volume (≥)", 0.05, 0.50,
                             E.AMBANG_DTD_DEFAULT, 0.01, format="%.2f", key="pf_amb_v")

i_h = hari_all.index(tgl_h)
tgl_p = hari_all[i_h - 1] if i_h > 0 else None
sub_h = E.filter_cb(cb, tgl=tgl_h, pts=[pid], gran="Harian")

st.caption(f"Laporan **Harian** · {E.fmt_tgl(tgl_h)} · KUPVA **{nama(pid)}** · "
           f"pembanding volume {E.fmt_tgl(tgl_p) if tgl_p is not None else '—'}")

if sub_h.empty:
    st.warning(f"🚫 {nama(pid)} **tidak menyampaikan transaksi** pada {E.fmt_tgl(tgl_h)} "
               "(berkategori belum lapor). Tidak ada rincian untuk ditampilkan.", icon="⚠️")
    st.stop()

# ----------------------------------------------------------------------------
# KPI
# ----------------------------------------------------------------------------
vj = float(sub_h[E.C_JUAL_RP].sum())
vb = float(sub_h[E.C_BELI_RP].sum())
saldo = float(sub_h[E.C_SAK_RP].sum())
vals = E.valuta_pt_pada(data, pid, tgl_h, gran="Harian")

k = st.columns(4)
k[0].metric("Volume jual (H)", E.rupiah(vj))
k[1].metric("Volume beli (H)", E.rupiah(vb))
k[2].metric("Saldo akhir (H)", E.rupiah(saldo))
k[3].metric("Valuta aktif", len(vals))

st.divider()

# ----------------------------------------------------------------------------
# RINCIAN PER VALUTA (kurs vs BI + volume dtd)
# ----------------------------------------------------------------------------
st.subheader(f"Rincian per valuta · {E.fmt_tgl(tgl_h)}")
tk = E.tabel_kurs_komponen(data, pid, tgl_h, vals, ambang_r, gran="Harian")
tv = E.tabel_volume_komponen(data, pid, tgl_h, tgl_p, vals, ambang_v, gran="Harian")
rdf = pd.DataFrame({
    "Valuta": tk["Valuta"],
    "Rasio Tengah": tk["Rasio Tengah"],
    "Status Kurs": tk["Status Akhir"],
    "Vol Jual (H)": tv["Jual (H)"],
    "Vol Beli (H)": tv["Beli (H)"],
    "Growth Jual": tv["Growth Jual"],
    "Growth Beli": tv["Growth Beli"],
    "Status Volume": tv["Status Akhir"],
})


def warna_status(v):
    c = E.STATUS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 600;" if c else ""


def tandai_kosong(v):
    return ("background-color: #8887801a; color: #888780; font-style: italic;"
            if pd.isna(v) else "")


num_cols = ["Rasio Tengah", "Vol Jual (H)", "Vol Beli (H)", "Growth Jual", "Growth Beli"]
sty = (rdf.style
       .map(warna_status, subset=["Status Kurs", "Status Volume"])
       .map(tandai_kosong, subset=num_cols)
       .format({"Rasio Tengah": E.persen, "Vol Jual (H)": E.rupiah, "Vol Beli (H)": E.rupiah,
                "Growth Jual": E.persen, "Growth Beli": E.persen}, na_rep="tidak ada data"))
st.dataframe(sty, width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# TREN KURS 3 HARI untuk valuta terpilih KUPVA ini
# ----------------------------------------------------------------------------
volmap = {v: float(sub_h[sub_h[E.C_VAL] == v][E.C_JUAL_RP].sum()
                   + sub_h[sub_h[E.C_VAL] == v][E.C_BELI_RP].sum()) for v in vals}
g_val = st.selectbox("📈 Valuta untuk tren kurs (3 hari)", options=vals,
                     index=vals.index(max(volmap, key=volmap.get)), key="pf_gval")

hari = [t for t in hari_all if pd.Timestamp(t) <= pd.Timestamp(tgl_h)][-3:]
rows = []
for t in hari:
    bi = E.kurs_bi_komponen(data, g_val, t)
    pt = E.kurs_rata2(cb, t, g_val, [pid], gran="Harian", acuan=bi["tengah"])
    rows.append({"Tanggal": E.fmt_tgl(t),
                 "BI Beli": bi["beli"], "BI Tengah": bi["tengah"], "BI Jual": bi["jual"],
                 "KUPVA Beli": pt["beli"], "KUPVA Tengah": pt["tengah"], "KUPVA Jual": pt["jual"]})
df1 = pd.DataFrame(rows)
WARNA = {"Beli": "#1D9E75", "Tengah": "#185FA5", "Jual": "#E24B4A"}
fig = go.Figure()
for komp, c in WARNA.items():
    fig.add_trace(go.Scatter(x=df1["Tanggal"], y=df1[f"BI {komp}"], name=f"BI {komp}",
                             mode="lines+markers", legendgroup="BI",
                             line=dict(color=c, width=2, dash="dash"),
                             marker=dict(symbol="square", size=7)))
    fig.add_trace(go.Scatter(x=df1["Tanggal"], y=df1[f"KUPVA {komp}"], name=f"KUPVA {komp}",
                             mode="lines+markers", legendgroup="KUPVA",
                             line=dict(color=c, width=2.6), marker=dict(size=9)))
fig.update_layout(height=340, margin=dict(t=36, b=8, l=8, r=8),
                  title=dict(text=f"Tren kurs {g_val} — {nama(pid)} vs BI (3 hari)", font=dict(size=15)),
                  legend=dict(orientation="h", y=-0.2), hovermode="x unified",
                  xaxis=dict(type="category"))
st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# NARASI
# ----------------------------------------------------------------------------
st.subheader("Narasi asesmen otomatis")
wk = rdf[rdf["Status Kurs"] == "Waspada"]["Valuta"].tolist()
pk = rdf[rdf["Status Kurs"] == "Perhatian"]["Valuta"].tolist()
wv = rdf[rdf["Status Volume"] == "Waspada"]["Valuta"].tolist()
bagian = [f"{nama(pid)} menyampaikan transaksi {len(vals)} valuta pada {E.fmt_tgl(tgl_h)} "
          f"(jual {E.rupiah(vj)}, beli {E.rupiah(vb)})."]
if wk:
    bagian.append(f"Rasio kurs Waspada (≥ {ambang_r:.0%}) pada: {', '.join(wk)}.")
if pk:
    bagian.append(f"Perhatian (100%–{ambang_r:.0%}) pada: {', '.join(pk)}.")
if wv:
    bagian.append(f"Growth volume Waspada (≥ {ambang_v:.0%}) pada: {', '.join(wv)}.")
if not wk and not pk and not wv:
    bagian.append("Tidak terdapat indikasi Perhatian/Waspada pada kurs maupun volume.")
st.info(" ".join(bagian), icon="📝")
