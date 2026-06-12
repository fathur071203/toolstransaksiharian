"""
SAKSI — shell aplikasi (launcher).
Berisi SELURUH logika entry point: set_page_config, gerbang login, navbar atas,
dan routing st.navigation. Dipanggil oleh app.py MAUPUN Ringkasan.py supaya
`streamlit run app.py` dan `streamlit run Ringkasan.py` sama-sama bekerja penuh.
"""
import streamlit as st


def main() -> None:
    st.set_page_config(
        page_title="SAKSI · Monitor Harian KUPVA BB",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # 1. State autentikasi
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None

    from core.ui_helpers import inject_css, render_login

    # 2. Gerbang login — belum login → form login lalu stop.
    if not st.session_state.authenticated:
        render_login()
        st.stop()

    # 3. Sudah login → CSS global + navbar + halaman aktif.
    inject_css()

    p_data      = st.Page("views/0_Data.py",                title="📁 Data",      url_path="data", default=True)
    p_ringkasan = st.Page("views/00_Ringkasan.py",          title="🛡️ Ringkasan", url_path="ringkasan")
    p_kurs      = st.Page("views/1_Monitoring_Kurs.py",     title="💱 Kurs",      url_path="kurs")
    p_volume    = st.Page("views/2_Monitoring_Volume.py",   title="📊 Volume",    url_path="volume")
    p_absensi   = st.Page("views/3_Absensi_Kelengkapan.py", title="🗓️ Absensi",   url_path="absensi")
    p_profil    = st.Page("views/4_Profil_per_KUPVA.py",    title="🏦 Profil",    url_path="profil")
    p_risiko    = st.Page("views/5_Risiko_Valuta.py",       title="⚠️ Risiko",    url_path="risiko")
    p_laporan   = st.Page("views/6_Ekspor_Laporan.py",      title="📄 Laporan",   url_path="laporan")
    p_tarikkurs = st.Page("views/7_Tarik_Kurs_BI.py",       title="🌐 Tarik Kurs", url_path="tarik-kurs")

    # 4 grup berurut sesuai alur kerja pengawas
    groups = [
        ("BERANDA",   [p_data, p_ringkasan]),
        ("ANALISIS",  [p_kurs, p_volume]),
        ("KEPATUHAN", [p_absensi, p_risiko]),
        ("LAPORAN",   [p_profil, p_laporan, p_tarikkurs]),
    ]
    pages = [pg for _, gp in groups for pg in gp]
    nav_router = st.navigation(pages, position="hidden")

    # ---- Navbar atas: [brand] + grup(label + link...) dipisah separator + [logout] ----
    status = "● Data termuat" if st.session_state.get("raw_bytes") else "○ Belum ada data"

    specs = [1.7]
    plan = []  # (jenis, payload)
    for gi, (label, gp) in enumerate(groups):
        specs.append(0.78)
        plan.append(("label", label))
        for page in gp:
            specs.append(0.95)
            plan.append(("link", page))
        if gi < len(groups) - 1:
            specs.append(0.12)
            plan.append(("sep", None))
    specs.append(1.0)

    nav = st.columns(specs, vertical_alignment="center")

    with nav[0]:
        st.markdown(
            f'<div class="nav-logo">'
            f'<span class="nav-title">🛡️ SAKSI</span>'
            f'<span class="nav-status">{status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    for col, (jenis, payload) in zip(nav[1:-1], plan):
        if jenis == "label":
            col.markdown(f'<div class="nav-grp">{payload}</div>', unsafe_allow_html=True)
        elif jenis == "link":
            col.page_link(payload, label=payload.title, use_container_width=True)
        else:  # sep
            col.markdown('<div class="nav-sep"></div>', unsafe_allow_html=True)

    with nav[-1]:
        if st.button("🚪 Logout", use_container_width=True):
            for k in ["authenticated", "user", "raw_bytes", "raw_name", "upl"]:
                st.session_state.pop(k, None)
            st.rerun()

    nav_router.run()
