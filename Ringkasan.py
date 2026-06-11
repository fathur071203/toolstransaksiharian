"""
SAKSI — alias entry point (setara app.py).
Memungkinkan `streamlit run Ringkasan.py` tetap memuat aplikasi penuh
(login + navbar atas), bukan sekadar satu halaman. Konten cockpit Ringkasan
kini ada di pages/00_Ringkasan.py.
"""
from core.shell import main

main()
