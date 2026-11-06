"""
backtest.py
Uji strategi BSJP di data historis: "kalau dulu beli di close hari itu,
bagaimana hasilnya besok?"

Jalankan:  python backtest.py              (default: 2 tahun, stop 2%, target 3%)
           python backtest.py 5y 2 3       (periode, stop %, target %)
"""

import json
import sys
from pathlib import Path

import pandas as pd

from data_source import DAFTAR_SAHAM_AWAL, ambil_banyak
from kalkulator import FEE_BELI_PCT, FEE_JUAL_PCT, hitung_rencana
from screener import MIN_DATA_HARI, MIN_HARGA, analisa_saham, bursa_sudah_tutup

PERIODE = "2y"
STOP_PCT = 2.0
TARGET_PCT = 3.0
MIN_SAMPEL = 30   # di bawah ini hasilnya terlalu sedikit untuk disimpulkan


def baca_daftar() -> list[str]:
    f = Path("daftar_saham.json")
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return list(DAFTAR_SAHAM_AWAL)


def hasil_bersih(beli: float, jual: float) -> float:
    """Persen untung/rugi bersih setelah biaya beli dan jual."""
    return (jual * (1 - FEE_JUAL_PCT / 100) / (beli * (1 + FEE_BELI_PCT / 100)) - 1) * 100


def uji_satu_saham(df: pd.DataFrame, stop_pct: float, target_pct: float) -> list[dict]:
    """Untuk tiap hari: nilai saham dengan data sampai hari itu, lalu lihat hasil besoknya."""
    baris = []
    for i in range(MIN_DATA_HARI, len(df) - 1):
        # PENTING: hanya data sampai hari i yang dipakai menilai (tidak boleh 'mengintip' besok)
        h = analisa_saham(df.iloc[: i + 1], data_final=True)
        if h is None:
            continue

        besok = df.iloc[i + 1]
        buka, tinggi, rendah, tutup = besok["Open"], besok["High"], besok["Low"], besok["Close"]

        r = hitung_rencana(1_000_000_000, h["close"], stop_pct, target_pct, 2.0)
        beli, stop, target = r["harga_beli"], r["stop"], r["target"]

        # Skenario "rencana": pasang stop loss dan target, kalau tidak kena jual di close besok.
        # Kalau stop dan target sama-sama tersentuh di hari yang sama, diasumsikan stop duluan
        # (lebih pesimis, karena dari data harian urutannya tidak bisa diketahui).
        if buka <= stop:
            jual, cara = buka, "Stop (gap turun)"
        elif buka >= target:
            jual, cara = buka, "Target (gap naik)"
        elif rendah <= stop:
            jual, cara = stop, "Stop"
        elif tinggi >= target:
            jual, cara = target, "Target"
        else:
            jual, cara = tutup, "Jual di close"

        baris.append({
            "kode": h["kode"],
            "tanggal": df.index[i].date(),
            "harga": h["close"],
            "skor": h["skor"],
            "label": h["label"],
            "posisi_close": h["posisi_close"],
            "rasio_volume": h["rasio_volume"],
            "perubahan_pct": h["perubahan_pct"],
            "rsi": h["rsi"],
            "jarak_ma20_pct": h["jarak_ma20_pct"],
            "ret_buka": hasil_bersih(beli, buka),      # jual tepat di harga buka besok
            "ret_rencana": hasil_bersih(beli, jual),   # pakai stop loss + target
            "cara_keluar": cara,
        })
    return baris


def ringkas(grup: pd.DataFrame) -> pd.Series:
    menang = grup[grup["ret_rencana"] > 0]
    kalah = grup[grup["ret_rencana"] <= 0]
    return pd.Series({
        "Sinyal": len(grup),
        "Naik di buka %": (grup["ret_buka"] > 0).mean() * 100,
        "Rata2 jual buka %": grup["ret_buka"].mean(),
        "Menang rencana %": (grup["ret_rencana"] > 0).mean() * 100,
        "Rata2 untung %": menang["ret_rencana"].mean() if len(menang) else 0.0,
        "Rata2 rugi %": kalah["ret_rencana"].mean() if len(kalah) else 0.0,
        "Rata2 rencana %": grup["ret_rencana"].mean(),
    })


def cetak_tabel(judul: str, tabel: pd.DataFrame) -> None:
    print(f"\n=== {judul} ===")
    tabel = tabel.copy()
    tabel["Sinyal"] = tabel["Sinyal"].astype(int)
    print(tabel.round(2).to_string())
    kecil = tabel[tabel["Sinyal"] < MIN_SAMPEL]
    if len(kecil):
        print(f"(!) Kelompok dengan sinyal < {MIN_SAMPEL} terlalu sedikit untuk disimpulkan: "
              + ", ".join(str(x) for x in kecil.index))

