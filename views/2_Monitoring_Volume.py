"""Halaman 3 — Monitoring Volume (§2): pertumbuhan transaksi day-to-day."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()
ctx = E.bootstrap("Monitoring Volume (§2)", "📊",
                  "Pertumbuhan volume transaksi day-to-day")
data, cb = ctx.data, ctx.data["combine"]
g = ctx.granularitas

# ---- tren volume per periode ----
tv = E.tren_volume(data, ctx.valutas, ctx.tgl_h, ctx.pts, gran=g)
tv = tv[tv["Tanggal"] >= pd.Timestamp(ctx.tgl_awal)]
fig = go.Figure()
fig.add_trace(go.Bar(x=tv["Tanggal"], y=tv["Jual"], name="Volume Jual",
                     marker_color="#185FA5"))
fig.add_trace(go.Bar(x=tv["Tanggal"], y=tv["Beli"], name="Volume Beli",
                     marker_color="#1D9E75"))
fig.update_layout(height=330, barmode="group", margin=dict(t=30, b=8, l=8, r=8),
                  title=dict(text=f"Tren volume {g.lower()} (Rp) · {', '.join(ctx.valutas)}",
                             font=dict(size=15)),
                  legend=dict(orientation="h", y=-0.2), hovermode="x unified")
st.plotly_chart(fig, width='stretch')

# ---- tabel growth periode-ke-periode ----
st.subheader(f"Pertumbuhan volume {g.lower()} ({ctx.lbl_p} → {ctx.lbl_h})")
tb = E.tabel_volume(data, ctx.valutas, ctx.tgl_h, ctx.tgl_p, ctx.tgl_awal, ctx.pts,
                    ctx.ambang_dtd, gran=g)
view = pd.DataFrame({
    "Volume": tb["Volume"], "Awal": tb["Awal"], "Pembanding": tb["Pembanding"],
    "Tanggal cek": tb["Tanggal cek"], "Growth (dtd)": tb["Growth (dtd)"], "Status": tb["Status"],
})

def warna_status(v):
    c = E.STATUS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 500;" if c else ""

sty = (view.style.map(warna_status, subset=["Status"])
       .format({"Awal": lambda x: E.rupiah(x), "Pembanding": lambda x: E.rupiah(x),
                "Tanggal cek": lambda x: E.rupiah(x), "Growth (dtd)": E.persen}))
st.dataframe(sty, width='stretch', hide_index=True)

# ---- KUPVA Waspada volume ----
mtx = E.matriks_per_kupva(data, ctx.valuta_fokus, ctx.valutas, ctx.tgl_h, ctx.tgl_p,
                          ctx.pts, ctx.ambang_rasio, ctx.ambang_dtd, gran=g)
mtx = mtx[mtx["ID"].isin(ctx.pts)]
wasp = mtx[mtx["Status Volume"] == "Waspada"]

c1, c2 = st.columns([1, 1])
with c1:
    st.subheader("KUPVA BB berkategori Waspada")
    if wasp.empty:
        st.success("Tidak ada KUPVA BB dengan growth volume ≥ ambang.")
    else:
        wv = pd.DataFrame({
            "KUPVA BB": wasp["KUPVA BB"],
            "Growth jual": wasp["Growth Jual"].map(lambda v: E.persen(v) if pd.notna(v) else "—"),
            "Growth beli": wasp["Growth Beli"].map(lambda v: E.persen(v) if pd.notna(v) else "—"),
        })
        st.dataframe(wv, width='stretch', hide_index=True)

with c2:
    st.subheader("Catatan basis pembanding")
    if g == "Harian" and E.is_weekend(ctx.tgl_p):
        st.warning(
            f"Tanggal pembanding {E.fmt_tgl(ctx.tgl_p)} jatuh pada akhir pekan. "
            "Basis pembanding berpotensi rendah sehingga persentase growth dtd dapat membesar "
            "secara semu — baca dengan hati-hati dan dalami penyebabnya.", icon="⚠️")
    pj = E.volume_jual_beli(cb, ctx.tgl_p, ctx.valutas, ctx.pts, gran=g)
    if pj[0] == 0 or pj[1] == 0:
        st.info("Sebagian basis pembanding bernilai 0 → growth dtd ditandai tak terhingga/NaN "
                "dan tidak dipakai untuk kategori Waspada pada sisi tersebut.")

# ---- narasi ----
st.subheader("Narasi asesmen otomatis (§2)")
rj = tb.iloc[0]; rb = tb.iloc[1]
catatan = ("Catatan: tanggal pembanding jatuh pada hari non-transaksi/akhir pekan sehingga basis "
           "pembanding dapat rendah dan persentase pertumbuhan dtd perlu dibaca berhati-hati. "
           if g == "Harian" and E.is_weekend(ctx.tgl_p) else "")
st.info(
    f"Monitoring volume transaksi {g.lower()} ({ctx.lbl_h} vs {ctx.lbl_p}) "
    f"untuk {', '.join(ctx.valutas)}: volume jual {E.persen(rj['Growth (dtd)'])} ({rj['Status']}) "
    f"dan volume beli {E.persen(rb['Growth (dtd)'])} ({rb['Status']}) antar periode. "
    f"Kategori Normal apabila perubahan dtd di bawah {ctx.ambang_dtd:.0%}, Waspada apabila "
    f"{ctx.ambang_dtd:.0%} atau lebih. Terdapat {len(wasp)} KUPVA BB berkategori Waspada. {catatan}",
    icon="📝")
