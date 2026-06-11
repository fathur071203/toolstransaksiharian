"""Halaman 6 — Risiko Valuta: eksposur valuta eksotik tanpa acuan BI."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()
ctx = E.bootstrap("Risiko Valuta", "⚠️",
                  "Eksposur valuta eksotik tanpa acuan BI")
data, cb = ctx.data, ctx.data["combine"]
g = ctx.granularitas

st.caption(
    "Valuta yang diperdagangkan namun tidak memiliki acuan kurs BI (Kurs Tengah/Jisdor) "
    "sulit di-benchmark, sehingga rawan mispricing dan menjadi titik perhatian APU-PPT — "
    "terutama valuta zona konflik/sanksi."
)

vt = E.valuta_tanpa_acuan(data, ctx.tgl_h, ctx.pts, gran=g)

if vt.empty:
    st.success("Seluruh valuta yang diperdagangkan pada tanggal cek memiliki acuan BI.")
    st.stop()

n_sensitif = int(vt["Sensitif"].sum())
tot_eksotik = float(vt["Volume H (Rp)"].sum())
k = st.columns(3)
k[0].metric("Valuta tanpa acuan", len(vt))
k[1].metric("Di antaranya sensitif", n_sensitif, help="Valuta zona konflik/sanksi")
k[2].metric("Total volume eksotik H", E.rupiah(tot_eksotik))

st.divider()
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("Eksposur volume per valuta tanpa acuan")
    top = vt[vt["Volume H (Rp)"] > 0].head(15)
    fig = go.Figure(go.Bar(
        x=top["Volume H (Rp)"], y=top["Valuta"], orientation="h",
        marker_color=[E.STATUS_WARNA["Waspada"] if s else E.STATUS_WARNA["Perhatian"]
                      for s in top["Sensitif"]],
        text=[E.rupiah(x) for x in top["Volume H (Rp)"]], textposition="outside"))
    fig.update_layout(height=380, margin=dict(t=10, b=8, l=8, r=8),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width='stretch')
    st.caption("Merah = valuta sensitif geopolitik · oranye = lainnya.")

with c2:
    st.subheader("Daftar tindak lanjut")
    view = vt.copy()
    view["Sensitif"] = view["Sensitif"].map({True: "⚠️ ya", False: "—"})

    def warna(v):
        return "background-color:#E24B4A22;color:#A32D2D;font-weight:500;" if v == "⚠️ ya" else ""

    sty = (view[["Valuta", "Negara/Konteks", "Sensitif", "Volume H (Rp)", "Jml KUPVA"]]
           .style.map(warna, subset=["Sensitif"])
           .format({"Volume H (Rp)": lambda x: E.rupiah(x)}))
    st.dataframe(sty, width='stretch', hide_index=True, height=380)

# ---- konsentrasi PT x valuta sensitif ----
st.subheader("Konsentrasi KUPVA BB pada valuta sensitif")
sens = vt[vt["Sensitif"]]["Valuta"].tolist()
sub = E.filter_cb(cb, tgl=ctx.tgl_h, valutas=sens, pts=ctx.pts, gran=g)
if sub.empty:
    st.info("Tidak ada transaksi valuta sensitif pada periode cek.")
else:
    sub = sub.copy()
    sub["Volume"] = sub[E.C_JUAL_RP] + sub[E.C_BELI_RP]
    piv = sub.pivot_table(index=E.C_ID, columns=E.C_VAL, values="Volume",
                          aggfunc="sum", fill_value=0)
    piv.index = [data["nama_map"].get(i, i) for i in piv.index]
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    fig2 = go.Figure(go.Heatmap(
        z=piv.values, x=list(piv.columns), y=list(piv.index),
        colorscale="Reds", colorbar=dict(title="Rp")))
    fig2.update_layout(height=max(260, 38 * len(piv)), margin=dict(t=10, b=8, l=8, r=8))
    st.plotly_chart(fig2, width='stretch')

st.info(
    f"Pada periode {ctx.lbl_h} ({g}) terdapat {len(vt)} valuta tanpa acuan BI "
    f"({n_sensitif} di antaranya valuta sensitif geopolitik) dengan total volume "
    f"{E.rupiah(tot_eksotik)}. Transaksi valuta tanpa acuan direkomendasikan untuk pendalaman "
    "(verifikasi kurs, underlying, dan profil nasabah) sebagai bagian pengawasan APU-PPT.",
    icon="📝")