KRITERIA = {
    "Posisi close dalam rentang harian (0 = di dasar, 1 = di puncak)": (
        "posisi_close", [0, 0.2, 0.4, 0.6, 0.8, 1.0]),
    "Volume dibanding rata-rata 20 hari (x)": (
        "rasio_volume", [0, 0.5, 0.8, 1.2, 1.5, 2, float("inf")]),
    "Perubahan harga hari itu (%)": (
        "perubahan_pct", [-float("inf"), -3, -1, 0, 1, 3, 5, float("inf")]),
    "RSI": (
        "rsi", [0, 30, 40, 50, 60, 70, 100]),
    "Jarak close ke rata-rata 20 hari (%)": (
        "jarak_ma20_pct", [-float("inf"), -5, -2, 0, 2, 5, float("inf")]),
}


def laporan_kriteria(hasil: pd.DataFrame, tgl_potong) -> None:
    """Tampilkan hasil per rentang nilai tiap kriteria, dipisah periode awal dan akhir."""
    awal = hasil[hasil["tanggal"] <= tgl_potong]
    akhir = hasil[hasil["tanggal"] > tgl_potong]
    print(
        f"\nPEMBANDING (semua sinyal): jual di buka awal {awal['ret_buka'].mean():+.2f}% | "
        f"akhir {akhir['ret_buka'].mean():+.2f}%  (sudah dikurangi biaya)"
    )

    for judul, (kolom, batas) in KRITERIA.items():
        kelompok = pd.cut(hasil[kolom], batas, include_lowest=True)
        baris = []
        for rentang, grup in hasil.groupby(kelompok, observed=True):
            g_awal = grup[grup["tanggal"] <= tgl_potong]
            g_akhir = grup[grup["tanggal"] > tgl_potong]
            baris.append({
                "Rentang": str(rentang),
                "Sinyal": len(grup),
                "Naik di buka %": (grup["ret_buka"] > 0).mean() * 100,
                "Buka awal %": g_awal["ret_buka"].mean() if len(g_awal) else float("nan"),
                "Buka akhir %": g_akhir["ret_buka"].mean() if len(g_akhir) else float("nan"),
                "Rencana awal %": g_awal["ret_rencana"].mean() if len(g_awal) else float("nan"),
                "Rencana akhir %": g_akhir["ret_rencana"].mean() if len(g_akhir) else float("nan"),
            })
        cetak_tabel(judul.upper(), pd.DataFrame(baris).set_index("Rentang"))

if __name__ == "__main__":
    periode = sys.argv[1] if len(sys.argv) > 1 else PERIODE
    stop_pct = float(sys.argv[2]) if len(sys.argv) > 2 else STOP_PCT
    target_pct = float(sys.argv[3]) if len(sys.argv) > 3 else TARGET_PCT

    daftar = baca_daftar()
    print(f"Backtest {len(daftar)} saham | periode {periode} | stop {stop_pct}% | target {target_pct}%")
    print("Mengambil data dan menghitung, tunggu sebentar...\n")

    data = ambil_banyak(daftar, periode)
    semua = []
    for kode, df in data.items():
        if not bursa_sudah_tutup():
            df = df.iloc[:-1]   # buang candle hari ini yang belum final
        semua.extend(uji_satu_saham(df, stop_pct, target_pct))
        print(f"  {kode} selesai")

    if not semua:
        print("Tidak ada hasil. Cek koneksi internet.")
        sys.exit()

    hasil = pd.DataFrame(semua)
    hasil["tanggal"] = pd.to_datetime(hasil["tanggal"])
    jumlah_awal = len(hasil)
    hasil = hasil[hasil["harga"] >= MIN_HARGA].copy()
    print(f"\n{jumlah_awal - len(hasil)} sinyal saham harga < Rp{MIN_HARGA} dibuang dari analisa.")
    hasil.to_csv("hasil_backtest.csv", index=False)

    # 1) Per label
    per_label = hasil.groupby("label").apply(ringkas, include_groups=False)
    urutan = [x for x in ["Layak dipantau", "Waspada", "Hindari"] if x in per_label.index]
    per_label = per_label.loc[urutan]
    per_label.loc["SEMUA HARI (pembanding)"] = ringkas(hasil)
    cetak_tabel("RINGKASAN PER LABEL", per_label)

    # 2) Per rentang skor
    hasil["rentang"] = pd.cut(
        hasil["skor"], [-1, 39, 59, 79, 100], labels=["0-39", "40-59", "60-79", "80-100"]
    )
    per_skor = hasil.groupby("rentang", observed=True).apply(ringkas, include_groups=False)
    cetak_tabel("RINGKASAN PER RENTANG SKOR", per_skor)

    # 3) Cara keluar untuk sinyal 'Layak dipantau'
    layak = hasil[hasil["label"] == "Layak dipantau"]
    if len(layak):
        print("\n=== CARA KELUAR (khusus Layak dipantau) ===")
        print((layak["cara_keluar"].value_counts(normalize=True) * 100).round(1).to_string())

    tgl_potong = hasil["tanggal"].quantile(0.7)
    print(f"\n##### ANALISA PER KRITERIA (data dibagi: awal sampai {tgl_potong.date()}, akhir sesudahnya) #####")
    laporan_kriteria(hasil, tgl_potong)

    print("\nDetail lengkap tersimpan di hasil_backtest.csv")
    print("Catatan: hasil masa lalu tidak menjamin hasil masa depan.")