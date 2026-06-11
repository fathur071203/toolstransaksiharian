"""Halaman 5 — Profil per-KUPVA: drill-down satu penyelenggara."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()
ctx = E.bootstrap("Profil per-KUPVA", "🏦",
                  "Drill-down satu penyelenggara KUPVA BB")
data, cb = ctx.data, ctx.data["combine"]
g = ctx.granularitas

pid = st.selectbox("Pilih KUPVA BB", options=ctx.pts,
                   format_func=lambda p: f"{data['nama_map'].get(p, p)} ({p})")
nama = data["nama_map"].get(pid, pid)

sub_h = E.filter_cb(cb, tgl=ctx.tgl_h, pts=[pid], gran=g)
sub_p = E.filter_cb(cb, tgl=ctx.tgl_p, pts=[pid], gran=g)

if sub_h.empty:
    st.warning(f"{nama} tidak menyampaikan data transaksi pada periode {ctx.lbl_h} "
               "(berkategori belum lapor / kelengkapan).", icon="⚠️")

vj = float(sub_h[E.C_JUAL_RP].sum()); vb = float(sub_h[E.C_BELI_RP].sum())
saldo = float(sub_h[E.C_SAK_RP].sum()); n_val = int(sub_h[E.C_VAL].nunique())

k = st.columns(4)
k[0].metric("Volume jual", E.rupiah(vj))
k[1].metric("Volume beli", E.rupiah(vb))
k[2].metric("Saldo akhir", E.rupiah(saldo))
k[3].metric("Valuta aktif", n_val)

st.divider()

# ---- rincian per valuta ----
st.subheader(f"Rincian per valuta · {ctx.lbl_h}")
rows = []
for v in sorted(sub_h[E.C_VAL].unique()):
    a = E.acuan_bi(data, v, ctx.tgl_h, gran=g)
    kr = E.kurs_rata2(cb, ctx.tgl_h, v, [pid], gran=g, acuan=a)["tengah"]
    rasio = E.hitung_rasio(kr, a)
    jh = float(sub_h[sub_h[E.C_VAL] == v][E.C_JUAL_RP].sum())
    bh = float(sub_h[sub_h[E.C_VAL] == v][E.C_BELI_RP].sum())
    jp = float(sub_p[sub_p[E.C_VAL] == v][E.C_JUAL_RP].sum())
    bp = float(sub_p[sub_p[E.C_VAL] == v][E.C_BELI_RP].sum())
    gj, gb = E.growth(jh, jp), E.growth(bh, bp)
    s_kurs = "Tanpa acuan" if a is None else E.status_kurs(rasio, ctx.ambang_rasio)
    s_vol = "Waspada" if "Waspada" in (E.status_volume(gj, ctx.ambang_dtd),
                                       E.status_volume(gb, ctx.ambang_dtd)) else "Normal"
    rows.append({"Valuta": v, "Rasio tengah": rasio, "Vol jual H": jh, "Vol beli H": bh,
                 "Growth jual": gj, "Growth beli": gb,
                 "Status kurs": s_kurs, "Status volume": s_vol})
rdf = pd.DataFrame(rows)

def warna_status(val):
    c = E.STATUS_WARNA.get(val, "#BA7517" if val == "Tanpa acuan" else None)
    return f"background-color: {c}22; color: {c}; font-weight: 500;" if c else ""

if not rdf.empty:
    sty = (rdf.style.map(warna_status, subset=["Status kurs", "Status volume"])
           .format({"Rasio tengah": lambda x: E.persen(x) if pd.notna(x) else "tanpa acuan",
                    "Vol jual H": lambda x: E.rupiah(x), "Vol beli H": lambda x: E.rupiah(x),
                    "Growth jual": lambda x: E.persen(x) if pd.notna(x) else "—",
                    "Growth beli": lambda x: E.persen(x) if pd.notna(x) else "—"}))
    st.dataframe(sty, width='stretch', hide_index=True)

# ---- tren kurs valuta fokus utk PT ini ----
if ctx.valuta_fokus in cb[cb[E.C_ID] == pid][E.C_VAL].unique():
    tk = E.tren_kurs(data, ctx.valuta_fokus, ctx.tgl_h, [pid], gran=g)
    fig = go.Figure()
    for komp, c in {"Kurs Jual": "#E24B4A", "Kurs Tengah": "#185FA5", "Kurs Beli": "#1D9E75"}.items():
        s = tk[["Tanggal", komp]].replace(0, np.nan).dropna()
        fig.add_trace(go.Scatter(x=s["Tanggal"], y=s[komp], name=komp, mode="lines+markers",
                                 line=dict(color=c, width=2)))
    acu = tk[["Tanggal", "Acuan BI"]].dropna()
    fig.add_trace(go.Scatter(x=acu["Tanggal"], y=acu["Acuan BI"], name="Acuan BI",
                             mode="lines", line=dict(color="#888780", dash="dash", width=2)))
    fig.update_layout(height=300, margin=dict(t=30, b=8, l=8, r=8),
                      title=dict(text=f"Tren kurs {ctx.valuta_fokus} — {nama}", font=dict(size=15)),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    st.plotly_chart(fig, width='stretch')

# ---- narasi per PT ----
st.subheader("Narasi asesmen otomatis")
wasp_v = rdf[rdf["Status volume"] == "Waspada"]["Valuta"].tolist() if not rdf.empty else []
wasp_k = rdf[rdf["Status kurs"] == "Waspada"]["Valuta"].tolist() if not rdf.empty else []
tanpa = rdf[rdf["Status kurs"] == "Tanpa acuan"]["Valuta"].tolist() if not rdf.empty else []

bagian = []
if not sub_h.empty:
    bagian.append(f"{nama} menyampaikan transaksi {n_val} valuta pada periode {ctx.lbl_h} "
                  f"(jual {E.rupiah(vj)}, beli {E.rupiah(vb)}).")
if wasp_v:
    bagian.append(f"Tergolong Waspada pada sisi volume untuk valuta: {', '.join(wasp_v)}.")
if wasp_k:
    bagian.append(f"Rasio kurs Waspada (≥ {ctx.ambang_rasio:.0%}) pada: {', '.join(wasp_k)}.")
if tanpa:
    bagian.append(f"Memperdagangkan valuta tanpa acuan BI: {', '.join(tanpa)} — perlu perhatian "
                  "karena kurs tidak dapat di-benchmark.")
if not wasp_v and not wasp_k and not sub_h.empty:
    bagian.append("Tidak terdapat indikasi Waspada pada kurs maupun volume.")
if g == "Harian" and E.is_weekend(ctx.tgl_p):
    bagian.append("Tanggal pembanding jatuh pada akhir pekan; pertumbuhan dtd dibaca berhati-hati.")
st.info(" ".join(bagian) if bagian else "Tidak ada data untuk dinarasikan.", icon="📝")
