"""
SAKSI - Monitor Harian Transaksi KUPVA BB
==========================================
Engine inti: pemuatan data, normalisasi, dan seluruh perhitungan pengawasan.

Logika di sini diverifikasi 1:1 terhadap sheet `Summary` & `Laporan Asesmen`
pada workbook sumber (KPwBI DKI Jakarta):
  - KUPVA dipantau (H)        -> jumlah PT unik yang punya baris transaksi di tanggal cek
  - Total volume (H)          -> sum(Penjualan Rp + Pembelian Rp), seluruh valuta, PT terpilih
  - Volume "Jual"             -> kolom 'Volume Penjualan dalam Rupiah'
  - Volume "Beli"             -> kolom 'Volume Pembelian dalam Rupiah'
  - Growth dtd                -> (H - pembanding) / pembanding
  - Kurs rata2 KUPVA          -> ROBUST MEAN (buang nilai <= 0 & di luar acuan BI*[0.5..2])
  - Acuan BI                  -> USD = Kurs Jisdor (forward-fill); valuta lain = Kurs Tengah BI (ffill)
  - Rasio kurs                -> kurs_komponen_rata2 / acuan_BI
  - Status kurs               -> Waspada >= 1.05 ; Perhatian > 1.00 ; selain itu Normal
  - Status volume             -> Waspada bila |growth| >= 0.15
"""

from __future__ import annotations
import io
import hashlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# Konstanta domain
# ----------------------------------------------------------------------------
SHEET_COMBINE = "Combine"
SHEET_TENGAH = "Kurs Tengah"
SHEET_JISDOR = "Kurs Jisdor"

C_PT = "Nama PT (Lengkap"          # catatan: header sumber memang tanpa kurung tutup
C_ID = "ID PT"
C_TGL = "Tanggal"
C_VAL = "Mata Uang"
C_JENIS = "Jenis Valuta"
C_SAW_VAL = "Saldo Awal dalam Valas"
C_SAW_RP = "Saldo Awal dalam Rupiah"
C_BELI_VAL = "Volume Pembelian dalam Valas"
C_BELI_RP = "Volume Pembelian dalam Rupiah"
C_JUAL_VAL = "Volume Penjualan dalam Valas"
C_JUAL_RP = "Volume Penjualan dalam Rupiah"
C_SAK_VAL = "Saldo Akhir dalam Valas"
C_KBELI = "Kurs Beli"
C_KTENGAH = "Kurs Tengah"
C_KJUAL = "Kurs Jual"
C_SAK_RP = "Saldo Akhir dalam Rupiah"

# Valuta sensitif geopolitik (untuk halaman Risiko Valuta "Pasca Perang & Politik")
VALUTA_SENSITIF = {
    "RUB": "Rusia", "IQD": "Irak", "TRY": "Turki", "EGP": "Mesir",
    "JOD": "Yordania", "BHD": "Bahrain", "QAR": "Qatar", "OMR": "Oman",
    "KWD": "Kuwait", "SAR": "Arab Saudi", "LKR": "Sri Lanka",
}

AMBANG_RASIO_DEFAULT = 1.05
AMBANG_DTD_DEFAULT = 0.15

STATUS_WARNA = {
    "Normal": "#1D9E75",
    "Perhatian": "#BA7517",
    "Waspada": "#E24B4A",
    "Tanpa data": "#888780",
    "-": "#888780",
}


