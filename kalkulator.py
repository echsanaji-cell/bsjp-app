"""
kalkulator.py
Menghitung jumlah lot, stop loss, target jual, dan risiko untuk satu transaksi.
"""

import math

LEMBAR_PER_LOT = 100
FEE_BELI_PCT = 0.15   # perkiraan biaya beli (%). Cek biaya di akun Stockbit-mu lalu sesuaikan.
FEE_JUAL_PCT = 0.25   # perkiraan biaya jual + pajak (%). Cek juga di Stockbit.


def fraksi_harga(harga: float) -> int:
    """Kelipatan harga yang berlaku di BEI. Cek ketentuan BEI terbaru kalau ada perubahan."""
    if harga < 200:
        return 1
    if harga < 500:
        return 2
    if harga < 2000:
        return 5
    if harga < 5000:
        return 10
    return 25


def bulatkan(harga: float, arah: str = "terdekat") -> int:
    """Bulatkan harga ke fraksi BEI yang valid."""
    f = fraksi_harga(harga)
    nilai = harga / f
    if arah == "bawah":
        n = math.floor(nilai + 1e-9)
    elif arah == "atas":
        n = math.ceil(nilai - 1e-9)
    else:
        n = round(nilai)
    return int(n * f)


def hitung_rencana(
    modal: float,
    harga_beli: float,
    stop_pct: float = 2.0,
    target_pct: float = 3.0,
    risiko_pct: float = 2.0,
) -> dict:
    """
    modal      : uang yang disiapkan untuk trading (Rp)
    harga_beli : harga beli per lembar (Rp)
    stop_pct   : batas rugi dari harga beli (%)
    target_pct : target untung dari harga beli (%)
    risiko_pct : rugi maksimal yang rela ditanggung per transaksi, sebagai % dari modal
    """
    harga_beli = bulatkan(harga_beli, "terdekat")
    stop = bulatkan(harga_beli * (1 - stop_pct / 100), "bawah")
    if stop >= harga_beli:                      # stop minimal 1 fraksi di bawah harga beli
        stop = harga_beli - fraksi_harga(harga_beli)
    target = bulatkan(harga_beli * (1 + target_pct / 100), "atas")

    biaya_beli_per_lembar = harga_beli * (1 + FEE_BELI_PCT / 100)
    hasil_stop_per_lembar = stop * (1 - FEE_JUAL_PCT / 100)
    hasil_target_per_lembar = target * (1 - FEE_JUAL_PCT / 100)

    rugi_per_lembar = max(biaya_beli_per_lembar - hasil_stop_per_lembar, 0.01)
    untung_per_lembar = max(hasil_target_per_lembar - biaya_beli_per_lembar, 0)

    risiko_maks_rp = modal * risiko_pct / 100
    lembar_dari_risiko = risiko_maks_rp / rugi_per_lembar
    lembar_dari_modal = modal / biaya_beli_per_lembar
    pembatas = "risiko" if lembar_dari_risiko <= lembar_dari_modal else "modal"

    lot = int(min(lembar_dari_risiko, lembar_dari_modal) // LEMBAR_PER_LOT)
    lembar = lot * LEMBAR_PER_LOT

    impas = bulatkan(biaya_beli_per_lembar / (1 - FEE_JUAL_PCT / 100), "atas")

    return {
        "modal": modal,
        "harga_beli": harga_beli,
        "stop": stop,
        "target": target,
        "impas": impas,
        "lot": lot,
        "lembar": lembar,
        "pembatas": pembatas,
        "total_beli": round(lembar * biaya_beli_per_lembar),
        "rugi_stop": round(lembar * rugi_per_lembar),
        "rugi_stop_pct": (lembar * rugi_per_lembar / modal * 100) if modal else 0,
        "untung_target": round(lembar * untung_per_lembar),
        "rasio": untung_per_lembar / rugi_per_lembar,
        # untuk pesan kalau 1 lot saja belum cukup
        "biaya_1_lot": round(LEMBAR_PER_LOT * biaya_beli_per_lembar),
        "rugi_1_lot": round(LEMBAR_PER_LOT * rugi_per_lembar),
    }