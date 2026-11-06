"""
data_source.py
Mengambil data harga saham IDX (Bursa Efek Indonesia).
Sumber saat ini: Yahoo Finance (via yfinance). Data bisa tertunda.
"""

import pandas as pd
import yfinance as yf

# Daftar awal saham likuid untuk uji coba (bisa diganti/ditambah nanti)
DAFTAR_SAHAM_AWAL = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM",
    "ASII", "GOTO", "ADRO", "ANTM", "UNVR",
]


def ke_ticker_yahoo(kode: str) -> str:
    """Ubah kode Stockbit (mis. 'BBCA') jadi format Yahoo ('BBCA.JK')."""
    kode = kode.strip().upper()
    if not kode.endswith(".JK"):
        kode += ".JK"
    return kode


def ambil_harga(kode: str, periode: str = "6mo") -> pd.DataFrame:
    """
    Ambil data harian satu saham.
    Kolom hasil: Open, High, Low, Close, Volume, Nilai, Kode
    'Nilai' = perkiraan nilai transaksi (Close x Volume) dalam rupiah.
    Mengembalikan DataFrame kosong kalau gagal.
    """
    ticker = ke_ticker_yahoo(kode)
    try:
        df = yf.Ticker(ticker).history(
            period=periode, interval="1d", auto_adjust=False
        )
    except Exception as e:
        print(f"[GAGAL] {kode}: {e}")
        return pd.DataFrame()

    if df.empty:
        print(f"[KOSONG] {kode}: tidak ada data")
        return pd.DataFrame()

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)  # buang info zona waktu
    df.index.name = "Tanggal"
    df = df.dropna()
    df = df[df["Volume"] > 0]  # buang hari tanpa transaksi
    df["Nilai"] = df["Close"] * df["Volume"]
    df["Kode"] = kode.strip().upper().replace(".JK", "")
    return df


def ambil_banyak(daftar_kode: list[str], periode: str = "6mo") -> dict[str, pd.DataFrame]:
    """Ambil data banyak saham sekaligus. Hasil: {kode: DataFrame}."""
    hasil = {}
    for kode in daftar_kode:
        df = ambil_harga(kode, periode)
        if not df.empty:
            hasil[kode.strip().upper()] = df
    return hasil


if __name__ == "__main__":
    # Tes cepat: jalankan  python data_source.py
    data = ambil_banyak(DAFTAR_SAHAM_AWAL, periode="1mo")
    print(f"\nBerhasil ambil {len(data)} dari {len(DAFTAR_SAHAM_AWAL)} saham\n")
    for kode, df in data.items():
        terakhir = df.iloc[-1]
        print(
            f"{kode:5s} | {df.index[-1].date()} | "
            f"Close: {terakhir['Close']:>8,.0f} | "
            f"Nilai: Rp {terakhir['Nilai'] / 1e9:>8,.1f} M"
        )