# ----------------------------------------------------------------------------
# 1. Pemuatan & normalisasi data
# ----------------------------------------------------------------------------
def _norm_kode(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper()


def _load_data_raw(file_bytes: bytes) -> dict:
    """Baca 3 sheet inti dari bytes Excel, normalisasi, kembalikan dict df.
    Versi tanpa cache supaya bisa diuji di luar runtime Streamlit."""
    bio = io.BytesIO(file_bytes)
    xls = pd.ExcelFile(bio, engine="openpyxl")
    sheets = set(xls.sheet_names)
    missing = [s for s in (SHEET_COMBINE, SHEET_TENGAH, SHEET_JISDOR) if s not in sheets]
    if missing:
        raise ValueError(
            "Sheet wajib tidak ditemukan: " + ", ".join(missing)
            + ". Pastikan workbook memuat 'Combine', 'Kurs Tengah', dan 'Kurs Jisdor'."
        )

    cb = pd.read_excel(xls, sheet_name=SHEET_COMBINE)
    kt = pd.read_excel(xls, sheet_name=SHEET_TENGAH)
    kj = pd.read_excel(xls, sheet_name=SHEET_JISDOR)

    # --- Combine ---
    cb[C_VAL] = _norm_kode(cb[C_VAL])
    cb["Tgl"] = pd.to_datetime(cb[C_TGL]).dt.normalize()
    for c in (C_JUAL_RP, C_BELI_RP, C_JUAL_VAL, C_BELI_VAL, C_SAK_RP, C_SAW_RP,
              C_KBELI, C_KTENGAH, C_KJUAL, C_SAK_VAL):
        cb[c] = pd.to_numeric(cb[c], errors="coerce").fillna(0)
    # peta ID -> nama lengkap
    nama_map = (cb[[C_ID, C_PT]].dropna().drop_duplicates()
                .set_index(C_ID)[C_PT].to_dict())

    # --- Kurs Tengah BI ---
    kt["Kode"] = _norm_kode(kt["Kode"])
    kt["Tgl"] = pd.to_datetime(kt["Fix Date"]).dt.normalize()
    kt = kt[["Kode", "Tgl", "Kurs Tengah", "beli_subkurslokal", "jual_subkurslokal"]].copy()
    kt = kt.rename(columns={"beli_subkurslokal": "Beli BI", "jual_subkurslokal": "Jual BI"})
    kt = kt.sort_values("Tgl")

    # --- Kurs Jisdor (USD) ---
    kj["Tgl"] = pd.to_datetime(kj["Tanggal"]).dt.normalize()
    kj = kj[["Tgl", "Kurs Jisdor USD"]].sort_values("Tgl")

    return {"combine": cb, "tengah": kt, "jisdor": kj, "nama_map": nama_map}


@st.cache_data(show_spinner=False)
def load_data(file_bytes: bytes) -> dict:
    return _load_data_raw(file_bytes)


# ----------------------------------------------------------------------------
# 2. Helper perhitungan (murni, tanpa Streamlit)
# ----------------------------------------------------------------------------
def robust_mean(s, acuan=None) -> float:
    """Rata-rata kurs robust (replika filter sheet Summary).

    Bila `acuan` (acuan BI) diberikan → hanya nilai dalam **acuan × [0,5 .. 2]**
    yang dipakai (membuang typo/orde miliar relatif terhadap acuan BI). Ini perilaku
    yang dipakai sheet Summary. Tanpa `acuan` → fallback: buang <= 0 dan outlier di
    luar median × [0,1 .. 10]."""
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    s = s[s > 0]
    if s.empty:
        return np.nan
    if acuan is not None and acuan > 0:
        s = s[(s >= 0.5 * acuan) & (s <= 2.0 * acuan)]
        return float(s.mean()) if len(s) else np.nan
    med = s.median()
    if med > 0:
        s = s[(s >= med / 10) & (s <= med * 10)]
    return float(s.mean()) if len(s) else np.nan


def daftar_tanggal(cb: pd.DataFrame) -> list:
    return sorted(cb["Tgl"].dropna().unique())


def daftar_pt(cb: pd.DataFrame) -> list:
    return sorted(cb[C_ID].dropna().unique().tolist())


def daftar_valuta(cb: pd.DataFrame) -> list:
    return sorted(cb[C_VAL].dropna().unique().tolist())


def acuan_bi(data: dict, valuta: str, tgl: pd.Timestamp, gran: str = "Harian") -> Optional[float]:
    """Acuan BI ber-forward-fill: nilai pada hari kerja terakhir <= tgl.
    USD -> Jisdor; valuta lain -> Kurs Tengah BI. None bila tak tersedia.
    Untuk periode (gran != Harian), acuan diambil pada ujung periode."""
    tgl = periode_akhir(tgl, gran) if gran != "Harian" else pd.Timestamp(tgl).normalize()
    if valuta == "USD":
        ref = data["jisdor"]
        sub = ref[ref["Tgl"] <= tgl]
        if sub.empty:
            return None
        return float(sub.iloc[-1]["Kurs Jisdor USD"])
    ref = data["tengah"]
    sub = ref[(ref["Kode"] == valuta) & (ref["Tgl"] <= tgl)]
    if sub.empty:
        return None
    return float(sub.iloc[-1]["Kurs Tengah"])


def acuan_bi_avg(data: dict, valuta: str, tgl, gran: str = "Harian") -> Optional[float]:
    """Acuan BI untuk VISUAL tren. Harian → nilai 1 hari (ffill, = acuan_bi).
    Periode agregat (Mingguan/Bulanan/Tahunan) → RATA-RATA nilai acuan BI
    (Jisdor untuk USD / Kurs Tengah untuk lainnya) yang jatuh dalam periode,
    agar setara dengan kurs KUPVA yang juga dirata-rata. Bila tak ada nilai BI
    dalam periode → fallback ke acuan_bi (ffill ujung periode)."""
    if gran == "Harian":
        return acuan_bi(data, valuta, tgl, "Harian")
    lo, hi = periode_range(tgl, gran)
    if valuta == "USD":
        ref = data["jisdor"]
        sub = ref[(ref["Tgl"] >= lo) & (ref["Tgl"] <= hi)]
        if not sub.empty:
            return float(sub["Kurs Jisdor USD"].mean())
    else:
        ref = data["tengah"]
        sub = ref[(ref["Kode"] == valuta) & (ref["Tgl"] >= lo) & (ref["Tgl"] <= hi)]
        if not sub.empty:
            return float(sub["Kurs Tengah"].mean())
    return acuan_bi(data, valuta, tgl, gran)


def punya_acuan(data: dict, valuta: str) -> bool:
    if valuta == "USD":
        return not data["jisdor"].empty
    return (data["tengah"]["Kode"] == valuta).any()


# ----------------------------------------------------------------------------
# Periode (granularitas pemantauan): Harian / Mingguan / Bulanan / Tahunan
# ----------------------------------------------------------------------------
GRANULARITAS = ["Harian", "Mingguan", "Bulanan", "Tahunan"]
_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def periode_range(tgl, gran: str = "Harian"):
    """(awal, akhir) inklusif periode yang memuat tgl, sesuai granularitas."""
    t = pd.Timestamp(tgl).normalize()
    if gran == "Mingguan":          # Senin–Minggu
        lo = t - pd.Timedelta(days=int(t.weekday()))
        hi = lo + pd.Timedelta(days=6)
    elif gran == "Bulanan":
        lo = t.replace(day=1)
        hi = lo + pd.offsets.MonthEnd(0)
    elif gran == "Tahunan":
        lo = t.replace(month=1, day=1)
        hi = t.replace(month=12, day=31)
    else:                           # Harian
        lo = hi = t
    return pd.Timestamp(lo).normalize(), pd.Timestamp(hi).normalize()


def periode_akhir(tgl, gran: str = "Harian") -> pd.Timestamp:
    """Tanggal ujung periode — dipakai sebagai tanggal acuan BI efektif."""
    return periode_range(tgl, gran)[1]


def fmt_periode(tgl, gran: str = "Harian") -> str:
    """Label periode yang ramah baca (mis. 'Bulanan' → 'Jun 2024')."""
    t = pd.Timestamp(tgl)
    if gran == "Mingguan":
        lo, hi = periode_range(t, gran)
        return f"Minggu {int(t.isocalendar().week)} · {fmt_tgl(lo)}–{fmt_tgl(hi)}"
    if gran == "Bulanan":
        return f"{_BULAN[t.month - 1]} {t.year}"
    if gran == "Tahunan":
        return f"Tahun {t.year}"
    return fmt_tgl(t)


def daftar_periode(cb: pd.DataFrame, gran: str = "Harian") -> list:
    """Tanggal-wakil (awal periode) tiap periode yang ada pada data, terurut."""
    if gran == "Harian":
        return daftar_tanggal(cb)
    awal = {periode_range(t, gran)[0] for t in daftar_tanggal(cb)}
    return sorted(awal)


def filter_cb(cb, tgl=None, valutas=None, pts=None, gran: str = "Harian") -> pd.DataFrame:
    """Saring Combine. Bila gran != Harian, `tgl` mewakili periode dan disaring
    sebagai rentang [awal, akhir] periode tersebut (agregasi multi-hari)."""
    m = pd.Series(True, index=cb.index)
    if tgl is not None:
        if gran == "Harian":
            m &= cb["Tgl"] == pd.Timestamp(tgl).normalize()
        else:
            lo, hi = periode_range(tgl, gran)
            m &= (cb["Tgl"] >= lo) & (cb["Tgl"] <= hi)
    if valutas is not None:
        m &= cb[C_VAL].isin(list(valutas))
    if pts is not None:
        m &= cb[C_ID].isin(list(pts))
    return cb[m]


def volume_total(cb, tgl, valutas=None, pts=None, gran: str = "Harian") -> float:
    """Total volume (Jual + Beli) dalam Rupiah pada periode."""
    sub = filter_cb(cb, tgl=tgl, valutas=valutas, pts=pts, gran=gran)
    return float(sub[C_JUAL_RP].sum() + sub[C_BELI_RP].sum())


def volume_jual_beli(cb, tgl, valutas=None, pts=None, gran: str = "Harian") -> tuple:
    sub = filter_cb(cb, tgl=tgl, valutas=valutas, pts=pts, gran=gran)
    return float(sub[C_JUAL_RP].sum()), float(sub[C_BELI_RP].sum())


def growth(h: float, pembanding: float) -> float:
    """Pertumbuhan day-to-day sebagai rasio. NaN bila basis pembanding = 0."""
    if pembanding is None or pembanding == 0:
        return np.nan
    return (h - pembanding) / pembanding


def kurs_rata2(cb, tgl, valuta, pts=None, gran: str = "Harian", acuan=None) -> dict:
    """Rata-rata robust Kurs Jual/Tengah/Beli KUPVA untuk satu valuta & periode.
    Bila `acuan` (acuan BI pada tgl tsb) diberikan, penyaringan robust memakai
    acuan × [0,5 .. 2] sesuai sheet Summary."""
    sub = filter_cb(cb, tgl=tgl, valutas=[valuta], pts=pts, gran=gran)
    return {
        "jual": robust_mean(sub[C_KJUAL], acuan),
        "tengah": robust_mean(sub[C_KTENGAH], acuan),
        "beli": robust_mean(sub[C_KBELI], acuan),
    }


def status_kurs(rasio, ambang=AMBANG_RASIO_DEFAULT) -> str:
    """Status 2-tingkat sesuai Summary: Normal (<ambang) / Waspada (>=ambang).
    Rasio >100% bersifat 'perhatian pengawasan' (lihat perhatian_kurs), bukan label tersendiri."""
    if rasio is None or (isinstance(rasio, float) and np.isnan(rasio)) or rasio == 0:
        return "Tanpa data"
    if rasio >= ambang:
        return "Waspada"
    return "Normal"


def perhatian_kurs(rasio) -> bool:
    """True bila rasio > 100% (di atas acuan BI) namun belum mencapai ambang Waspada."""
    return rasio is not None and rasio == rasio and 1.0 < rasio < AMBANG_RASIO_DEFAULT


def hitung_rasio(kurs, acuan, lo=0.5, hi=2.0):
    """Rasio kurs/acuan, dengan guard kualitas data: bila kurs di luar [acuan*lo, acuan*hi]
    (= acuan × [0,5 .. 2], konsisten filter robust sheet Summary), kembalikan NaN agar
    tidak terbaca Waspada palsu. Deviasi wajar (5-20%) tetap lolos."""
    if acuan is None or acuan == 0 or kurs is None:
        return np.nan
    if isinstance(kurs, float) and np.isnan(kurs):
        return np.nan
    if kurs <= 0:
        return np.nan
    if not (acuan * lo <= kurs <= acuan * hi):
        return np.nan
    return kurs / acuan


def status_volume(g, ambang=AMBANG_DTD_DEFAULT) -> str:
    if g is None or (isinstance(g, float) and np.isnan(g)):
        return "Tanpa data"
    if abs(g) >= ambang:
        return "Waspada"
    return "Normal"


def is_weekend(tgl) -> bool:
    return pd.Timestamp(tgl).weekday() >= 5


# ----------------------------------------------------------------------------
# 3. Tabel turunan untuk halaman
# ----------------------------------------------------------------------------
def tabel_rasio_kurs(data, valuta, tgl_h, tgl_p, tgl_awal, pts, ambang, gran="Harian") -> pd.DataFrame:
    """§1 - rasio Kurs Jual/Tengah/Beli vs acuan BI pada periode cek."""
    cb = data["combine"]
    acu = acuan_bi(data, valuta, tgl_h, gran)
    acu_awal = acuan_bi(data, valuta, tgl_awal, gran)
    acu_p = acuan_bi(data, valuta, tgl_p, gran)
    rows = []
    for label, key in (("Kurs Jual", "jual"), ("Kurs Tengah", "tengah"), ("Kurs Beli", "beli")):
        k_awal = kurs_rata2(cb, tgl_awal, valuta, pts, gran, acuan=acu_awal)[key]
        k_p = kurs_rata2(cb, tgl_p, valuta, pts, gran, acuan=acu_p)[key]
        k_h = kurs_rata2(cb, tgl_h, valuta, pts, gran, acuan=acu)[key]
        rasio = hitung_rasio(k_h, acu)
        rows.append({
            "Komponen": label, "Awal": k_awal, "Pembanding": k_p, "Tanggal cek": k_h,
            "Rasio vs BI": rasio, "Status": status_kurs(rasio, ambang),
            "Perhatian": perhatian_kurs(rasio),
        })
    df = pd.DataFrame(rows)
    df.attrs["acuan"] = acu
    return df


def tren_kurs(data, valuta, tgl_h, pts, gran="Harian") -> pd.DataFrame:
    """Tren Kurs Jual/Tengah/Beli (rata2) + Acuan BI per periode hingga periode cek."""
    cb = data["combine"]
    if gran == "Harian":
        titik = [t for t in daftar_tanggal(cb) if pd.Timestamp(t) <= pd.Timestamp(tgl_h)]
    else:
        hi = periode_akhir(tgl_h, gran)
        titik = [t for t in daftar_periode(cb, gran) if periode_akhir(t, gran) <= hi]
    rows = []
    for t in titik:
        acu_t = acuan_bi_avg(data, valuta, t, gran)   # rata-rata per periode utk visual
        kr = kurs_rata2(cb, t, valuta, pts, gran, acuan=acu_t)
        rows.append({
            "Tanggal": pd.Timestamp(t), "Kurs Jual": kr["jual"],
            "Kurs Tengah": kr["tengah"], "Kurs Beli": kr["beli"],
            "Acuan BI": acu_t,
        })
    return pd.DataFrame(rows)


def tabel_volume(data, valutas, tgl_h, tgl_p, tgl_awal, pts, ambang, gran="Harian") -> pd.DataFrame:
    """§2 - volume Jual & Beli (gabungan valuta terpilih) + growth periode-ke-periode."""
    cb = data["combine"]
    rows = []
    for label, col in (("Volume Jual (Rp)", C_JUAL_RP), ("Volume Beli (Rp)", C_BELI_RP)):
        v_awal = filter_cb(cb, tgl=tgl_awal, valutas=valutas, pts=pts, gran=gran)[col].sum()
        v_p = filter_cb(cb, tgl=tgl_p, valutas=valutas, pts=pts, gran=gran)[col].sum()
        v_h = filter_cb(cb, tgl=tgl_h, valutas=valutas, pts=pts, gran=gran)[col].sum()
        g = growth(v_h, v_p)
        rows.append({
            "Volume": label, "Awal": float(v_awal), "Pembanding": float(v_p),
            "Tanggal cek": float(v_h), "Growth (dtd)": g, "Status": status_volume(g, ambang),
        })
    return pd.DataFrame(rows)


def tren_volume(data, valutas, tgl_h, pts, gran="Harian") -> pd.DataFrame:
    cb = data["combine"]
    if gran == "Harian":
        titik = [t for t in daftar_tanggal(cb) if pd.Timestamp(t) <= pd.Timestamp(tgl_h)]
    else:
        hi = periode_akhir(tgl_h, gran)
        titik = [t for t in daftar_periode(cb, gran) if periode_akhir(t, gran) <= hi]
    rows = []
    for t in titik:
        j, b = volume_jual_beli(cb, t, valutas, pts, gran)
        rows.append({"Tanggal": pd.Timestamp(t), "Jual": j, "Beli": b})
    return pd.DataFrame(rows)


def matriks_per_kupva(data, valuta_fokus, valutas, tgl_h, tgl_p, pts, ambang_r, ambang_v, gran="Harian") -> pd.DataFrame:
    """Status per-KUPVA: rasio kurs (valuta fokus) + growth volume (gabungan valuta terpilih)."""
    cb = data["combine"]
    acu = acuan_bi(data, valuta_fokus, tgl_h, gran)
    rows = []
    for pid in daftar_pt(cb):
        nama = data["nama_map"].get(pid, pid)
        ada_h = not filter_cb(cb, tgl=tgl_h, pts=[pid], gran=gran).empty
        kr = kurs_rata2(cb, tgl_h, valuta_fokus, [pid], gran, acuan=acu)["tengah"]
        rasio = hitung_rasio(kr, acu)
        jh, bh = volume_jual_beli(cb, tgl_h, valutas, [pid], gran)
        jp, bp = volume_jual_beli(cb, tgl_p, valutas, [pid], gran)
        gj, gb = growth(jh, jp), growth(bh, bp)
        s_vol = "Waspada" if ("Waspada" in (status_volume(gj, ambang_v), status_volume(gb, ambang_v))) else \
                ("Normal" if (not np.isnan(gj) or not np.isnan(gb)) and (jh > 0 or bh > 0) else "-")
        rows.append({
            "ID": pid, "KUPVA BB": nama, "Lapor H": ada_h,
            "Kurs Tengah (H)": kr, "Rasio vs BI": rasio,
            "Status Kurs": status_kurs(rasio, ambang_r) if rasio == rasio and kr > 0 else "-",
            "Vol Jual (H)": jh, "Growth Jual": gj,
            "Vol Beli (H)": bh, "Growth Beli": gb, "Status Volume": s_vol,
        })
    return pd.DataFrame(rows)


def tabel_absensi(data, tgl_h, pts, gran="Harian") -> pd.DataFrame:
    """§3 - absensi & kelengkapan. Proxy ketepatan = ketersediaan baris transaksi di periode."""
    cb = data["combine"]
    rows = []
    for pid in daftar_pt(cb):
        nama = data["nama_map"].get(pid, pid)
        sub = filter_cb(cb, tgl=tgl_h, pts=[pid], gran=gran)
        ada = not sub.empty
        vol = float(sub[C_JUAL_RP].sum() + sub[C_BELI_RP].sum())
        dalam_pilihan = pid in set(pts)
        rows.append({
            "ID": pid, "KUPVA BB": nama, "Dipilih": dalam_pilihan,
            "Lapor H": ada, "Jml baris": int(len(sub)), "Volume H (Rp)": vol,
            "Status": "Lengkap" if ada else "Belum lapor",
        })
    return pd.DataFrame(rows)


def valuta_tanpa_acuan(data, tgl_h, pts=None, gran="Harian") -> pd.DataFrame:
    """Valuta yang diperdagangkan namun tidak punya acuan BI (Kurs Tengah/Jisdor)."""
    cb = data["combine"]
    sub = filter_cb(cb, tgl=tgl_h, pts=pts, gran=gran)
    rows = []
    for val in sorted(sub[C_VAL].dropna().unique()):
        if punya_acuan(data, val):
            continue
        v = sub[sub[C_VAL] == val]
        rows.append({
            "Valuta": val, "Negara/Konteks": VALUTA_SENSITIF.get(val, "—"),
            "Sensitif": val in VALUTA_SENSITIF,
            "Volume H (Rp)": float(v[C_JUAL_RP].sum() + v[C_BELI_RP].sum()),
            "Jml KUPVA": int(v[C_ID].nunique()), "Jml transaksi": int(len(v)),
        })
    return pd.DataFrame(rows).sort_values("Volume H (Rp)", ascending=False) if rows else pd.DataFrame()


# ----------------------------------------------------------------------------
# 4. Formatter tampilan (gaya Indonesia)
# ----------------------------------------------------------------------------
def rupiah(x, ringkas=True) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    x = float(x)
    if ringkas:
        a = abs(x)
        if a >= 1e12:
            return f"Rp {x/1e12:,.2f} T".replace(",", "#").replace(".", ",").replace("#", ".")
        if a >= 1e9:
            return f"Rp {x/1e9:,.2f} M".replace(",", "#").replace(".", ",").replace("#", ".")
        if a >= 1e6:
            return f"Rp {x/1e6:,.2f} Jt".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("Rp " + f"{x:,.0f}").replace(",", ".")


def persen(x, desimal=2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{x*100:,.{desimal}f}%".replace(",", "#").replace(".", ",").replace("#", ".")


def angka(x, desimal=2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{x:,.{desimal}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def fmt_tgl(t) -> str:
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    t = pd.Timestamp(t)
    return f"{t.day} {bulan[t.month-1]} {t.year}"


# ----------------------------------------------------------------------------
# 5. Bootstrap sidebar (dipanggil di setiap halaman)
# ----------------------------------------------------------------------------
@dataclass
class Konteks:
    data: dict
    tgl_h: pd.Timestamp
    tgl_p: pd.Timestamp
    tgl_awal: pd.Timestamp
    valutas: list
    pts: list
    ambang_rasio: float
    ambang_dtd: float
    valuta_fokus: str = "USD"
    nama_map: dict = field(default_factory=dict)
    granularitas: str = "Harian"

    @property
    def lbl_h(self) -> str:
        """Label periode cek (mis. 'Jun 2024' untuk Bulanan)."""
        return fmt_periode(self.tgl_h, self.granularitas)

    @property
    def lbl_p(self) -> str:
        return fmt_periode(self.tgl_p, self.granularitas)


def ada_data() -> bool:
    """True bila workbook sudah diunggah (tersimpan di session_state)."""
    return "raw_bytes" in st.session_state


def get_data() -> Optional[dict]:
    """Muat data dari session_state (None bila belum ada / gagal)."""
    if "raw_bytes" not in st.session_state:
        return None
    try:
        return load_data(st.session_state["raw_bytes"])
    except Exception:  # noqa
        return None


def bootstrap(judul: str, icon: str = "📊", subtitle: str = "") -> Optional[Konteks]:
    """Render header halaman + FILTER BAR HORIZONTAL di atas (gaya Power BI),
    lalu kembalikan Konteks. Data diunggah di halaman 'Data' (bukan sidebar).
    Bila belum ada data → tampilkan ajakan + st.stop()."""
    from core.ui_helpers import page_header, no_data_card

    page_header(icon, judul, subtitle)

    if "raw_bytes" not in st.session_state:
        no_data_card()
        st.stop()

    try:
        data = load_data(st.session_state["raw_bytes"])
    except Exception as e:  # noqa
        st.error(f"Gagal membaca workbook: {e}")
        st.stop()

    cb = data["combine"]
    pts_all = daftar_pt(cb)
    vals_all = daftar_valuta(cb)

    # ---- Filter bar horizontal (padat) ----
    fb = st.columns([1.0, 1.25, 1.25, 1.5, 1.0, 0.85])

    gran = fb[0].selectbox("🗓️ Periode", options=GRANULARITAS, index=0, key="gran")

    # Opsi tanggal/periode bergantung granularitas. Kunci di-suffix gran agar
    # nilai tersimpan selalu valid saat granularitas berganti.
    opsi = daftar_periode(cb, gran)
    fmt = (lambda t: fmt_tgl(t)) if gran == "Harian" else (lambda t: fmt_periode(t, gran))
    tgl_awal = opsi[0]

    tgl_h = fb[1].selectbox("📅 Periode cek (H)", options=opsi, index=len(opsi) - 1,
                            format_func=fmt, key=f"tgl_h_{gran}")
    opsi_p = [t for t in opsi if pd.Timestamp(t) < pd.Timestamp(tgl_h)] or opsi
    tgl_p = fb[2].selectbox("↩️ Pembanding", options=opsi_p, index=len(opsi_p) - 1,
                            format_func=fmt, key=f"tgl_p_{gran}")

    valutas = fb[3].multiselect("💱 Valuta dipantau", options=vals_all,
                                default=["USD"] if "USD" in vals_all else vals_all[:1],
                                key="valutas")
    if not valutas:
        valutas = ["USD"] if "USD" in vals_all else vals_all[:1]
    valuta_fokus = fb[4].selectbox("🎯 Valuta fokus", options=valutas, index=0, key="valuta_fokus")

    with fb[5].popover("⚙️ Lainnya", use_container_width=True):
        st.caption(f"{len(cb):,} baris · {len(pts_all)} KUPVA · {len(vals_all)} valuta".replace(",", "."))
        semua_pt = st.checkbox("Pilih semua KUPVA BB", value=True, key="semua_pt")
        if semua_pt:
            pts = pts_all
        else:
            pts = st.multiselect("KUPVA BB", options=pts_all, default=pts_all,
                                 format_func=lambda p: data["nama_map"].get(p, p),
                                 key="pts") or pts_all
        st.markdown("**Ambang status**")
        ambang_rasio = st.slider("Waspada rasio kurs (≥)", 1.00, 1.20,
                                 AMBANG_RASIO_DEFAULT, 0.01, key="amb_r")
        ambang_dtd = st.slider("Waspada growth volume (≥)", 0.05, 0.50,
                               AMBANG_DTD_DEFAULT, 0.01, format="%.2f", key="amb_v")

    st.caption(
        f"Periode **{gran}** · cek {fmt_periode(tgl_h, gran)} · pembanding "
        f"{fmt_periode(tgl_p, gran)} · {len(pts)}/{len(pts_all)} KUPVA · "
        f"valuta {', '.join(valutas)}"
    )
    if gran == "Harian" and is_weekend(tgl_p):
        st.warning(
            f"Pembanding ({fmt_tgl(tgl_p)}) jatuh pada akhir pekan — basis berpotensi "
            "rendah; baca persentase growth dtd dengan hati-hati.",
            icon="⚠️",
        )

    return Konteks(
        data=data, tgl_h=pd.Timestamp(tgl_h), tgl_p=pd.Timestamp(tgl_p),
        tgl_awal=pd.Timestamp(tgl_awal), valutas=valutas, pts=pts,
        ambang_rasio=ambang_rasio, ambang_dtd=ambang_dtd,
        valuta_fokus=valuta_fokus, nama_map=data["nama_map"], granularitas=gran,
    )


def chip(text: str, status: str) -> str:
    warna = STATUS_WARNA.get(status, "#888780")
    return (f'<span class="chip" style="background:{warna}22;color:{warna};">{text}</span>')
