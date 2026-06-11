"""
SAKSI — Helper UI & styling global
==================================
Satu sumber kebenaran untuk tampilan: palet warna Bank Indonesia, navbar atas,
dan helper reusable (require_auth, page_header, dst).

Palet brand (Bank Indonesia):
    Biru tua  #002855   navbar (gradien), judul
    Biru      #004990   aksen, border, tombol
    Emas      #C8A951   garis bawah navbar, item aktif, logout
    Abu latar #EEF2F7   background aplikasi
    Abu garis #DDE3EE   garis card/tabel
"""
from __future__ import annotations

import streamlit as st

# ----------------------------------------------------------------------------
# CSS global — disuntik sekali per render dari app.py
# ----------------------------------------------------------------------------
GLOBAL_CSS = """
<style>
  :root {
    --bi-biru-tua: #002855;
    --bi-biru:     #004990;
    --bi-emas:     #C8A951;
    --bi-abu:      #EEF2F7;
    --bi-garis:    #DDE3EE;
  }

  /* ---- Layout utama (padat) ---- */
  .block-container {
    max-width: 1640px !important;
    padding: 0.5rem 1.6rem 2rem !important;
  }
  /* Rapatkan jarak antar elemen vertikal */
  div[data-testid="stVerticalBlock"] { gap: 0.6rem !important; }
  hr { margin: 0.5rem 0 !important; }

  /* ---- Sembunyikan SEMUA krom Streamlit termasuk SIDEBAR (gaya Power BI) ---- */
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="stSidebar"],
  [data-testid="stSidebarNav"],
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],
  #MainMenu, footer {
    display: none !important;
  }
  /* Pastikan area utama memakai lebar penuh setelah sidebar hilang */
  .stMain .block-container { margin-left: auto !important; margin-right: auto !important; }

  /* ---- NAVBAR ATAS ----
     Baris st.columns yang DI DALAMNYA ada st.page_link → kita sulap jadi bar biru. */
  div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPageLink"]) {
    background: linear-gradient(90deg, #002855 0%, #004990 100%) !important;
    border-bottom: 3px solid var(--bi-emas) !important;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0, 40, 85, 0.18);
    position: sticky; top: 0; z-index: 999;
    padding: 4px 14px !important;
    margin-bottom: 1.1rem;
    gap: 2px !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
  }

  /* Brand / logo di kolom pertama */
  .nav-logo { display: flex; flex-direction: column; line-height: 1.15; padding: 6px 4px; }
  .nav-title { color: #fff; font-weight: 800; font-size: 1.02rem; letter-spacing: .3px; }
  .nav-status { color: #C8A951; font-size: .72rem; font-weight: 600; }

  /* Label grup navbar (BERANDA / ANALISIS / KEPATUHAN / LAPORAN) */
  .nav-grp {
    color: #C8A951; font-weight: 800; font-size: .6rem; letter-spacing: .6px;
    text-transform: uppercase; text-align: center; line-height: 1.1; padding-top: 2px;
  }
  /* Pemisah antar grup */
  .nav-sep { width: 1px; height: 30px; background: rgba(255,255,255,0.28); margin: 0 auto; }

  /* Tiap link navbar (padat) */
  div[data-testid="stPageLink"] a {
    color: #fff !important;
    font-weight: 600 !important;
    font-size: .9rem !important;
    text-align: center !important;
    justify-content: center !important;
    padding: 8px 4px !important;
    border-radius: 7px !important;
    border-bottom: 3px solid transparent !important;
    transition: background .15s ease, border-color .15s ease;
    white-space: nowrap !important;
  }
  div[data-testid="stPageLink"] a * { color: #fff !important; }
  div[data-testid="stPageLink"] a:hover { background: rgba(255,255,255,0.13) !important; }

  /* Halaman aktif → garis emas */
  div[data-testid="stPageLink"] a[aria-current="page"] {
    border-bottom: 3px solid var(--bi-emas) !important;
    background: rgba(255,255,255,0.14) !important;
  }

  /* Tombol Logout di navbar */
  div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPageLink"]) .stButton button {
    background: var(--bi-emas) !important;
    color: #002855 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 7px !important;
  }
  div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPageLink"]) .stButton button:hover {
    background: #d8bb66 !important;
  }

  /* ---- Kartu judul halaman (page_header) — padat ---- */
  .page-header {
    display: flex; align-items: center; gap: 14px;
    background: #fff; border: 1px solid var(--bi-garis);
    border-left: 5px solid var(--bi-biru);
    border-radius: 10px; padding: 10px 16px; margin-bottom: 0.7rem;
    box-shadow: 0 1px 4px rgba(0,40,85,0.05);
  }
  .page-header .ph-icon { font-size: 1.7rem; line-height: 1; }
  .page-header .ph-title { font-size: 1.25rem; font-weight: 800; color: var(--bi-biru-tua); margin: 0; }
  .page-header .ph-sub { font-size: .82rem; color: #5b6b7d; margin: 1px 0 0; }

  /* ---- Filter bar atas (label kecil & rapat) ---- */
  div[data-testid="stSelectbox"] label,
  div[data-testid="stMultiSelect"] label {
    font-size: .76rem !important; font-weight: 600 !important;
    color: #33475b !important; margin-bottom: 2px !important;
  }
  /* Tombol popover "Lainnya" senada navbar */
  div[data-testid="stPopover"] > div button {
    background: #fff !important; border: 1px solid var(--bi-garis) !important;
    color: var(--bi-biru-tua) !important; font-weight: 600 !important; margin-top: 22px;
  }

  /* ---- Label seksi ---- */
  .section-title {
    text-transform: uppercase; letter-spacing: 1px; font-size: .78rem;
    font-weight: 700; color: var(--bi-biru); border-bottom: 2px solid var(--bi-garis);
    padding-bottom: 5px; margin: 1.3rem 0 .7rem;
  }

  /* ---- Placeholder belum ada data ---- */
  .no-data-card {
    text-align: center; background: #fff; border: 1px dashed var(--bi-garis);
    border-radius: 12px; padding: 42px 24px; margin-top: 1rem; color: #5b6b7d;
  }
  .no-data-card .nd-icon { font-size: 2.4rem; }
  .no-data-card .nd-title { font-size: 1.1rem; font-weight: 700; color: var(--bi-biru-tua); margin: 8px 0 4px; }

  /* ---- Metric cards ---- */
  [data-testid="stMetric"] {
    background: #fff; border: 1px solid var(--bi-garis);
    border-radius: 10px; padding: 12px 16px;
  }
  [data-testid="stMetricValue"] { font-size: 1.45rem; color: var(--bi-biru-tua); }

  h1 { font-size: 1.55rem !important; color: var(--bi-biru-tua); }
  h2 { font-size: 1.2rem !important; color: var(--bi-biru-tua); }

  .chip { display:inline-block; padding:2px 9px; border-radius:7px; font-size:12px; font-weight:500; }
</style>
"""


