"""Halaman Ringkasan Pengawasan (cockpit) — KPI, status kurs & volume, matriks per-KUPVA."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth

require_auth()

ctx = E.bootstrap("Ringkasan Pengawasan", "🛡️",
                  "Cockpit KPI · status kurs & volume · matriks per-KUPVA")
data, cb = ctx.data, ctx.data["combine"]
pts_all = E.daftar_pt(cb)

g = ctx.granularitas

# ---- hitung ----
n_lapor = E.filter_cb(cb, tgl=ctx.tgl_h, pts=ctx.pts, gran=g)[E.C_ID].nunique()
tot_vol = E.volume_total(cb, ctx.tgl_h, valutas=None, pts=ctx.pts, gran=g)  # semua valuta

mtx = E.matriks_per_kupva(data, ctx.valuta_fokus, ctx.valutas, ctx.tgl_h, ctx.tgl_p,
                          ctx.pts, ctx.ambang_rasio, ctx.ambang_dtd, gran=g)
mtx = mtx[mtx["ID"].isin(ctx.pts)].copy()

absn = E.tabel_absensi(data, ctx.tgl_h, ctx.pts, gran=g)
absn = absn[absn["ID"].isin(ctx.pts)]
n_belum = int((absn["Status"] == "Belum lapor").sum())

n_wasp_kurs = int((mtx["Status Kurs"] == "Waspada").sum())
n_wasp_vol = int((mtx["Status Volume"] == "Waspada").sum())
v_tanpa = E.valuta_tanpa_acuan(data, ctx.tgl_h, ctx.pts, gran=g)
n_tanpa = len(v_tanpa)

# ---- KPI ----
k = st.columns(6)
k[0].metric("KUPVA dipantau", f"{n_lapor} / {len(ctx.pts)}")
k[1].metric(f"Total volume · {ctx.lbl_h}", E.rupiah(tot_vol))
k[2].metric("Waspada kurs", n_wasp_kurs, help=f"Rasio kurs ≥ {ctx.ambang_rasio:.2f} pada valuta fokus {ctx.valuta_fokus}")
k[3].metric("Waspada volume", n_wasp_vol, delta=None,
            help=f"|growth periode| ≥ {ctx.ambang_dtd:.0%}")
k[4].metric("Belum lapor", n_belum, help="Tidak ada baris transaksi pada periode cek")
k[5].metric("Valuta tanpa acuan", n_tanpa, help="Diperdagangkan namun tak ada Kurs Tengah/Jisdor BI")

st.divider()


# ---- donut helper ----
def donut(judul, seg):
    seg = [(lbl, val, col) for lbl, val, col in seg if val > 0]
    fig = go.Figure(go.Pie(
        labels=[s[0] for s in seg], values=[s[1] for s in seg],
        marker=dict(colors=[s[2] for s in seg], line=dict(color="#ffffff", width=1.5)),
        hole=0.62, textinfo="value", sort=False, direction="clockwise",
    ))
    fig.update_layout(
        title=dict(text=judul, font=dict(size=15)),
        showlegend=True, height=240, margin=dict(t=42, b=8, l=8, r=8),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, font=dict(size=12)),
    )
    return fig


c1, c2 = st.columns(2)
sk = mtx["Status Kurs"].replace("-", "Tanpa data")
c1.plotly_chart(donut(
    f"Status kurs · {ctx.valuta_fokus}",
    [("Normal", int((sk == "Normal").sum()), E.STATUS_WARNA["Normal"]),
     ("Waspada", int((sk == "Waspada").sum()), E.STATUS_WARNA["Waspada"]),
     ("Tanpa data", int((sk == "Tanpa data").sum()), E.STATUS_WARNA["Tanpa data"])],
), width='stretch')

sv = mtx["Status Volume"].replace("-", "Tanpa data")
c2.plotly_chart(donut(
    "Status volume · gabungan valuta terpilih",
    [("Waspada", int((sv == "Waspada").sum()), E.STATUS_WARNA["Waspada"]),
     ("Normal", int((sv == "Normal").sum()), E.STATUS_WARNA["Normal"]),
     ("Tanpa data", int((sv == "Tanpa data").sum()), E.STATUS_WARNA["Tanpa data"])],
), width='stretch')

# ---- matriks per-KUPVA ----
st.subheader("Matriks status per KUPVA BB")

view = pd.DataFrame({
    "KUPVA BB": mtx["KUPVA BB"],
    "Lapor": mtx["Lapor H"].map({True: "✓", False: "—"}),
    "Status kurs": mtx["Status Kurs"],
    "Rasio kurs": mtx["Rasio vs BI"],
    "Growth jual": mtx["Growth Jual"],
    "Growth beli": mtx["Growth Beli"],
    "Status volume": mtx["Status Volume"],
})


def warna_status(val):
    c = E.STATUS_WARNA.get(val)
    return f"background-color: {c}22; color: {c}; font-weight: 500;" if c else ""


sty = (view.style
       .map(warna_status, subset=["Status kurs", "Status volume"])
       .format({"Rasio kurs": lambda v: E.persen(v) if pd.notna(v) and v != 0 else "—",
                "Growth jual": lambda v: E.persen(v) if pd.notna(v) else "—",
                "Growth beli": lambda v: E.persen(v) if pd.notna(v) else "—"}))

st.dataframe(sty, width='stretch', hide_index=True, height=430,
             column_config={"KUPVA BB": st.column_config.TextColumn(width="large")})

st.caption(
    "Status kurs 2-tingkat (Normal/Waspada) konsisten dengan sheet Summary; rasio > 100% "
    "menjadi catatan perhatian pengawasan. Growth volume dihitung day-to-day (H vs pembanding)."
)
