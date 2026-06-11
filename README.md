# SAKSI · Monitor Harian Transaksi KUPVA BB

Dashboard pengawasan *offsite* transaksi harian **KUPVA BB** (Kegiatan Usaha Penukaran
Valuta Asing Bukan Bank) — KPwDN/KPwBI Provinsi DKI Jakarta. Dibangun dengan **Streamlit**,
input dari **satu workbook Excel**, lalu seluruh halaman terisi otomatis. Mendukung
pemantauan **Harian / Mingguan / Bulanan / Tahunan** dan **ekspor laporan Word (.docx)**.

---

## 1. Cara menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py          # atau: streamlit run Ringkasan.py (setara)
```

1. **Login** dengan akun bawaan **`admin` / `admin123`** (ter-hash di `data/users.xlsx`; harap ganti).
2. Buka menu **📁 Data** di navbar atas → unggah workbook Excel transaksi.
3. Semua halaman terisi; atur **filter bar di atas tiap halaman** (periode, tanggal, valuta, KUPVA, ambang).

> `app.py` dan `Ringkasan.py` keduanya memuat aplikasi penuh (login + navbar) lewat `core/shell.py`.

---

## 2. Arsitektur & alur besar

```
            ┌──────────────────────────────────────────────────────────────┐
            │ app.py / Ringkasan.py  →  core/shell.py                       │
            │   • st.set_page_config + gerbang LOGIN (render_login)         │
            │   • navbar atas (st.navigation + st.page_link)                │
            │   • routing ke halaman di views/                              │
            └──────────────────────────────────────────────────────────────┘
                                        │
   INPUT                PENGOLAHAN                         OUTPUT (per halaman)
 ┌────────┐   upload   ┌───────────────────┐  Konteks   ┌────────────────────────┐
 │ Excel  │ ─────────► │ saksi_engine.py   │ ─────────► │ views/*.py             │
 │ .xlsx  │  (📁 Data) │ load_data()       │            │ grafik + tabel + narasi│
 │ 3 sheet│            │ + perhitungan     │            │ + ekspor Word          │
 └────────┘            └───────────────────┘            └────────────────────────┘
```

**Prinsip:** semua logika data & rumus terpusat di `saksi_engine.py`. Tiap halaman di `views/`
hanya memanggil fungsi engine lalu menggambar grafik/tabel. Filter bar (`E.bootstrap`) memberi
objek **`Konteks`** (tanggal, periode, valuta, KUPVA, ambang) yang dipakai seluruh perhitungan.

---

## 3. INPUT — Format workbook Excel

Satu file `.xlsx` dengan **3 sheet wajib**:

| Sheet | Isi | Kolom yang dibaca |
|-------|-----|-------------------|
| **`Combine`** | Baris transaksi harian per KUPVA per valuta | `ID PT`, `Nama PT (Lengkap`, `Tanggal`, `Mata Uang`, `Jenis Valuta`, `Saldo Awal/Akhir dalam Valas/Rupiah`, `Volume Pembelian/Penjualan dalam Valas/Rupiah`, `Kurs Beli/Tengah/Jual` |
| **`Kurs Tengah`** | Acuan Kurs Tengah BI (valuta non-USD) | `Kode`, `Fix Date`, `Kurs Tengah`, `beli_subkurslokal`, `jual_subkurslokal` |
| **`Kurs Jisdor`** | Acuan Jisdor (USD) | `Tanggal`, `Kurs Jisdor USD` |

Bila salah satu sheet hilang, `load_data()` melempar error yang menyebut sheet yang kurang.

---

## 4. PENGOLAHAN — `saksi_engine.py`

### 4.1 Pemuatan & normalisasi (`load_data`, cache)
- **Combine:** kode valuta di-`upper().strip()`; `Tanggal → Tgl` (dinormalkan ke tengah malam);
  seluruh kolom numerik di-`to_numeric(...).fillna(0)`; dibangun **`nama_map`** (ID → nama lengkap).
- **Kurs Tengah:** `Kode` dinormalkan; `Fix Date → Tgl`; di-*sort* per tanggal.
- **Kurs Jisdor:** `Tanggal → Tgl`; di-*sort*.
- Hasil di-*cache* (`@st.cache_data`) → upload sekali, dipakai semua halaman.

### 4.2 Konstanta domain
- Ambang default: **rasio kurs Waspada = 1,05** (`AMBANG_RASIO_DEFAULT`), **growth Waspada = 0,15** (`AMBANG_DTD_DEFAULT`).
- Warna status: Normal `#1D9E75`, Perhatian `#BA7517`, Waspada `#E24B4A`, Tanpa data `#888780`.
- `VALUTA_SENSITIF`: peta valuta zona konflik/sanksi (RUB, IQD, TRY, … → negara) untuk halaman Risiko.

### 4.3 Rumus inti (semuanya murni, dapat diuji)

| Fungsi | Rumus / logika |
|--------|----------------|
| `robust_mean(s, acuan)` | Buang nilai ≤ 0; lalu **hanya pakai nilai dalam `acuan BI × [0,5 .. 2]`** (replika filter sheet Summary). Tanpa `acuan` → fallback `median × [0,1 .. 10]`. |
| `acuan_bi(valuta, tgl)` | **USD → Kurs Jisdor**, lainnya **→ Kurs Tengah BI**, secara *forward-fill*: nilai hari kerja terakhir `≤ tgl`. Untuk periode, dipakai **ujung periode**. |
| `kurs_rata2(tgl, valuta, pts, acuan)` | `robust_mean` Kurs Jual / Tengah / Beli KUPVA pada periode, disaring `acuan × [0,5 .. 2]`. |
| `hitung_rasio(kurs, acuan)` | `kurs / acuan`, dengan **guard**: bila `kurs ≤ 0` atau di luar `acuan × [0,5 .. 2]` → `NaN` (mencegah Waspada palsu dari salah input berorde miliar). |
| `status_kurs(rasio, ambang)` | `Tanpa data` bila NaN/0; **`Waspada` bila rasio ≥ ambang (1,05)**; selain itu `Normal`. |
| `perhatian_kurs(rasio)` | `True` bila `1,00 < rasio < 1,05` (di atas acuan BI tapi belum Waspada). |
| `growth(H, P)` | `(H − P) / P`; `NaN` bila basis `P = 0`. |
| `status_volume(g, ambang)` | **`Waspada` bila `|g| ≥ ambang (0,15)`**; selain itu `Normal` (Tanpa data bila NaN). |
| `volume_total / volume_jual_beli` | Penjumlahan `Volume Penjualan/Pembelian dalam Rupiah` sesuai filter. |

### 4.4 Periode pemantauan (Harian / Mingguan / Bulanan / Tahunan)
`filter_cb(..., gran)` menyaring data sebagai **rentang periode** yang memuat tanggal terpilih:

| Periode | Rentang agregasi |
|---------|------------------|
| Harian | satu hari (perilaku semula, 1:1 sheet Summary) |
| Mingguan | Senin–Minggu yang memuat tanggal |
| Bulanan | tanggal 1 – akhir bulan |
| Tahunan | 1 Jan – 31 Des |

Konsekuensi: **volume dijumlahkan** sepanjang periode, **kurs dirata-rata robust** per periode,
**growth dihitung antar-periode** (mis. bulan ini vs bulan lalu), **acuan BI** diambil di ujung periode.
Helper: `periode_range`, `periode_akhir`, `fmt_periode`, `daftar_periode`.

### 4.5 Filter bar & `Konteks` (`bootstrap`)
Filter bar horizontal padat di atas tiap halaman menghasilkan `Konteks`:
`🗓️ Periode · 📅 Periode cek (H) · ↩️ Pembanding · 💱 Valuta dipantau · 🎯 Valuta fokus · ⚙️ Lainnya (KUPVA + ambang)`.
Disimpan di `session_state` → konsisten lintas halaman.

---

## 5. HALAMAN — input → olah → grafik/tabel/perhitungan

Navbar atas dikelompokkan menjadi **4 grup** sesuai alur kerja pengawas:
**BERANDA** (📁 Data · 🛡️ Ringkasan) · **ANALISIS** (💱 Kurs · 📊 Volume) ·
**KEPATUHAN** (🗓️ Absensi · ⚠️ Risiko) · **LAPORAN** (🏦 Profil · 📄 Laporan).

### 📁 Data — `views/0_Data.py`
- **Input:** unggah `.xlsx`.
- **Olah:** simpan ke `session_state`, `load_data()` validasi 3 sheet.
- **Output:** info format + **4 metrik** (baris transaksi, jumlah KUPVA, valuta, tanggal).

### 🛡️ Ringkasan — `views/00_Ringkasan.py` (cockpit)
- **Olah:** `matriks_per_kupva`, `tabel_absensi`, `volume_total`, `valuta_tanpa_acuan`.
- **Output:**
  - **6 KPI:** KUPVA dipantau (n unik lapor / total terpilih), Total volume periode, Waspada kurs, Waspada volume, Belum lapor, Valuta tanpa acuan.
  - **2 grafik donut:** komposisi *Status Kurs* (valuta fokus) & *Status Volume* (Normal/Waspada/Tanpa data).
  - **Tabel matriks per-KUPVA:** Lapor (✓/—), Status kurs (berwarna), Rasio kurs, Growth jual/beli, Status volume.
- **Perhitungan:** status per-KUPVA = `status_kurs(rasio_tengah)` + `status_volume(growth jual|beli)`.

### 💱 Kurs — `views/1_Monitoring_Kurs.py` (§1)
- **Olah:** `tren_kurs`, `kurs_rata2`, `acuan_bi`, `hitung_rasio`, `tabel_rasio_kurs`.
- **Output:**
  - **Grafik garis — Tren kurs** valuta fokus: Kurs Jual/Tengah/Beli (rata-rata KUPVA) + garis **Acuan BI** sepanjang periode.
  - **Grafik bar — Rasio kurs tengah vs BI per valuta** (warna per status; garis batas `1,00` & ambang `1,05`).
  - **Tabel rasio komponen:** Awal / Pembanding / Periode cek + **Rasio vs BI** + Status + Catatan (">100% perhatian").
  - **Narasi otomatis (§1):** rangkuman rasio jual/tengah/beli + simpulan Waspada/Normal.
- **Perhitungan:** `rasio = kurs_rata2(tengah) / acuan_bi`; status per `status_kurs`.

### 📊 Volume — `views/2_Monitoring_Volume.py` (§2)
- **Olah:** `tren_volume`, `tabel_volume`, `matriks_per_kupva`, `volume_jual_beli`.
- **Output:**
  - **Grafik bar berkelompok — Tren volume** Jual & Beli (Rp) per periode.
  - **Tabel growth:** Awal / Pembanding / Periode cek + **Growth (dtd)** + Status (per valuta gabungan).
  - **Tabel KUPVA Waspada volume** (growth jual/beli).
  - Catatan basis pembanding (peringatan bila pembanding akhir pekan) + **narasi otomatis (§2)**.
- **Perhitungan:** `growth = (H − P)/P`; `status_volume(|growth| ≥ 0,15)`.

### 🗓️ Absensi — `views/3_Absensi_Kelengkapan.py` (§3 & §4)
- **Olah:** `tabel_absensi` (proxy lapor = ada baris transaksi pada periode).
- **Output:**
  - **4 metrik:** KUPVA terpilih, Telah lapor, Belum lapor, **Ketepatan (%)** = lapor/total.
  - **Tabel daftar penyampaian** (Lapor, Jml baris, Volume, Status berwarna).
  - **Grafik donut komposisi** Telah/Belum lapor.
  - **Narasi (§3 & §4)** + daftar **Supervisory Action**.

### 🏦 Profil — `views/4_Profil_per_KUPVA.py`
- **Input tambahan:** pilih satu KUPVA.
- **Olah:** `filter_cb` per PT, `kurs_rata2`, `acuan_bi`, `growth`, `tren_kurs` untuk PT itu.
- **Output:**
  - **4 metrik:** Volume jual/beli, Saldo akhir, Valuta aktif.
  - **Tabel rincian per valuta:** Rasio tengah, Vol jual/beli, Growth jual/beli, Status kurs & volume.
  - **Grafik garis tren kurs** valuta fokus untuk PT terpilih.
  - **Narasi per-PT** (Waspada kurs/volume, valuta tanpa acuan).

### ⚠️ Risiko — `views/5_Risiko_Valuta.py`
- **Olah:** `valuta_tanpa_acuan` (valuta diperdagangkan tanpa Kurs Tengah/Jisdor), `filter_cb` valuta sensitif.
- **Output:**
  - **3 metrik:** Valuta tanpa acuan, di antaranya sensitif, Total volume eksotik.
  - **Grafik bar — eksposur volume** per valuta tanpa acuan (merah = sensitif geopolitik).
  - **Tabel tindak lanjut** (valuta, negara/konteks, sensitif, volume, jml KUPVA).
  - **Grafik heatmap — konsentrasi KUPVA × valuta sensitif** + narasi APU-PPT.

### 📄 Laporan — `views/6_Ekspor_Laporan.py`
Tiga *section* (tab): **Word — Laporan Harian** (aktif), **Excel — Per Entitas** & **Excel — Transaksi** (kerangka, segera). Halaman ini **tanpa** filter bar global; kontrol ada di dalam tab. Word **dikunci Harian otomatis**. Lihat §6.

---

## 6. Ekspor Laporan Word — `core/report.py`

Tombol **Susun → Unduh** menghasilkan **"Laporan Monitoring Harian Transaksi KUPVA BB" (.docx)**
sesuai template KPwDN BI (python-docx + grafik matplotlib):

- **Header:** banner BANK INDONESIA · KPwDN Provinsi · Tanggal cek · Rentang tren · Valuta dianalisis · jumlah KUPVA.
- **Seksi 1 — Analisis Kurs** (rasio jual/tengah/beli + status; ">100% perhatian, ≥105% Waspada"; daftar Waspada).
- **Seksi 2 — Jumlah Transaksi** (growth jual/beli + status; daftar nama KUPVA Waspada; pendalaman penyebab).
- **Seksi 3 — Objek Monitoring & Absensi** (jumlah dimonitor; ketepatan H+1 12.00; kelengkapan + catatan metodologi).
- **Seksi 4 — Supervisory Action**.
- **Grafik §1 (Kurs):** tren kurs jual/tengah/beli vs BI · tren kurs tengah **multi-valuta** vs BI · **rasio per valuta**.
- **Grafik §2 (Jumlah Transaksi):** tren volume jual & beli.

Semua angka & daftar dihitung ulang dari engine sesuai cakupan (valuta, KUPVA) dan tanggal harian terpilih.

---

## 7. Autentikasi — `components/auth.py`
- Backend Excel `data/users.xlsx` (dibuat otomatis dengan admin bawaan saat pertama jalan).
- Password **PBKDF2-SHA256** bersalt (`pbkdf2_sha256$iter$salt$hash`) — **tidak pernah plaintext**.
- Fungsi: `login_user`, `register_user`, `get_user_by_username`. Gerbang login di `core/shell.py`.

---

## 8. Struktur file

```
saksi_app/
├── app.py / Ringkasan.py         # entry point (alias) → core/shell.py
├── saksi_engine.py               # ENGINE: load data + seluruh perhitungan + filter bar
├── components/auth.py            # autentikasi PBKDF2 (users.xlsx)
├── core/
│   ├── shell.py                  # launcher: login + navbar + routing
│   ├── ui_helpers.py             # CSS global (palet BI) + form login + helper UI
│   └── report.py                 # penyusun Laporan Word (.docx)
├── data/users.xlsx               # tabel pengguna (auto, tidak di-commit)
├── views/
│   ├── 0_Data.py                 # upload (landing)
│   ├── 00_Ringkasan.py           # cockpit KPI + donut + matriks
│   ├── 1_Monitoring_Kurs.py      # §1 rasio kurs vs BI
│   ├── 2_Monitoring_Volume.py    # §2 growth volume
│   ├── 3_Absensi_Kelengkapan.py  # §3/§4 absensi + supervisory
│   ├── 4_Profil_per_KUPVA.py     # drill-down per KUPVA
│   ├── 5_Risiko_Valuta.py        # eksposur valuta tanpa acuan
│   └── 6_Ekspor_Laporan.py       # ekspor Word/Excel
├── .streamlit/config.toml        # tema palet BI
└── requirements.txt
```

---

## 9. Logika pengawasan (terkunci ke sheet Summary)

| Indikator | Rumus | Ambang default |
|-----------|-------|----------------|
| Rasio kurs | `kurs KUPVA (robust) / acuan BI` | Waspada ≥ 1,05 · perhatian > 100% |
| Growth volume | `(H − pembanding) / pembanding` | Waspada ≥ 15% |
| Acuan kurs | USD → Jisdor; lain → Kurs Tengah (ffill) | tak ada → "tanpa acuan" |
| Absensi | ada baris transaksi pada periode? | tidak → "belum lapor" |

- **Rata-rata kurs robust:** buang ≤ 0 & nilai di luar `acuan BI × [0,5 .. 2]` (sesuai sheet Summary).
- **Acuan BI forward-fill:** hari non-bursa memakai nilai hari kerja terakhir.
- **Guard growth:** basis pembanding 0 → `NaN`, tidak dipakai Waspada.
- Status kurs 2-tingkat (Normal/Waspada) konsisten Summary; rasio > 100% jadi catatan perhatian.

---

*Disusun untuk Tools Kepengawasan — SAKSI, KPwDN/KPwBI Provinsi DKI Jakarta.*
