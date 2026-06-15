"""Halaman Monitoring Volume (§2) — Laporan Harian (konsep selaras §1 Kurs).

Alur:
  1. Pilih PERIODE (Harian aktif; lainnya placeholder).
  2. Filter Harian: Tanggal laporan → KUPVA terpilih → Valuta fokus (multi /
     semua valuta).
  3. Valuta tanpa transaksi di KUPVA → peringatan.
  4. ≥2 valuta → dropdown 'valuta grafik' mengatur grafik volume & growth.
     TABEL tetap menampilkan seluruh valuta.
  5. Grafik volume: bar Jual & Beli (Rp) 3 hari terakhir. Grafik growth: tren
     growth dtd Jual & Beli dengan ambang ±waspada.
  6. Tabel lebar: per valuta Jual & Beli (H vs pembanding) + growth + status,
     plus Total & Status Akhir.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth, page_header, no_data_card, section_title

require_auth()
page_header("📊", "Monitoring Volume — Laporan Harian (§2)",
            "Pertumbuhan volume transaksi (Jual & Beli) day-to-day per valuta")

data = E.get_data()
if data is None:
    no_data_card()
    st.stop()

cb = data["combine"]
hari_all = E.daftar_tanggal(cb)
vals_all = E.daftar_valuta(cb)
pts_all = E.daftar_pt(cb)
nama = lambda p: data["nama_map"].get(p, p)

# ----------------------------------------------------------------------------
# 1. PERIODE
# ----------------------------------------------------------------------------
gp = st.columns([1.2, 5])
gran = gp[0].selectbox("🗓️ Periode laporan", options=E.GRANULARITAS, index=0, key="vol_gran")
if gran != "Harian":
    st.info(f"Laporan **{gran}** sedang dalam pengembangan — saat ini baru **Harian** "
            "yang aktif. Pilih **Harian** untuk melanjutkan.", icon="🚧")
    st.stop()

# ----------------------------------------------------------------------------
# 2. FILTER LAPORAN VOLUME HARIAN
# ----------------------------------------------------------------------------
with st.container(border=True):
    section_title("Filter laporan volume harian")

    pov = st.radio("👁️ Sudut pandang",
                   ["🚁 Keseluruhan (helicopter view)", "🏦 Per KUPVA (individu)"],
                   horizontal=True, key="vol_pov")
    individu = pov.startswith("🏦")

    r1 = st.columns([1.4, 2.4, 0.6])
    tgl_h = r1[0].selectbox("📅 Tanggal laporan (H)", options=hari_all,
                            index=len(hari_all) - 1, format_func=E.fmt_tgl, key="vol_tgl")
    if individu:
        pid = r1[1].selectbox("🏦 KUPVA terpilih", options=pts_all, format_func=nama, key="vol_pt")
        subjek_pts, subjek_label = [pid], nama(pid)
    else:
        r1[1].markdown(f'<div style="margin-top:26px;font-weight:600;color:#33475b;">'
                       f'🚁 Agregat seluruh <b>{len(pts_all)}</b> KUPVA (volume dijumlahkan)</div>',
                       unsafe_allow_html=True)
        subjek_pts, subjek_label = list(pts_all), f"Seluruh KUPVA ({len(pts_all)})"
    with r1[2].popover("⚙️", use_container_width=True):
        ambang = st.slider("Ambang Waspada growth (≥)", 0.05, 0.50,
                           E.AMBANG_DTD_DEFAULT, 0.01, format="%.2f", key="vol_amb")
        st.caption(f"Waspada bila |growth dtd| ≥ {ambang:.0%}.")

    semua = st.checkbox("💱 Pilih semua valuta", key="vol_semua_val")
    _vdef = [v for v in ["USD"] if v in vals_all] or vals_all[:1]
    fokus_sel = st.multiselect("🎯 Valuta fokus (boleh lebih dari satu)", options=vals_all,
                               default=_vdef, key="vol_fokus", disabled=semua)
    fokus_list = list(vals_all) if semua else (fokus_sel or _vdef)

# 3 hari transaksi terakhir s/d H + pembanding (hari transaksi sebelum H)
hari = [t for t in hari_all if pd.Timestamp(t) <= pd.Timestamp(tgl_h)][-3:]
lbl_x = [E.fmt_tgl(t) for t in hari]
i_h = hari_all.index(tgl_h)
tgl_p = hari_all[i_h - 1] if i_h > 0 else None

# Valuta yang benar-benar ditransaksikan subjek (KUPVA / seluruh KUPVA) pada H
val_pt = E.valuta_pt_pada(data, subjek_pts, tgl_h, gran="Harian")
tersedia = [v for v in fokus_list if v in val_pt]
tidak_ada = [v for v in fokus_list if v not in val_pt]

st.caption(f"Laporan **Harian** · {E.fmt_tgl(tgl_h)} · {subjek_label} · "
           f"pembanding {E.fmt_tgl(tgl_p) if tgl_p is not None else '—'} · "
           f"valuta fokus: {', '.join(fokus_list)}")

if tidak_ada:
    st.warning(f"🚫 **Tidak ada transaksi** pada {E.fmt_tgl(tgl_h)} ({subjek_label}) "
               f"untuk valuta: **{', '.join(tidak_ada)}**. Valuta tersebut dikecualikan.",
               icon="⚠️")

if not tersedia:
    st.info(f"Tidak ada valuta fokus yang ditransaksikan pada tanggal ini ({subjek_label}). "
            "Ubah tanggal / sudut pandang / valuta fokus.", icon="ℹ️")
    st.stop()

if tgl_p is not None and E.is_weekend(tgl_p):
    st.warning(f"Pembanding ({E.fmt_tgl(tgl_p)}) jatuh pada akhir pekan — basis berpotensi "
               "rendah; baca persentase growth dtd dengan hati-hati.", icon="⚠️")

# ----------------------------------------------------------------------------
# 3. Pemilih valuta grafik (muncul bila ≥ 2 valuta tersedia)
# ----------------------------------------------------------------------------
if len(tersedia) >= 2:
    g_val = st.selectbox("📈 Valuta untuk grafik (volume & growth)", options=tersedia, key="vol_gval")
else:
    g_val = tersedia[0]

# ----------------------------------------------------------------------------
# GRAFIK 1 — Volume Jual & Beli (Rp), 3 hari
# ----------------------------------------------------------------------------
vrows = []
for t in hari:
    j, b = E.volume_jual_beli_lapor(cb, t, [g_val], subjek_pts, gran="Harian")
    vrows.append({"Tanggal": E.fmt_tgl(t), "Jual": j, "Beli": b})
vdf = pd.DataFrame(vrows)

fig = go.Figure()
fig.add_trace(go.Bar(x=vdf["Tanggal"], y=vdf["Jual"], name="Volume Jual", marker_color="#185FA5"))
fig.add_trace(go.Bar(x=vdf["Tanggal"], y=vdf["Beli"], name="Volume Beli", marker_color="#1D9E75"))
fig.update_layout(height=380, barmode="group", margin=dict(t=36, b=8, l=8, r=8),
                  title=dict(text=f"Volume {g_val} (Rp) — {subjek_label} (3 hari terakhir)",
                             font=dict(size=15)),
                  legend=dict(orientation="h", y=-0.18), hovermode="x unified",
                  xaxis=dict(type="category"))

# ----------------------------------------------------------------------------
# GRAFIK 2 — Tren growth dtd Jual & Beli, 3 hari
# ----------------------------------------------------------------------------
grows = []
for t in hari:
    it = hari_all.index(t)
    prev = hari_all[it - 1] if it > 0 else None
    jh, bh = E.volume_jual_beli_lapor(cb, t, [g_val], subjek_pts, gran="Harian")
    if prev is not None:
        jp, bp = E.volume_jual_beli_lapor(cb, prev, [g_val], subjek_pts, gran="Harian")
    else:
        jp = bp = np.nan
    grows.append({"Tanggal": E.fmt_tgl(t),
                  "Growth Jual": E.growth(jh, jp), "Growth Beli": E.growth(bh, bp)})
gdf = pd.DataFrame(grows)
ada_growth = gdf[["Growth Jual", "Growth Beli"]].notna().any().any()

gfig = go.Figure()
if ada_growth:
    gfig.add_trace(go.Scatter(x=gdf["Tanggal"], y=gdf["Growth Jual"], name="Growth Jual",
                              mode="lines+markers", line=dict(color="#185FA5", width=2.6),
                              marker=dict(size=9)))
    gfig.add_trace(go.Scatter(x=gdf["Tanggal"], y=gdf["Growth Beli"], name="Growth Beli",
                              mode="lines+markers", line=dict(color="#1D9E75", width=2.6),
                              marker=dict(size=9)))
    for y in (ambang, -ambang):
        gfig.add_hline(y=y, line=dict(color=E.STATUS_WARNA["Waspada"], dash="dash"),
                       annotation_text=f"{y:+.0%}", annotation_position="top left",
                       annotation_font_size=10)
    gfig.add_hline(y=0, line=dict(color="#888780", dash="dot"))
    gfig.update_layout(height=380, margin=dict(t=36, b=8, l=8, r=8),
                       title=dict(text=f"Growth dtd {g_val} — {subjek_label}", font=dict(size=15)),
                       yaxis=dict(tickformat=".0%"), hovermode="x unified",
                       legend=dict(orientation="h", y=-0.18), xaxis=dict(type="category"))

c1, c2 = st.columns([3, 2])
c1.plotly_chart(fig, width="stretch")
with c2:
    if not ada_growth:
        st.info(f"Growth dtd {g_val} tak tersedia (basis pembanding 0 / tidak ada).")
    else:
        st.plotly_chart(gfig, width="stretch")

# ----------------------------------------------------------------------------
# TABEL LEBAR — seluruh valuta tersedia
# ----------------------------------------------------------------------------
st.subheader(f"Rincian volume {subjek_label} pada {E.fmt_tgl(tgl_h)} (Jual · Beli, growth dtd)")
tbl = E.tabel_volume_komponen(data, subjek_pts, tgl_h, tgl_p, tersedia, ambang, gran="Harian")


def warna_status(v):
    c = E.STATUS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 600;" if c else ""


def tandai_kosong(v):
    """Sel tanpa data (NaN) → abu & miring, agar jelas 'tidak ada data', bukan 0."""
    return ("background-color: #8887801a; color: #888780; font-style: italic;"
            if pd.isna(v) else "")


fmt_map = {
    "Jual (H)": E.rupiah, "Jual (Pemb.)": E.rupiah, "Growth Jual": E.persen,
    "Beli (H)": E.rupiah, "Beli (Pemb.)": E.rupiah, "Growth Beli": E.persen,
    "Total (H)": E.rupiah,
}
status_cols = ["Status Jual", "Status Beli", "Status Akhir"]
sty = (tbl.style
       .map(warna_status, subset=status_cols)
       .map(tandai_kosong, subset=list(fmt_map.keys()))
       .format(fmt_map, na_rep="tidak ada data"))
st.dataframe(sty, width="stretch", hide_index=True)
st.caption("Growth dtd = (H − pembanding) ÷ pembanding · sel **tidak ada data** "
           "(KUPVA tak melapor/bertransaksi) ditandai abu & tidak dihitung sebagai 0 · "
           f"Status Waspada bila |growth| ≥ {ambang:.0%} · Status Akhir = paling berat antar sisi.")

# ----------------------------------------------------------------------------
# NARASI OTOMATIS (§2)
# ----------------------------------------------------------------------------
st.subheader("Narasi asesmen otomatis (§2)")
n_w = int((tbl["Status Akhir"] == "Waspada").sum())
val_w = ", ".join(tbl.loc[tbl["Status Akhir"] == "Waspada", "Valuta"])
catatan = (" Catatan: tanggal pembanding jatuh pada akhir pekan/non-transaksi sehingga basis "
           "rendah — baca growth dtd dengan hati-hati."
           if tgl_p is not None and E.is_weekend(tgl_p) else "")
if n_w == 0:
    kes = f"Tidak ada valuta dengan pertumbuhan volume ≥ {ambang:.0%} (seluruhnya Normal)."
else:
    kes = (f"{n_w} valuta berkategori Waspada (growth dtd ≥ {ambang:.0%}): {val_w}. "
           "Perlu pendalaman penyebab terhadap KUPVA terkait.")
st.info(f"Pada {E.fmt_tgl(tgl_h)} (Harian) vs pembanding "
        f"{E.fmt_tgl(tgl_p) if tgl_p is not None else '—'}, asesmen volume {subjek_label} atas "
        f"{len(tersedia)} valuta ({', '.join(tersedia)}): {kes}{catatan}", icon="📝")
