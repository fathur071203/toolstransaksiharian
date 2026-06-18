"""Halaman Monitoring Kurs (§1) — Laporan Harian (konsep baru).

Alur:
  1. Pilih PERIODE (Harian/Mingguan/Bulanan/Triwulanan/Tahunan). Saat ini hanya
     **Harian** yang aktif; lainnya placeholder (dalam pengembangan).
  2. Filter Harian: Tanggal laporan → KUPVA terpilih → Valuta fokus (multi /
     semua valuta).
  3. Valuta yang tak ada transaksinya di KUPVA → diberi peringatan.
  4. Bila ≥2 valuta → dropdown 'valuta grafik' mengatur grafik kurs & rasio
     tengah; TABEL tetap menampilkan seluruh valuta.
  5. Grafik kurs: BI (beli/tengah/jual) vs KUPVA (beli/tengah/jual), 3 hari
     terakhir (H, H-1, H-2). Grafik rasio: rasio kurs tengah (KUPVA/BI) 3 hari.
  6. Tabel lebar: per valuta Beli/Jual/Tengah (KUPVA vs BI) + rasio + status,
     plus Status Akhir.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import (require_auth, page_header, no_data_card, section_title,
                             filter_harian_mode)

require_auth()
page_header("💱", "Monitoring Kurs — Laporan Harian (§1)",
            "Kurs KUPVA terpilih vs Bank Indonesia + rasio per valuta")

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
gran = gp[0].selectbox("🗓️ Periode laporan", options=E.GRANULARITAS, index=0, key="kurs_gran")
if gran != "Harian":
    gp[1].markdown("&nbsp;")
    st.info(f"Laporan **{gran}** sedang dalam pengembangan — saat ini baru **Harian** "
            "yang aktif. Pilih **Harian** untuk melanjutkan.", icon="🚧")
    st.stop()

# ----------------------------------------------------------------------------
# 2. FILTER LAPORAN KURS HARIAN
# ----------------------------------------------------------------------------
with st.container(border=True):
    section_title("Filter laporan kurs harian")

    pov = st.radio("👁️ Sudut pandang",
                   ["🚁 Keseluruhan (helicopter view)", "🏦 Per KUPVA (individu)"],
                   horizontal=True, key="kurs_pov")
    individu = pov.startswith("🏦")

    tgl_h, hari, is_series = filter_harian_mode(hari_all, "kurs")

    r1 = st.columns([3.4, 0.6])
    if individu:
        pid = r1[0].selectbox("🏦 KUPVA terpilih", options=pts_all, format_func=nama, key="kurs_pt")
        subjek_pts, subjek_label, seri = [pid], nama(pid), "KUPVA"
    else:
        r1[0].markdown(f'<div style="margin-top:26px;font-weight:600;color:#33475b;">'
                       f'🚁 Agregat seluruh <b>{len(pts_all)}</b> KUPVA (rata-rata kurs)</div>',
                       unsafe_allow_html=True)
        subjek_pts, subjek_label, seri = list(pts_all), f"Seluruh KUPVA ({len(pts_all)})", "Rata-rata KUPVA"
    with r1[1].popover("⚙️", use_container_width=True):
        ambang = st.slider("Ambang Waspada rasio (≥)", 1.00, 1.20,
                           E.AMBANG_RASIO_DEFAULT, 0.01, key="kurs_amb")
        st.caption(f"< 100% Normal · 100%–{ambang:.0%} Perhatian · ≥ {ambang:.0%} Waspada.")

    semua = st.checkbox("💱 Pilih semua valuta", key="kurs_semua_val")
    _vdef = [v for v in ["USD"] if v in vals_all] or vals_all[:1]
    fokus_sel = st.multiselect("🎯 Valuta fokus (boleh lebih dari satu)", options=vals_all,
                               default=_vdef, key="kurs_fokus", disabled=semua)
    fokus_list = list(vals_all) if semua else (fokus_sel or _vdef)

# Deret tanggal untuk grafik (3 hari terakhir / sepanjang rentang series)
lbl_x = [E.fmt_tgl(t) for t in hari]
rentang_lbl = (f"series {lbl_x[0]} – {lbl_x[-1]} ({len(hari)} hari)"
               if is_series else f"{len(hari)} hari terakhir")

# Valuta yang benar-benar ditransaksikan subjek (KUPVA / seluruh KUPVA) pada H
val_pt = E.valuta_pt_pada(data, subjek_pts, tgl_h, gran="Harian")
tersedia = [v for v in fokus_list if v in val_pt]
tidak_ada = [v for v in fokus_list if v not in val_pt]

st.caption(f"Laporan **Harian** · {'tanggal akhir ' if is_series else ''}{E.fmt_tgl(tgl_h)} · "
           f"{subjek_label} · valuta fokus: {', '.join(fokus_list)} · grafik {rentang_lbl}")

if tidak_ada:
    st.warning(f"🚫 **Tidak ada transaksi** pada {E.fmt_tgl(tgl_h)} ({subjek_label}) "
               f"untuk valuta: **{', '.join(tidak_ada)}**. Valuta tersebut dikecualikan "
               "dari grafik & tabel.", icon="⚠️")

if not tersedia:
    st.info(f"Tidak ada valuta fokus yang ditransaksikan pada tanggal ini ({subjek_label}). "
            "Ubah tanggal / sudut pandang / valuta fokus.", icon="ℹ️")
    st.stop()

# ----------------------------------------------------------------------------
# 3. Pemilih valuta grafik (muncul bila ≥ 2 valuta tersedia)
# ----------------------------------------------------------------------------
if len(tersedia) >= 2:
    g_val = st.selectbox("📈 Valuta untuk grafik (kurs & rasio tengah)", options=tersedia,
                         key="kurs_gval")
else:
    g_val = tersedia[0]

# ----------------------------------------------------------------------------
# GRAFIK 1 — Kurs BI vs KUPVA (beli/tengah/jual), 3 hari
# ----------------------------------------------------------------------------
rows = []
for t in hari:
    bi = E.kurs_bi_komponen(data, g_val, t)
    pt = E.kurs_rata2(cb, t, g_val, subjek_pts, gran="Harian", acuan=bi["tengah"])
    rows.append({
        "Tanggal": E.fmt_tgl(t),
        "BI Beli": bi["beli"], "BI Tengah": bi["tengah"], "BI Jual": bi["jual"],
        "Subj Beli": pt["beli"], "Subj Tengah": pt["tengah"], "Subj Jual": pt["jual"],
    })
df1 = pd.DataFrame(rows)

WARNA = {"Beli": "#1D9E75", "Tengah": "#185FA5", "Jual": "#E24B4A"}
fig = go.Figure()
for komp, c in WARNA.items():
    fig.add_trace(go.Scatter(x=df1["Tanggal"], y=df1[f"BI {komp}"], name=f"BI {komp}",
                             mode="lines+markers", legendgroup="BI",
                             line=dict(color=c, width=2, dash="dash"),
                             marker=dict(symbol="square", size=7)))
    fig.add_trace(go.Scatter(x=df1["Tanggal"], y=df1[f"Subj {komp}"], name=f"{seri} {komp}",
                             mode="lines+markers", legendgroup="subj",
                             line=dict(color=c, width=2.6), marker=dict(symbol="circle", size=9)))
fig.update_layout(height=380, margin=dict(t=36, b=8, l=8, r=8),
                  title=dict(text=f"Kurs {g_val} — {subjek_label} vs Bank Indonesia ({rentang_lbl})",
                             font=dict(size=15)),
                  legend=dict(orientation="h", y=-0.18), hovermode="x unified",
                  xaxis=dict(type="category"))

# ----------------------------------------------------------------------------
# GRAFIK 2 — Rasio kurs Beli/Tengah/Jual (KUPVA/BI) dalam 1 grafik, 3 hari
# ----------------------------------------------------------------------------
rrows = []
for t in hari:
    bi = E.kurs_bi_komponen(data, g_val, t)
    pt = E.kurs_rata2(cb, t, g_val, subjek_pts, gran="Harian", acuan=bi["tengah"])
    rrows.append({
        "Tanggal": E.fmt_tgl(t),
        "Rasio Beli": E.hitung_rasio(pt["beli"], bi["beli"]),
        "Rasio Tengah": E.hitung_rasio(pt["tengah"], bi["tengah"]),
        "Rasio Jual": E.hitung_rasio(pt["jual"], bi["jual"]),
    })
rdf = pd.DataFrame(rrows)
ada_rasio = rdf[["Rasio Beli", "Rasio Tengah", "Rasio Jual"]].notna().any().any()

rfig = go.Figure()
if ada_rasio:
    for komp, c in WARNA.items():
        rfig.add_trace(go.Scatter(
            x=rdf["Tanggal"], y=rdf[f"Rasio {komp}"], name=f"Rasio {komp}",
            mode="lines+markers", line=dict(color=c, width=2.6), marker=dict(size=9)))
    rfig.add_hline(y=ambang, line=dict(color=E.STATUS_WARNA["Waspada"], dash="dash"),
                   annotation_text=f"Waspada {ambang:.0%}", annotation_position="top left",
                   annotation_font_size=10)
    rfig.add_hline(y=1.0, line=dict(color=E.STATUS_WARNA["Perhatian"], dash="dot"),
                   annotation_text="100%", annotation_position="bottom left",
                   annotation_font_size=10)
    rfig.update_layout(height=380, margin=dict(t=36, b=8, l=8, r=8),
                       title=dict(text=f"Rasio kurs (beli/tengah/jual) {g_val} — {subjek_label} vs BI",
                                  font=dict(size=15)),
                       yaxis=dict(tickformat=".1%"), hovermode="x unified",
                       legend=dict(orientation="h", y=-0.18), xaxis=dict(type="category"))

c1, c2 = st.columns([3, 2])
c1.plotly_chart(fig, width="stretch")
with c2:
    if not ada_rasio:
        st.info(f"Rasio {g_val} tak tersedia (acuan BI / kurs tidak memadai).")
    else:
        st.plotly_chart(rfig, width="stretch")

# ----------------------------------------------------------------------------
# TABEL LEBAR — seluruh valuta tersedia
#   Satu hari  → satu tabel (tanggal H).
#   Series     → tabel ditumpuk PER TANGGAL (kolom Tanggal di depan).
# ----------------------------------------------------------------------------
tbl = E.tabel_kurs_komponen(data, subjek_pts, tgl_h, tersedia, ambang, gran="Harian")  # H → narasi

if is_series:
    st.subheader(f"Rincian kurs {subjek_label} per tanggal "
                 f"({lbl_x[0]} – {lbl_x[-1]}) (Beli · Jual · Tengah)")
    parts = []
    for t in hari:
        val_t = [v for v in fokus_list if v in E.valuta_pt_pada(data, subjek_pts, t, gran="Harian")]
        if not val_t:
            continue
        tt = E.tabel_kurs_komponen(data, subjek_pts, t, val_t, ambang, gran="Harian")
        tt.insert(0, "Tanggal", E.fmt_tgl(t))
        parts.append(tt)
    tbl_show = pd.concat(parts, ignore_index=True) if parts else tbl.copy()
else:
    st.subheader(f"Rincian kurs {subjek_label} pada {E.fmt_tgl(tgl_h)} (Beli · Jual · Tengah)")
    tbl_show = tbl


def warna_status(v):
    c = E.STATUS_WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 600;" if c else ""


def tandai_kosong(v):
    """Sel tanpa data (NaN) → abu & miring, agar jelas 'tidak ada data', bukan 0."""
    return ("background-color: #8887801a; color: #888780; font-style: italic;"
            if pd.isna(v) else "")


fmt_map = {}
for label in ("Beli", "Jual", "Tengah"):
    fmt_map[f"{label} KUPVA"] = E.angka
    fmt_map[f"{label} BI"] = E.angka
    fmt_map[f"Rasio {label}"] = E.persen
status_cols = ["Status Beli", "Status Jual", "Status Tengah", "Status Akhir"]
sty = (tbl_show.style
       .map(warna_status, subset=status_cols)
       .map(tandai_kosong, subset=list(fmt_map.keys()))
       .format(fmt_map, na_rep="tidak ada data"))
st.dataframe(sty, width="stretch", hide_index=True,
             height=(430 if is_series else "content"))
st.caption("Rasio = Kurs KUPVA ÷ Kurs BI · sel **tidak ada data** ditandai abu (bukan 0) · "
           f"Status per komponen 3-tingkat · Status Akhir = paling berat · ambang Waspada ≥ {ambang:.0%}."
           + (" · baris dikelompokkan per **Tanggal** sepanjang rentang series." if is_series else ""))

# ----------------------------------------------------------------------------
# NARASI OTOMATIS (§1)
# ----------------------------------------------------------------------------
st.subheader("Narasi asesmen otomatis (§1)")
n_w = int((tbl["Status Akhir"] == "Waspada").sum())
n_p = int((tbl["Status Akhir"] == "Perhatian").sum())
val_w = ", ".join(tbl.loc[tbl["Status Akhir"] == "Waspada", "Valuta"])
val_p = ", ".join(tbl.loc[tbl["Status Akhir"] == "Perhatian", "Valuta"])
if n_w == 0 and n_p == 0:
    kes = "Seluruh valuta tergolong Normal (rasio < 100%)."
elif n_w == 0:
    kes = f"{n_p} valuta berkategori Perhatian (100%–{ambang:.0%}): {val_p}. Belum Waspada namun dipantau."
else:
    kes = (f"{n_w} valuta berkategori Waspada (≥ {ambang:.0%}): {val_w}"
           + (f"; {n_p} valuta Perhatian: {val_p}" if n_p else "")
           + ". Perlu pendalaman penyebab terhadap KUPVA terkait.")
st.info(f"Pada {E.fmt_tgl(tgl_h)} (Harian), asesmen kurs {subjek_label} atas "
        f"{len(tersedia)} valuta ({', '.join(tersedia)}): {kes}", icon="📝")
