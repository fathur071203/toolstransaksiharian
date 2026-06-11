"""
SAKSI — Penyusun Laporan Word (.docx)
=====================================
Membentuk "Laporan Monitoring Harian Transaksi KUPVA BB" mengikuti template
KPwDN Bank Indonesia, lengkap dengan narasi + data + seluruh grafik:

Header  : banner BI + tanggal cek, rentang tren, valuta dianalisis, jumlah KUPVA.
Seksi 1 : Analisis Monitoring Transaksi – KURS (a–d).
Seksi 2 : Analisis Monitoring Transaksi – JUMLAH TRANSAKSI (a–c + pendalaman).
Seksi 3 : Objek Monitoring & Absensi (a–c + catatan metodologi).
Seksi 4 : Supervisory Action (a–b).
Grafik  : §1 tren kurs (jual/tengah/beli) + tren kurs tengah multi-valuta + rasio
          per valuta; §2 tren jumlah transaksi (jual & beli).
Seluruhnya sadar-periode (granularitas pada Konteks).
"""
from __future__ import annotations

from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

import saksi_engine as E

_BIRU_TUA = "002855"
_BIRU_BAR = "1F4E79"
_EMAS = "C8A951"
_BIRU_TEKS = RGBColor(0x1F, 0x4E, 0x79)
_PUTIH = RGBColor(0xFF, 0xFF, 0xFF)


# ----------------------------------------------------------------------------
# Helper docx
# ----------------------------------------------------------------------------
def _shade(element, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    element.append(shd)


def _no_borders(table) -> None:
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "nil")
        borders.append(e)
    table._tbl.tblPr.append(borders)


def _set_cell_bg(cell, fill: str) -> None:
    _shade(cell._tc.get_or_add_tcPr(), fill)


def _banner(doc, judul: str) -> None:
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _no_borders(t)
    cell = t.rows[0].cells[0]
    _set_cell_bg(cell, _BIRU_TUA)
    p1 = cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p1.add_run(judul)
    r1.bold = True
    r1.font.size = Pt(13)
    r1.font.color.rgb = _PUTIH