def inject_css() -> None:
    """Suntik CSS global. Aman dipanggil berulang (idempoten secara visual)."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Login (UI reusable) — dipanggil core/shell.py saat belum terautentikasi.
# Tampilan: kartu putih di tengah, latar pola garis biru, bar emas/biru di atas.
# ----------------------------------------------------------------------------
_LOGIN_CSS = """
<style>
html, body, .stApp {
    background-color: #ffffff !important;
    background-image:
        repeating-linear-gradient(135deg,
            rgba(0, 73, 144, 0.05) 0, rgba(0, 73, 144, 0.05) 1px,
            transparent 1px, transparent 18px),
        repeating-linear-gradient(45deg,
            rgba(0, 40, 85, 0.035) 0, rgba(0, 40, 85, 0.035) 1px,
            transparent 1px, transparent 24px) !important;
    min-height: 100vh !important;
}

/* Kartu utama */
.block-container {
    max-width: 440px !important;
    padding: 34px 32px 26px !important;
    margin: 7vh auto 6vh !important;
    background: #ffffff !important;
    border: 1px solid #dde3ee !important;
    border-radius: 14px !important;
    box-shadow: 0 18px 50px rgba(0, 40, 85, 0.10) !important;
}
.block-container::before {
    content: "";
    display: block; height: 7px; border-radius: 14px 14px 0 0;
    background: linear-gradient(90deg, #002855 0%, #004990 100%);
    margin: -34px -32px 22px;
}

/* Sembunyikan krom Streamlit */
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarNav"], [data-testid="stDecoration"],
[data-testid="stNavigation"], #MainMenu, footer { display: none !important; }

/* Header login */
.login-header { text-align: center; margin-bottom: 18px; }
.login-title {
    font-size: 28px; font-weight: 700; color: #002855; margin-bottom: 6px;
    display: flex; align-items: center; justify-content: center; gap: 8px;
}
.login-subtitle { font-size: 13px; color: #64748b; }
.login-subtitle .accent-gold { color: #C8A951; font-weight: 600; }
h3 { margin: .6rem 0 !important; color: #002855 !important; }

/* Input */
div[data-baseweb="input"] { background: #f8fafc !important; border-radius: 6px !important; }
div[data-baseweb="input"] input {
    border: 2px solid #dde3ee !important; border-radius: 6px !important;
    padding: 10px 12px !important; font-size: 14px !important;
}
div[data-baseweb="input"] input:focus {
    border-color: #004990 !important; box-shadow: 0 0 0 3px rgba(0, 73, 144, 0.1) !important;
}

/* Tombol submit */
button[kind="primary"], button[kind="primaryFormSubmit"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(90deg, #004990 0%, #003366 100%) !important;
    border: none !important; color: #fff !important; font-weight: 700 !important;
    font-size: 14px !important; padding: 10px 20px !important; border-radius: 6px !important;
    width: 100% !important; transition: all 0.2s !important; margin-top: 8px !important;
}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(90deg, #003366 0%, #001f40 100%) !important;
    transform: translateY(-1px) !important; box-shadow: 0 8px 16px rgba(0, 73, 144, 0.25) !important;
}

/* Alert error */
div[data-testid="stAlert"] { border-radius: 8px !important; }

/* Footer */
.login-footer-info { text-align: center; color: #64748b; font-size: 11px; margin-top: 14px; }
</style>
"""


def render_login() -> None:
    """Render halaman login berstyling + tangani submit. Set authenticated lalu rerun."""
    import time

    from components.auth import login_user

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="login-header">'
        '<div class="login-title">🛡️ SAKSI</div>'
        '<div class="login-subtitle">Monitor Harian Transaksi KUPVA BB · '
        '<span class="accent-gold">KPwDN DKI Jakarta</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### Masuk ke Akun Anda")

    with st.form(key="login_form", clear_on_submit=True):
        username = st.text_input("Username", placeholder="Masukkan username Anda",
                                 help="Username untuk login")
        password = st.text_input("Password", type="password",
                                 placeholder="Masukkan password Anda",
                                 help="Password untuk login")
        submitted = st.form_submit_button("🔓 Masuk", type="primary",
                                          use_container_width=True)

        if submitted:
            if username and password:
                with st.spinner("Memverifikasi akun..."):
                    success, message, user_data = login_user(username, password)
                    time.sleep(0.35)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user = user_data
                    st.success(f"✅ {message}")
                    st.balloons()
                    time.sleep(1.2)
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
            else:
                st.error("❌ Username dan password harus diisi")

    st.markdown(
        "<div class='login-footer-info'>"
        "<div>© 2026 Bank Indonesia · Kantor Perwakilan DKI Jakarta</div>"
        "<div>SAKSI — Sistem Analisis Transaksi KUPVA · akun bawaan: admin / admin123</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def require_auth() -> None:
    """Penjaga ringan: hentikan render bila belum login.

    Satu-satunya gerbang login ada di app.py (entry point tunggal). Fungsi ini
    hanya memastikan konten halaman tak terender bila state belum terautentikasi."""
    if not st.session_state.get("authenticated", False):
        st.stop()


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Kartu judul halaman ala dashboard (ikon + judul + subjudul)."""
    sub = f'<p class="ph-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="page-header"><div class="ph-icon">{icon}</div>'
        f'<div><p class="ph-title">{title}</p>{sub}</div></div>',
        unsafe_allow_html=True,
    )


def section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def no_data_card() -> None:
    st.markdown(
        '<div class="no-data-card"><div class="nd-icon">📂</div>'
        '<div class="nd-title">Belum Ada Data</div>'
        '<div>Buka menu <b>📁 Data</b> di navbar atas dan unggah workbook Excel '
        'transaksi harian untuk mengisi seluruh halaman.</div></div>',
        unsafe_allow_html=True,
    )
