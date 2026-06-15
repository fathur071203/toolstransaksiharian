"""Halaman Ringkasan Pengawasan (cockpit terintegrasi).

Menyambungkan §1 Kurs, §2 Volume, dan §3 Absensi dalam satu pandangan: KPI,
komposisi status ketiga pilar, dan matriks per-KUPVA yang menggabungkan absensi +
status kurs + status volume + status akhir untuk tanggal laporan terpilih.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import saksi_engine as E
from core.ui_helpers import require_auth, page_header, no_data_card, section_title

require_auth()
page_header("🛡️", "Ringkasan Pengawasan",
            "Cockpit terintegrasi · Absensi × Kurs × Volume per KUPVA")

data = E.get_data()
if data is None:
    no_data_card()
    st.stop()

cb = data["combine"]
hari_all = E.daftar_tanggal(cb)

# Peta warna gabungan (status kurs/volume + absensi)
WARNA = dict(E.STATUS_WARNA)
WARNA.update({"Lengkap": E.STATUS_WARNA["Normal"],
              "Sebagian": E.STATUS_WARNA["Perhatian"],
              "Belum lapor": E.STATUS_WARNA["Waspada"]})


def warna(v):
    c = WARNA.get(v)
    return f"background-color: {c}22; color: {c}; font-weight: 600;" if c else ""


# ----------------------------------------------------------------------------
# 1. PERIODE
# ----------------------------------------------------------------------------
gp = st.columns([1.2, 5])
gran = gp[0].selectbox("🗓️ Periode laporan", options=E.GRANULARITAS, index=0, key="rk_gran")
if gran != "Harian":
    st.info(f"Ringkasan **{gran}** sedang dalam pengembangan — saat ini baru **Harian** "
            "yang aktif (menyatukan Kurs & Volume harian). Pilih **Harian**.", icon="🚧")
    st.stop()

# ----------------------------------------------------------------------------
# 2. FILTER
# ----------------------------------------------------------------------------
with st.container(border=True):
    section_title("Filter ringkasan harian")
    r1 = st.columns([1.6, 0.7])
    tgl_h = r1[0].selectbox("📅 Tanggal laporan (H)", options=hari_all,
                            index=len(hari_all) - 1, format_func=E.fmt_tgl, key="rk_tgl")
    with r1[1].popover("⚙️ Ambang", use_container_width=True):
        ambang_r = st.slider("Waspada rasio kurs (≥)", 1.00, 1.20,
                             E.AMBANG_RASIO_DEFAULT, 0.01, key="rk_amb_r")
        ambang_v = st.slider("Waspada growth volume (≥)", 0.05, 0.50,
                             E.AMBANG_DTD_DEFAULT, 0.01, format="%.2f", key="rk_amb_v")

i_h = hari_all.index(tgl_h)
tgl_p = hari_all[i_h - 1] if i_h > 0 else None

mtx = E.ringkasan_kupva(data, tgl_h, tgl_p, ambang_r, ambang_v, gran="Harian")
total = len(mtx)
n_belum = int((mtx["Absensi"] == "Belum lapor").sum())
n_lapor = total - n_belum
n_kw = int((mtx["Status Kurs"] == "Waspada").sum())
n_kp = int((mtx["Status Kurs"] == "Perhatian").sum())
n_vw = int((mtx["Status Volume"] == "Waspada").sum())
n_aw = int((mtx["Status Akhir"] == "Waspada").sum())
tot_vol = float(mtx["Volume (Rp)"].sum())

st.caption(f"Laporan **Harian** · {E.fmt_tgl(tgl_h)} · pembanding volume "
           f"{E.fmt_tgl(tgl_p) if tgl_p is not None else '—'} · seluruh {total} KUPVA pada data")

# ----------------------------------------------------------------------------
# KPI
# ----------------------------------------------------------------------------
k = st.columns(6)
k[0].metric("Total KUPVA", total)
k[1].metric("Telah lapor", n_lapor)
k[2].metric("Belum lapor", n_belum)
k[3].metric("Waspada kurs", n_kw, help=f"Rasio ≥ {ambang_r:.0%} pada ≥1 valuta · Perhatian: {n_kp}")
k[4].metric("Waspada volume", n_vw, help=f"|growth dtd| ≥ {ambang_v:.0%} pada ≥1 valuta")
k[5].metric(f"Total volume", E.rupiah(tot_vol))

# ----------------------------------------------------------------------------
# CARD VIEW — ringkasan transaksi (seluruh KUPVA pada H)
# ----------------------------------------------------------------------------
sub_h = E.filter_cb(cb, tgl=tgl_h, gran="Harian")
v_jual = float(sub_h[E.C_JUAL_RP].sum())
v_beli = float(sub_h[E.C_BELI_RP].sum())
saldo = float(sub_h[E.C_SAK_RP].sum())
n_trx = int(len(sub_h))
n_val_aktif = int(sub_h[E.C_VAL].nunique())
n_lapor_h = int(sub_h[E.C_ID].nunique())

section_title(f"Ringkasan transaksi · {E.fmt_tgl(tgl_h)}")
t = st.columns(6)
t[0].metric("💵 Volume Jual", E.rupiah(v_jual))
t[1].metric("💴 Volume Beli", E.rupiah(v_beli))
t[2].metric("⚖️ Selisih Jual−Beli", E.rupiah(v_jual - v_beli),
            help="Positif = penjualan valas (oleh KUPVA) lebih besar dari pembelian.")
t[3].metric("🧾 Jumlah transaksi", f"{n_trx:,}".replace(",", "."))
t[4].metric("💱 Valuta aktif", n_val_aktif)
t[5].metric("🏦 KUPVA bertransaksi", n_lapor_h)

st.divider()


def donut(judul, seg):
    seg = [(lbl, val, col) for lbl, val, col in seg if val > 0]
    fig = go.Figure(go.Pie(
        labels=[s[0] for s in seg], values=[s[1] for s in seg],
        marker=dict(colors=[s[2] for s in seg], line=dict(color="#fff", width=1.5)),
        hole=0.62, textinfo="value", sort=False))
    fig.update_layout(title=dict(text=judul, font=dict(size=14)), showlegend=True, height=240,
                      margin=dict(t=42, b=8, l=8, r=8),
                      legend=dict(orientation="h", y=-0.18, font=dict(size=11)))
    return fig


d1, d2, d3 = st.columns(3)
d1.plotly_chart(donut("Absensi (§3)", [
    ("Lengkap", n_lapor, WARNA["Lengkap"]),
    ("Belum lapor", n_belum, WARNA["Belum lapor"])]), width="stretch")
d2.plotly_chart(donut("Status Kurs (§1)", [
    ("Normal", int((mtx["Status Kurs"] == "Normal").sum()), E.STATUS_WARNA["Normal"]),
    ("Perhatian", n_kp, E.STATUS_WARNA["Perhatian"]),
    ("Waspada", n_kw, E.STATUS_WARNA["Waspada"]),
    ("Tanpa data", int((mtx["Status Kurs"] == "Tanpa data").sum()), E.STATUS_WARNA["Tanpa data"])]),
    width="stretch")
d3.plotly_chart(donut("Status Volume (§2)", [
    ("Normal", int((mtx["Status Volume"] == "Normal").sum()), E.STATUS_WARNA["Normal"]),
    ("Waspada", n_vw, E.STATUS_WARNA["Waspada"]),
    ("Tanpa data", int((mtx["Status Volume"] == "Tanpa data").sum()), E.STATUS_WARNA["Tanpa data"])]),
    width="stretch")

# ----------------------------------------------------------------------------
# MATRIKS TERINTEGRASI per KUPVA
# ----------------------------------------------------------------------------
st.subheader("Matriks terintegrasi per KUPVA BB — Absensi × Kurs × Volume")
view = pd.DataFrame({
    "KUPVA BB": mtx["KUPVA BB"],
    "Absensi": mtx["Absensi"],
    "Jml valuta": mtx["Jml valuta"],
    "Status Kurs": mtx["Status Kurs"],
    "Status Volume": mtx["Status Volume"],
    "Volume (Rp)": mtx["Volume (Rp)"],
    "Status Akhir": mtx["Status Akhir"],
})
sty = (view.style.map(warna, subset=["Absensi", "Status Kurs", "Status Volume", "Status Akhir"])
       .format({"Volume (Rp)": lambda x: E.rupiah(x)}))
st.dataframe(sty, width="stretch", hide_index=True, height=440,
             column_config={"KUPVA BB": st.column_config.TextColumn(width="large")})
st.caption("Status Kurs/Volume = kondisi TERBURUK antar valuta yang ditransaksikan KUPVA pada H. "
           "Status Akhir = gabungan terburuk Kurs & Volume. KUPVA belum lapor → kurs/volume 'Tanpa data'.")

# ----------------------------------------------------------------------------
# NARASI TERINTEGRASI
# ----------------------------------------------------------------------------
belum = mtx[mtx["Absensi"] == "Belum lapor"]["KUPVA BB"].tolist()
wasp = mtx[mtx["Status Akhir"] == "Waspada"]["KUPVA BB"].tolist()
st.subheader("Narasi ringkasan otomatis")
st.info(
    f"Pada {E.fmt_tgl(tgl_h)}, dari **{total}** KUPVA BB: **{n_lapor}** telah lapor, "
    f"**{n_belum}** belum. Sisi kurs: {n_kw} Waspada, {n_kp} Perhatian; sisi volume: "
    f"{n_vw} Waspada. Secara gabungan, **{n_aw}** KUPVA berkategori Waspada"
    + (f" ({', '.join(wasp)})" if wasp else "")
    + (f". KUPVA belum lapor: {', '.join(belum)}." if belum else ".")
    + " Prioritaskan pendalaman pada KUPVA Waspada dan tindak lanjut penyampaian bagi yang belum lapor.",
    icon="📝")