def _center(doc, text, *, bold=False, italic=False, size=10, color=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color


def _section_bar(doc, text: str) -> None:
    doc.add_paragraph()
    t = doc.add_table(rows=1, cols=1)
    _no_borders(t)
    cell = t.rows[0].cells[0]
    _set_cell_bg(cell, _BIRU_BAR)
    r = cell.paragraphs[0].add_run(text)
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = _PUTIH


def _bullet(doc, *segments) -> None:
    p = doc.add_paragraph(style="List Bullet")
    for seg in segments:
        teks, bold = (seg, False) if isinstance(seg, str) else (seg[0], seg[1])
        r = p.add_run(teks)
        r.bold = bold
        r.font.size = Pt(10.5)


def _note(doc, text: str) -> None:
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = _BIRU_TEKS


def _label_grafik(doc, text: str) -> None:
    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.italic = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = _BIRU_TEKS


def _add_pic(doc, buf: BytesIO) -> None:
    doc.add_picture(buf, width=Inches(6.4))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def _para(doc, *segments, indent: float = 0.25) -> None:
    """Paragraf indent (bukan bullet) dengan run campuran bold/normal."""
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.left_indent = Inches(indent)
    for seg in segments:
        teks, bold = (seg, False) if isinstance(seg, str) else (seg[0], seg[1])
        r = p.add_run(teks)
        r.bold = bold
        r.font.size = Pt(10.5)


# ---- format angka gaya laporan asesmen ----
def _pct(x) -> str:
    """Persen rasio (selalu positif), mis. '100.7%'."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{x * 100:.1f}%"


def _perub(g) -> str:
    """Arah perubahan tanpa tanda minus: 'naik 16,0%' / 'turun 84,8%' / 'tetap'."""
    if g is None or (isinstance(g, float) and np.isnan(g)):
        return "tidak terdefinisi"
    a = f"{abs(g) * 100:.1f}".replace(".", ",")
    if g > 0:
        return f"naik {a}%"
    if g < 0:
        return f"turun {a}%"
    return "tetap (0,0%)"


def _rp_kata(x) -> str:
    """Rupiah kata penuh, mis. 'Rp12,3 miliar', 'Rp450,0 juta'."""
    x = float(x) if x is not None and x == x else 0.0
    a = abs(x)
    if a >= 1e12:
        return f"Rp{x / 1e12:.1f} triliun".replace(".", ",")
    if a >= 1e9:
        return f"Rp{x / 1e9:.1f} miliar".replace(".", ",")
    if a >= 1e6:
        return f"Rp{x / 1e6:.1f} juta".replace(".", ",")
    return ("Rp" + f"{x:,.0f}").replace(",", ".")


def _stat_kurs(rasio, ambang) -> str:
    """Status kurs 3-tingkat untuk laporan: Normal (≤100%) / Perhatian (>100%) /
    Waspada (≥ ambang, default 105%)."""
    if rasio is None or (isinstance(rasio, float) and np.isnan(rasio)) or rasio == 0:
        return "Tanpa data"
    if rasio >= ambang:
        return "Waspada"
    if rasio > 1.0:
        return "Perhatian"
    return "Normal"


def _stat_vol(g, ambang) -> str:
    """Status volume BERARAH (tidak dinormalkan): Waspada bila NAIK ≥ ambang;
    Perhatian bila TURUN ≥ ambang; selain itu Normal."""
    if g is None or (isinstance(g, float) and np.isnan(g)):
        return "Tanpa data"
    if g >= ambang:
        return "Waspada"
    if g <= -ambang:
        return "Perhatian"
    return "Normal"


# ----------------------------------------------------------------------------
# Grafik (matplotlib → PNG)
# ----------------------------------------------------------------------------
def _png(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_kurs(tk: pd.DataFrame, val: str) -> BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    for komp, c in {"Kurs Jual": "#E24B4A", "Kurs Tengah": "#185FA5", "Kurs Beli": "#1D9E75"}.items():
        s = tk[["Tanggal", komp]].replace(0, np.nan).dropna()
        ax.plot(s["Tanggal"], s[komp], marker="o", ms=3, color=c, label=komp, lw=1.6)
    acu = tk[["Tanggal", "Acuan BI"]].dropna()
    ax.plot(acu["Tanggal"], acu["Acuan BI"], "--", color="#888780", label="Acuan BI", lw=1.6)
    ax.set_title(f"Tren kurs {val} (jual/tengah/beli, rata-rata KUPVA) vs acuan BI", fontsize=10)
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8)
    fig.autofmt_xdate(rotation=30)
    return _png(fig)


def _chart_kurs_multi(data, ctx) -> BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    cmap = plt.cm.tab10
    for i, v in enumerate(ctx.valutas):
        tk = E.tren_kurs(data, v, ctx.tgl_h, ctx.pts, gran=ctx.granularitas)
        s = tk[["Tanggal", "Kurs Tengah"]].replace(0, np.nan).dropna()
        c = cmap(i % 10)
        ax.plot(s["Tanggal"], s["Kurs Tengah"], marker="o", ms=3, color=c, lw=1.5,
                label=f"{v} · KUPVA")
        acu = tk[["Tanggal", "Acuan BI"]].dropna()
        if not acu.empty:
            ax.plot(acu["Tanggal"], acu["Acuan BI"], "--", color=c, lw=1.1, label=f"{v} · BI")
    ax.set_title("Tren kurs tengah per valuta (KUPVA) vs acuan BI", fontsize=10)
    ax.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8)
    fig.autofmt_xdate(rotation=30)
    return _png(fig)


def _chart_rasio(data, ctx) -> BytesIO:
    cb = data["combine"]
    rows = []
    for v in ctx.valutas:
        a = E.acuan_bi(data, v, ctx.tgl_h, gran=ctx.granularitas)
        kr = E.kurs_rata2(cb, ctx.tgl_h, v, ctx.pts, gran=ctx.granularitas, acuan=a)["tengah"]
        r = E.hitung_rasio(kr, a)
        if r == r:
            rows.append((v, r))
    fig, ax = plt.subplots(figsize=(7.2, 2.6 + 0.25 * len(rows)))
    if rows:
        vs = [x[0] for x in rows]
        rr = [x[1] for x in rows]
        col = ["#E24B4A" if x >= ctx.ambang_rasio else ("#BA7517" if x > 1.0 else "#1D9E75")
               for x in rr]
        ax.barh(vs, rr, color=col)
        ax.axvline(ctx.ambang_rasio, color="#E24B4A", ls="--", lw=1, label=f"Batas Waspada ({ctx.ambang_rasio:.0%})")
        ax.axvline(1.0, color="#BA7517", ls=":", lw=1, label="100% (acuan BI)")
        for i, x in enumerate(rr):
            ax.text(x, i, f" {E.persen(x)}", va="center", fontsize=7)
        ax.legend(fontsize=7, loc="lower right")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "Tidak ada valuta dengan acuan BI untuk dirasiokan",
                ha="center", va="center", fontsize=9)
    ax.set_title("Rasio kurs tengah KUPVA vs acuan BI per valuta", fontsize=10)
    ax.tick_params(labelsize=8)
    return _png(fig)


def _chart_volume(tv: pd.DataFrame, gran: str) -> BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(len(tv))
    ax.bar(x - 0.2, tv["Jual"], width=0.4, color="#185FA5", label="Volume Jual (Rp)")
    ax.bar(x + 0.2, tv["Beli"], width=0.4, color="#1D9E75", label="Volume Beli (Rp)")
    ax.set_xticks(x)
    ax.set_xticklabels([E.fmt_periode(t, gran) if gran != "Harian" else E.fmt_tgl(t)
                        for t in tv["Tanggal"]], rotation=35, ha="right", fontsize=7)
    ax.set_title(f"Tren jumlah transaksi {gran.lower()} (Jual & Beli, Rp)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="y")
    ax.tick_params(axis="y", labelsize=8)
    return _png(fig)


# ----------------------------------------------------------------------------
# Penyusun utama
# ----------------------------------------------------------------------------
def build_report(ctx, provinsi: str = "DKI Jakarta", penyusun: str = "") -> bytes:
    """Bangun laporan .docx lengkap dari Konteks aktif; kembalikan bytes siap-unduh."""
    g = ctx.granularitas
    data, cb = ctx.data, ctx.data["combine"]
    val = ctx.valuta_fokus
    pts_all = E.daftar_pt(cb)
    semua_pt = len(ctx.pts) >= len(pts_all)

    # ---- hitung data ----
    absn = E.tabel_absensi(data, ctx.tgl_h, ctx.pts, gran=g)
    absn = absn[absn["ID"].isin(ctx.pts)]
    total = len(absn)
    n_lapor = int((absn["Status"] == "Lengkap").sum())
    belum = absn[absn["Status"] == "Belum lapor"]["KUPVA BB"].tolist()

    mtx = E.matriks_per_kupva(data, val, ctx.valutas, ctx.tgl_h, ctx.tgl_p,
                              ctx.pts, ctx.ambang_rasio, ctx.ambang_dtd, gran=g)
    mtx = mtx[mtx["ID"].isin(ctx.pts)]
    wasp_kurs = mtx[mtx["Status Kurs"] == "Waspada"]["KUPVA BB"].tolist()
    wasp_vol = mtx[mtx["Status Volume"] == "Waspada"]["KUPVA BB"].tolist()

    tr = E.tabel_rasio_kurs(data, val, ctx.tgl_h, ctx.tgl_p, ctx.tgl_awal,
                            ctx.pts, ctx.ambang_rasio, gran=g)
    rj = tr[tr["Komponen"] == "Kurs Jual"].iloc[0]
    rt = tr[tr["Komponen"] == "Kurs Tengah"].iloc[0]
    rb = tr[tr["Komponen"] == "Kurs Beli"].iloc[0]

    tb = E.tabel_volume(data, ctx.valutas, ctx.tgl_h, ctx.tgl_p, ctx.tgl_awal,
                        ctx.pts, ctx.ambang_dtd, gran=g)
    vj, vb = tb.iloc[0], tb.iloc[1]

    tk = E.tren_kurs(data, val, ctx.tgl_h, ctx.pts, gran=g)
    tv = E.tren_volume(data, ctx.valutas, ctx.tgl_h, ctx.pts, gran=g)
    tv = tv[tv["Tanggal"] >= pd.Timestamp(ctx.tgl_awal)]

    akhir_pekan = g == "Harian" and E.is_weekend(ctx.tgl_p)
    pt_lbl = f"Seluruh {total} KUPVA BB" if semua_pt else f"{total} KUPVA BB terpilih"
    n_tanggal = sum(1 for t in E.daftar_tanggal(cb)
                    if pd.Timestamp(ctx.tgl_awal) <= pd.Timestamp(t) <= pd.Timestamp(ctx.tgl_h))
    tgl_cek_en = pd.Timestamp(ctx.tgl_h).strftime("%d %B %Y")

    # rincian KUPVA BB perhatian (perubahan volume dtd >= ambang)
    # Waspada volume = KENAIKAN dtd >= ambang (tidak dinormalkan / abs).
    ambv = ctx.ambang_dtd
    naik_mask = (mtx["Growth Jual"] >= ambv) | (mtx["Growth Beli"] >= ambv)
    wasp_vol_naik = mtx[naik_mask]["KUPVA BB"].tolist()

    rinci = mtx[mtx["Status Volume"] == "Waspada"]   # perubahan besar (naik/turun) → "perhatian"
    rincian_txt = "; ".join(
        f"{r['KUPVA BB']} (vol jual {_perub(r['Growth Jual'])} setara {_rp_kata(r['Vol Jual (H)'])}; "
        f"vol beli {_perub(r['Growth Beli'])} setara {_rp_kata(r['Vol Beli (H)'])})"
        for _, r in rinci.iterrows()
    )

    # ---- dokumen ----
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(0.5)
        s.bottom_margin = Inches(0.5)
        s.left_margin = Inches(0.7)
        s.right_margin = Inches(0.7)

    _banner(doc, "OBJEK MONITORING DAN ABSENSI LAPORAN")
    _center(doc, f"KPwBI Provinsi {provinsi}", bold=True, size=12, color=RGBColor(0, 0x28, 0x55))
    _center(doc, f"Tanggal cek : {tgl_cek_en}   |   "
                 f"Rentang tren: {E.fmt_tgl(ctx.tgl_awal)} - {E.fmt_tgl(ctx.tgl_h)}   |   "
                 f"{n_tanggal} tanggal dipilih", size=10)
    _center(doc, f"Laporan Monitoring {g} Transaksi KUPVA BB", bold=True, italic=True, size=11)
    _note(doc, f"Valuta dianalisis: {val}   |   PT/KUPVA BB: {pt_lbl}")

    # ====================================================================
    # 1. ANALISIS MONITORING TRANSAKSI – KURS
    # ====================================================================
    _section_bar(doc, f"1.  ANALISIS MONITORING TRANSAKSI {g.upper()} – KURS")
    _bullet(doc, "Grafik tren kurs jual, kurs tengah, dan kurs beli masing-masing jenis valuta "
                 "menggunakan seluruh tanggal data yang tersedia sampai dengan tanggal cek "
                 "(lihat grafik §1 di bawah).")
    _bullet(doc, "Grafik tren rasio perbandingan kurs KUPVA BB terhadap kurs Bank Indonesia per "
                 "jenis valuta menggunakan seluruh tanggal data yang tersedia sampai dengan tanggal cek.")
    _bullet(doc, f"Analisis rasio kurs per jenis valuta. Untuk valuta {val}: ",
            (f"rasio kurs jual {_pct(rj['Rasio vs BI'])} ({_stat_kurs(rj['Rasio vs BI'], ctx.ambang_rasio)}), "
             f"kurs tengah {_pct(rt['Rasio vs BI'])} ({_stat_kurs(rt['Rasio vs BI'], ctx.ambang_rasio)}), dan "
             f"kurs beli {_pct(rb['Rasio vs BI'])} ({_stat_kurs(rb['Rasio vs BI'], ctx.ambang_rasio)})", True),
            " terhadap kurs acuan Bank Indonesia. Adapun kriteria: rasio dikategorikan "
            f"Normal apabila tidak melebihi 100%, Perhatian apabila di atas 100%, dan Waspada "
            f"apabila mencapai {ctx.ambang_rasio:.0%} atau lebih terhadap acuan Bank Indonesia.")
    if rincian_txt:
        _para(doc, f"Rincian KUPVA BB yang menjadi perhatian (perubahan volume dtd "
                   f"mencapai {ctx.ambang_dtd:.0%} atau lebih): ", (rincian_txt + ".", True))
    if wasp_kurs:
        _bullet(doc, f"Terdapat {len(wasp_kurs)} KUPVA BB dengan rasio kurs Kategori Waspada "
                     f"(≥ {ctx.ambang_rasio:.0%}) pada hari pelaporan: ",
                (", ".join(wasp_kurs) + ".", True))
    else:
        _bullet(doc, f"Tidak terdapat KUPVA BB dengan rasio kurs Kategori Waspada "
                     f"(≥ {ctx.ambang_rasio:.0%}) pada hari pelaporan; seluruh objek monitoring "
                     "tergolong Normal. Rasio di atas 100% tetap menjadi perhatian pengawasan, "
                     "namun belum melampaui ambang Waspada.")

    # ====================================================================
    # 2. ANALISIS MONITORING TRANSAKSI – JUMLAH TRANSAKSI
    # ====================================================================
    _section_bar(doc, f"2.  ANALISIS MONITORING TRANSAKSI {g.upper()} – JUMLAH TRANSAKSI")
    _bullet(doc, "Grafik tren jumlah transaksi (jual & beli) menggunakan seluruh tanggal data "
                 "yang tersedia sampai dengan tanggal cek (lihat grafik §2 di bawah).")
    catatan_p = (f" Catatan: tanggal pembanding ({E.fmt_tgl(ctx.tgl_p)}) jatuh pada hari "
                 "non-transaksi (akhir pekan) sehingga basis pembanding dapat rendah dan "
                 "persentase pertumbuhan dtd perlu dibaca secara berhati-hati." if akhir_pekan else "")
    _bullet(doc, "Monitoring jumlah transaksi harian (tanggal cek terhadap tanggal pembanding "
                 f"sebelumnya) untuk {', '.join(ctx.valutas)}: ",
            (f"volume jual {_perub(vj['Growth (dtd)'])} dtd menjadi setara "
             f"{_rp_kata(vj['Tanggal cek'])} ({_stat_vol(vj['Growth (dtd)'], ambv)}) dan volume beli "
             f"{_perub(vb['Growth (dtd)'])} dtd menjadi setara "
             f"{_rp_kata(vb['Tanggal cek'])} ({_stat_vol(vb['Growth (dtd)'], ambv)})", True),
            f". Adapun kriteria: transaksi dikategorikan Waspada apabila volume NAIK mencapai "
            f"{ctx.ambang_dtd:.0%} atau lebih (dtd); Perhatian apabila TURUN mencapai "
            f"{ctx.ambang_dtd:.0%} atau lebih; selain itu Normal." + catatan_p)
    if wasp_vol_naik:
        _bullet(doc, f"Terdapat {len(wasp_vol_naik)} KUPVA BB dengan jumlah transaksi Kategori "
                     f"Waspada (kenaikan dtd {ctx.ambang_dtd:.0%} atau lebih pada sisi jual dan/atau "
                     "beli), yaitu: ",
                (", ".join(wasp_vol_naik) + ".", True))
    else:
        _bullet(doc, f"Tidak terdapat KUPVA BB dengan kenaikan jumlah transaksi mencapai "
                     f"{ctx.ambang_dtd:.0%} atau lebih (Kategori Waspada) pada periode ini.")
    pdln = ("Pendalaman penyebab dilakukan dengan menginformasikan nama KUPVA BB, jenis valuta, "
            "serta kurs yang digunakan.")
    if akhir_pekan:
        pdln += (" Karena tanggal pembanding adalah hari non-transaksi, lonjakan dtd dapat "
                 "dipengaruhi basis pembanding yang rendah.")
    _para(doc, pdln)

    # ====================================================================
    # 3. OBJEK MONITORING & ABSENSI
    # ====================================================================
    _section_bar(doc, "3.  OBJEK MONITORING & ABSENSI")
    _bullet(doc, f"Jumlah KUPVA BB yang dimonitor pada tanggal cek: ",
            (f"{n_lapor} KUPVA BB.", True),
            " Objek monitoring mencerminkan minimum 50% dari total transaksi jual dan beli "
            "KUPVA BB di KPwDN (mayoritas transaksi).")
    if belum:
        _bullet(doc, "Ketepatan waktu penyampaian (H+1 maks. pukul 12.00 waktu setempat): "
                     f"dari {total} KUPVA BB dipantau, {n_lapor} telah menyampaikan data transaksi "
                     f"untuk tanggal cek ({E.fmt_tgl(ctx.tgl_h)}). ",
                (f"Sebanyak {len(belum)} KUPVA BB belum/tidak menyampaikan data: "
                 f"{', '.join(belum)}.", True))
        _bullet(doc, "Kelengkapan penyampaian laporan: KUPVA BB berikut perlu ditindaklanjuti "
                     "karena tidak terdapat catatan transaksi pada hari pelaporan: ",
                (", ".join(belum) + ".", True))
    else:
        _bullet(doc, "Ketepatan waktu penyampaian (H+1 maks. pukul 12.00 waktu setempat): "
                     f"seluruh {total} KUPVA BB terpilih telah menyampaikan data transaksi untuk "
                     f"tanggal cek ({E.fmt_tgl(ctx.tgl_h)}).")
        _bullet(doc, "Kelengkapan penyampaian laporan: seluruh KUPVA BB terpilih lengkap "
                     "(terdapat catatan transaksi pada hari pelaporan).")
    _para(doc, "Adapun kriteria: KUPVA BB dinilai telah menyampaikan apabila terdapat catatan "
               "transaksi pada hari pelaporan; bila tidak terdapat, tergolong belum/tidak "
               "menyampaikan dan menjadi tindak lanjut kelengkapan.", indent=0)
    _note(doc, "Catatan: data sumber tidak memuat cap waktu (timestamp) penyampaian, sehingga "
               "penilaian ketepatan terhadap batas pukul 12.00 dilakukan manual oleh KPwDN; "
               "indikator di atas memakai ketersediaan data transaksi pada hari pelaporan sebagai "
               "proksi penyampaian/kelengkapan.")

    # ====================================================================
    # 4. SUPERVISORY ACTION
    # ====================================================================
    _section_bar(doc, "4.  SUPERVISORY ACTION")
    _bullet(doc, "Berdasarkan analisis di atas, KPwDN memberikan rekomendasi tindakan pengawasan "
                 "kepada KUPVA BB di KPwDN.")
    _bullet(doc, "Apabila transaksi “Kategori Normal”, supervisory action berupa pengawasan offsite "
                 f"melalui pemantauan transaksi {g.lower()} terhadap KUPVA BB selama adanya gejolak "
                 "nilai tukar.")

    # ====================================================================
    # GRAFIK §1 — KURS
    # ====================================================================
    _label_grafik(doc, "Grafik §1 — Tren Kurs & Rasio Kurs (seluruh tanggal data sampai tanggal cek):")
    _add_pic(doc, _chart_kurs(tk, val))
    if len(ctx.valutas) > 1:
        _add_pic(doc, _chart_kurs_multi(data, ctx))
    _add_pic(doc, _chart_rasio(data, ctx))

    # ====================================================================
    # GRAFIK §2 — JUMLAH TRANSAKSI
    # ====================================================================
    _label_grafik(doc, "Grafik §2 — Tren Jumlah Transaksi (Jual & Beli):")
    if not tv.empty:
        _add_pic(doc, _chart_volume(tv, g))

    # ---- footer penyusun ----
    doc.add_paragraph()
    foot = doc.add_paragraph()
    foot.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = foot.add_run(f"Disusun oleh: {penyusun}" if penyusun else "")
    fr.italic = True
    fr.font.size = Pt(9)

    out = BytesIO()
    doc.save(out)
    return out.getvalue()
