"""
screener.py
Menilai saham untuk konsep BSJP (beli sore jual pagi).
Setiap saham diberi skor 0-100, label, dan alasan dalam bahasa sederhana.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
from data_source import ambil_banyak, DAFTAR_SAHAM_AWAL

# ===== PENGATURAN (bisa diubah sesuai selera) =====
MIN_HARGA = 50                      # di bawah ini dianggap saham "gocap"/terlalu murah
MIN_NILAI_RATA2 = 5_000_000_000     # rata-rata nilai transaksi harian minimal Rp 5 miliar
MIN_DATA_HARI = 30                  # minimal jumlah hari data
BATAS_LAYAK = 70                    # skor >= ini -> "Layak dipantau"
BATAS_WASPADA = 45                  # skor >= ini -> "Waspada", di bawahnya "Hindari"

JAM_TUTUP_DATA = time(16, 15)  # setelah jam ini data hari itu dianggap final (WIB)


def bursa_sudah_tutup() -> bool:
    """True kalau data hari terakhir sudah final (bursa tutup, akhir pekan, atau belum buka)."""
    sekarang = datetime.now(ZoneInfo("Asia/Jakarta"))
    if sekarang.weekday() >= 5:          # Sabtu/Minggu
        return True
    if sekarang.time() < time(9, 0):     # belum buka, data terakhir = kemarin (final)
        return True
    return sekarang.time() >= JAM_TUTUP_DATA

def hitung_rsi(close: pd.Series, periode: int = 14) -> pd.Series:
    """RSI: ukuran seberapa 'panas' harga. Di atas 70-75 biasanya sudah jenuh beli."""
    selisih = close.diff()
    naik = selisih.clip(lower=0)
    turun = -selisih.clip(upper=0)
    rata_naik = naik.ewm(alpha=1 / periode, adjust=False).mean()
    rata_turun = turun.ewm(alpha=1 / periode, adjust=False).mean()
    rs = rata_naik / rata_turun.replace(0, float("nan"))
    return (100 - (100 / (1 + rs))).fillna(100)


def analisa_saham(df: pd.DataFrame, data_final: bool = True) -> dict | None:
    """Analisa satu saham dari data harian. Mengembalikan dict hasil, atau None kalau data kurang."""
    if len(df) < MIN_DATA_HARI:
        return None

    hari = df.iloc[-1]
    kemarin = df.iloc[-2]
    close = float(hari["Close"])
    perubahan = (close / float(kemarin["Close"]) - 1) * 100

    # Indikator
    rentang = float(hari["High"] - hari["Low"])
    posisi_close = (close - float(hari["Low"])) / rentang if rentang > 0 else 0.5
    rata_volume = float(df["Volume"].iloc[-21:-1].mean())
    rasio_volume = float(hari["Volume"]) / rata_volume if rata_volume > 0 else 0
    rata_nilai = float(df["Nilai"].iloc[-21:-1].mean())
    ma20 = float(df["Close"].rolling(20).mean().iloc[-1])
    rsi = float(hitung_rsi(df["Close"]).iloc[-1])

    hasil = {
        "kode": hari["Kode"],
        "tanggal": df.index[-1].date(),
        "close": close,
        "perubahan_pct": perubahan,
        "posisi_close": posisi_close,
        "rasio_volume": rasio_volume,
        "rsi": rsi,
        "jarak_ma20_pct": (close / ma20 - 1) * 100,
        "skor": 0,
        "label": "Hindari",
        "alasan": [],
    }

    # ===== Filter keras: kalau kena, langsung "Hindari" =====
    if close < MIN_HARGA:
        hasil["alasan"].append(
            f"Harga Rp{close:,.0f} terlalu murah (saham gocap), pergerakannya sulit diprediksi"
        )
    if rata_nilai < MIN_NILAI_RATA2:
        hasil["alasan"].append(
            f"Kurang likuid: rata-rata transaksi hanya Rp{rata_nilai / 1e9:,.1f} miliar/hari, "
            "bisa sulit dijual besok pagi"
        )
    if hasil["alasan"]:
        return hasil

    # ===== Penilaian skor =====
    skor = 0
    alasan = []

    # 1. Kekuatan penutupan (maks 25)
    if posisi_close >= 0.8:
        skor += 25
        alasan.append("Ditutup dekat harga tertinggi hari ini (pembeli masih kuat) (+25)")
    elif posisi_close >= 0.6:
        skor += 12
        alasan.append("Ditutup di bagian atas rentang harian (+12)")
    else:
        alasan.append("Ditutup jauh dari harga tertinggi, tekanan jual terasa (+0)")

    # 2. Volume dibanding rata-rata 20 hari (maks 25)
    if not data_final:
        skor += 12
        alasan.append("Volume belum bisa dinilai (bursa masih buka), diberi nilai netral (+12)")
    elif rasio_volume >= 1.5:
        skor += 25
        alasan.append(f"Volume {rasio_volume:.1f}x di atas rata-rata, banyak peminat (+25)")
    elif rasio_volume >= 1.0:
        skor += 12
        alasan.append(f"Volume normal ({rasio_volume:.1f}x rata-rata) (+12)")
    else:
        alasan.append(f"Volume sepi ({rasio_volume:.1f}x rata-rata) (+0)")

    # 3. Tren (maks 20)
    if close > ma20:
        skor += 20
        alasan.append("Harga di atas rata-rata 20 hari, tren sedang naik (+20)")
    else:
        alasan.append("Harga di bawah rata-rata 20 hari, tren belum mendukung (+0)")

    # 4. Kenaikan hari ini (maks 15)
    if 1 <= perubahan <= 5:
        skor += 15
        alasan.append(f"Naik {perubahan:.1f}% hari ini, kenaikan masih sehat (+15)")
    elif perubahan > 5:
        skor += 5
        alasan.append(f"Sudah naik {perubahan:.1f}% hari ini, risiko koreksi besok (+5)")
    elif perubahan >= 0:
        skor += 5
        alasan.append(f"Naik tipis {perubahan:.1f}% (+5)")
    else:
        alasan.append(f"Turun {abs(perubahan):.1f}% hari ini (+0)")

    # 5. RSI (maks 15)
    if 50 <= rsi <= 70:
        skor += 15
        alasan.append(f"Momentum sehat (RSI {rsi:.0f}) (+15)")
    elif rsi > 75:
        alasan.append(f"Sudah jenuh beli (RSI {rsi:.0f}), rawan turun (+0)")
    else:
        skor += 5
        alasan.append(f"Momentum biasa (RSI {rsi:.0f}) (+5)")

    hasil["skor"] = skor
    hasil["alasan"] = alasan
    if skor >= BATAS_LAYAK:
        hasil["label"] = "Layak dipantau"
    elif skor >= BATAS_WASPADA:
        hasil["label"] = "Waspada"
    else:
        hasil["label"] = "Hindari"
    return hasil


def jalankan_screener(daftar_kode: list[str], periode: str = "6mo") -> list[dict]:
    """Analisa banyak saham, hasil diurutkan dari skor tertinggi."""
    data_final = bursa_sudah_tutup()
    data = ambil_banyak(daftar_kode, periode)
    hasil = []
    for kode, df in data.items():
        h = analisa_saham(df, data_final)
        if h:
            hasil.append(h)
    return sorted(hasil, key=lambda x: x["skor"], reverse=True)


if __name__ == "__main__":
    # Tes cepat: jalankan  python screener.py
    if not bursa_sudah_tutup():
        print("PERHATIAN: bursa masih buka, data hari ini belum final.")
        print("Volume belum dinilai. Untuk BSJP, jalankan menjelang penutupan (sekitar 15.30-15.50 WIB).")
    for h in jalankan_screener(DAFTAR_SAHAM_AWAL):
        print(
            f"\n{h['kode']:5s} | Skor {h['skor']:>3} | {h['label']:<14} | "
            f"Rp{h['close']:,.0f} ({h['perubahan_pct']:+.1f}%) | {h['tanggal']}"
        )
        for a in h["alasan"]:
            print(f"   - {a}")
    print("\nCatatan: ini alat bantu analisa, bukan jaminan untung.")