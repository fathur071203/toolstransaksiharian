"""Halaman 2 — Monitoring Kurs (§1): rasio kurs KUPVA vs acuan BI."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()
ctx = E.bootstrap("Monitoring Kurs (§1)", "💱",
                  "Rasio kurs KUPVA terhadap acuan Bank Indonesia")
data, cb = ctx.data, ctx.data["combine"]
val = ctx.valuta_fokus

g = ctx.granularitas

# ---- tren kurs ----
tk = E.tren_kurs(data, val, ctx.tgl_h, ctx.pts, gran=g)
fig = go.Figure()
warna = {"Kurs Jual": "#E24B4A", "Kurs Tengah": "#185FA5", "Kurs Beli": "#1D9E75"}
for komp, c in warna.items():
    s = tk[["Tanggal", komp]].replace(0, np.nan).dropna()
    fig.add_trace(go.Scatter(x=s["Tanggal"], y=s[komp], name=komp, mode="lines+markers",
                             line=dict(color=c, width=2)))
acu = tk[["Tanggal", "Acuan BI"]].dropna()
fig.add_trace(go.Scatter(x=acu["Tanggal"], y=acu["Acuan BI"], name="Acuan BI",
                         mode="lines", line=dict(color="#888780", width=2, dash="dash")))
fig.update_layout(height=340, margin=dict(t=30, b=8, l=8, r=8),
                  title=dict(text=f"Tren kurs {val} (rata-rata KUPVA) vs acuan BI", font=dict(size=15)),
                  legend=dict(orientation="h", y=-0.2), hovermode="x unified")

# ---- rasio per valuta terpilih (tengah) ----
rows = []
for v in ctx.valutas:
    a = E.acuan_bi(data, v, ctx.tgl_h, gran=g)
    kr = E.kurs_rata2(cb, ctx.tgl_h, v, ctx.pts, gran=g, acuan=a)["tengah"]
    r = E.hitung_rasio(kr, a)
    rows.append({"Valuta": v, "Rasio": r})
rdf = pd.DataFrame(rows).dropna(subset=["Rasio"]) if rows else pd.DataFrame()

col1, col2 = st.columns([3, 2])
col1.plotly_chart(fig, width='stretch')

with col2:
    if not rdf.empty:
        bar = go.Figure(go.Bar(
            x=rdf["Rasio"], y=rdf["Valuta"], orientation="h",
            marker_color=[E.STATUS_WARNA["Waspada"] if x >= ctx.ambang_rasio
                          else (E.STATUS_WARNA["Perhatian"] if x > 1.0 else E.STATUS_WARNA["Normal"])
                          for x in rdf["Rasio"]],
            text=[E.persen(x) for x in rdf["Rasio"]], textposition="outside"))
        bar.add_vline(x=ctx.ambang_rasio, line=dict(color=E.STATUS_WARNA["Waspada"], dash="dash"))
        bar.add_vline(x=1.0, line=dict(color=E.STATUS_WARNA["Perhatian"], dash="dot"))
        bar.update_layout(height=340, margin=dict(t=30, b=8, l=8, r=8),
                          title=dict(text="Rasio kurs tengah vs BI", font=dict(size=15)),
                          xaxis=dict(tickformat=".0%"))
        st.plotly_chart(bar, width='stretch')
    else:
        st.info("Valuta terpilih tidak punya acuan BI untuk dirasiokan.")

# ---- tabel rasio komponen ----
st.subheader(f"Rasio kurs {val} pada periode {ctx.lbl_h}")
tr = E.tabel_rasio_kurs(data, val, ctx.tgl_h, ctx.tgl_p, ctx.tgl_awal, ctx.pts,
                        ctx.ambang_rasio, gran=g)
acuan = tr.attrs.get("acuan")

view = pd.DataFrame({
    "Komponen": tr["Komponen"],
    "Awal": tr["Awal"], "Pembanding": tr["Pembanding"], "Tanggal cek": tr["Tanggal cek"],
    "Rasio vs BI": tr["Rasio vs BI"], "Status": tr["Status"],
    "Catatan": tr["Perhatian"].map({True: "> 100% (perhatian)", False: ""}),
})

def warna_status(v):
    c = E.STATUS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 500;" if c else ""

sty = (view.style.map(warna_status, subset=["Status"])
       .format({"Awal": E.angka, "Pembanding": E.angka, "Tanggal cek": E.angka,
                "Rasio vs BI": E.persen}))
st.dataframe(sty, width='stretch', hide_index=True)
st.caption(f"Acuan BI {val} pada {ctx.lbl_h}: "
           f"{E.angka(acuan) if acuan else '—'} "
           f"({'Kurs Jisdor' if val=='USD' else 'Kurs Tengah BI'}, forward-fill ke ujung periode).")

# ---- narasi otomatis ----
st.subheader("Narasi asesmen otomatis (§1)")
n_wasp = int((tr["Status"] == "Waspada").sum())
komp_txt = "; ".join(
    f"{r.Komponen.lower()} {E.persen(r['Rasio vs BI'])} ({r.Status})"
    for _, r in tr.iterrows() if pd.notna(r["Rasio vs BI"])
)
if n_wasp == 0:
    kes = (f"Tidak terdapat komponen kurs {val} berkategori Waspada (≥ {ctx.ambang_rasio:.0%}); "
           "seluruh objek monitoring tergolong Normal. Rasio di atas 100% tetap menjadi perhatian "
           "pengawasan namun belum melampaui ambang Waspada.")
else:
    kes = (f"Terdapat {n_wasp} komponen kurs {val} berkategori Waspada (≥ {ctx.ambang_rasio:.0%}); "
           "pendalaman penyebab perlu dilakukan terhadap KUPVA BB terkait.")
st.info(
    f"Pada periode {ctx.lbl_h} ({ctx.granularitas}), rasio kurs {val} terhadap acuan "
    f"Bank Indonesia: {komp_txt}. {kes}",
    icon="📝")
