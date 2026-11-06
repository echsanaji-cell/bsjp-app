"""
analisa_aturan.py
Menguji beberapa aturan gabungan dari hasil_backtest.csv (hasil python backtest.py).

Aturan ditetapkan DI MUKA (bukan dicari-cari sampai kelihatan bagus), supaya jujur.
Saham di luar 10 saham awal dipakai sebagai uji di luar sampel.

Jalankan:  python analisa_aturan.py        (ringkasan semua aturan + rincian per saham aturan A)
           python analisa_aturan.py C      (rincian per saham untuk aturan C)
"""

import math
import sys
from pathlib import Path

import pandas as pd

from kalkulator import FEE_BELI_PCT, FEE_JUAL_PCT

FILE_CSV = "hasil_backtest.csv"
MIN_SAMPEL = 30
TOTAL_BIAYA = FEE_BELI_PCT + FEE_JUAL_PCT   # perkiraan biaya pulang-pergi (%)
SPREAD_PCT = 0.3   # perkiraan kasar selisih harga jual-beli (spread) pulang-pergi, sekitar 1 fraksi harga (%)

# 10 saham tempat pola ini pertama kali ditemukan. Saham lain = uji di luar sampel.
SAHAM_PENEMUAN = {"BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "GOTO", "ADRO", "ANTM", "UNVR"}

ATURAN = {
    "A. Naik >= 3% hari itu": lambda d: d["perubahan_pct"] >= 3,
    "B. Naik 3-7% hari itu": lambda d: d["perubahan_pct"].between(3, 7),
    "C. Naik >= 3% + volume >= 1,2x": lambda d: (d["perubahan_pct"] >= 3) & (d["rasio_volume"] >= 1.2),
    "D. Naik >= 3% + RSI > 60": lambda d: (d["perubahan_pct"] >= 3) & (d["rsi"] > 60),
    "E. Naik >= 3% + di atas rata2 20 hari": lambda d: (d["perubahan_pct"] >= 3) & (d["jarak_ma20_pct"] > 0),
    "F. Naik >= 3% + close tidak di puncak": lambda d: (d["perubahan_pct"] >= 3) & (d["posisi_close"] < 0.8),
}


def muat() -> pd.DataFrame:
    if not Path(FILE_CSV).exists():
        sys.exit(f"File {FILE_CSV} belum ada. Jalankan dulu: python backtest.py 3y 2 3")
    df = pd.read_csv(FILE_CSV, parse_dates=["tanggal"])
    perlu = ["kode", "tanggal", "perubahan_pct", "rasio_volume", "rsi",
             "jarak_ma20_pct", "posisi_close", "ret_buka"]
    kurang = [k for k in perlu if k not in df.columns]
    if kurang:
        sys.exit(f"Kolom {kurang} tidak ada di {FILE_CSV}. Jalankan ulang python backtest.py")
    return df


def statistik(ret: pd.Series) -> dict:
    n = len(ret)
    if n == 0:
        return {"n": 0, "rata": float("nan"), "bawah": float("nan")}
    rata = float(ret.mean())
    se = float(ret.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    return {"n": n, "rata": rata, "bawah": rata - 1.96 * se}


def vonis(s_all: dict, s_awal: dict, s_akhir: dict, s_baru: dict) -> str:
    if s_all["n"] < MIN_SAMPEL:
        return "sampel kecil"
    if not (s_awal["rata"] > 0 and s_akhir["rata"] > 0 and s_all["bawah"] > 0):
        return "tidak"
    if s_baru["n"] < MIN_SAMPEL:
        return "belum diuji di saham baru"
    return "LOLOS" if s_baru["rata"] > 0 else "tidak"


def laporan(df: pd.DataFrame, tgl_potong) -> None:
    semua = {"PEMBANDING (semua sinyal)": lambda d: pd.Series(True, index=d.index), **ATURAN}
    baris = []
    for nama, fungsi in semua.items():
        d = df[fungsi(df)]
        s_all = statistik(d["ret_buka"])
        s_awal = statistik(d.loc[d["tanggal"] <= tgl_potong, "ret_buka"])
        s_akhir = statistik(d.loc[d["tanggal"] > tgl_potong, "ret_buka"])
        s_baru = statistik(d.loc[~d["kode"].isin(SAHAM_PENEMUAN), "ret_buka"])
        baris.append({
            "Aturan": nama,
            "Sinyal": s_all["n"],
            "Sblm biaya %": s_all["rata"] + TOTAL_BIAYA,
            "Buka %": s_all["rata"],
            "Batas bawah 95%": s_all["bawah"],
            "Stlh spread %": s_all["rata"] - SPREAD_PCT,
            "Awal %": s_awal["rata"],
            "Akhir %": s_akhir["rata"],
            "Sinyal baru": s_baru["n"],
            "Buka baru %": s_baru["rata"],
            "Vonis": "-" if nama.startswith("PEMBANDING") else vonis(s_all, s_awal, s_akhir, s_baru),
        })
    print(pd.DataFrame(baris).set_index("Aturan").round(2).to_string())


def per_saham(df: pd.DataFrame, kunci: str, tgl_potong) -> None:
    nama = next((n for n in ATURAN if n.startswith(kunci + ".")), None)
    if nama is None:
        print(f"Aturan '{kunci}' tidak dikenal. Pilih salah satu dari A sampai F.")
        return
    d = df[ATURAN[nama](df)]
    baris = []
    for kode, g in d.groupby("kode"):
        baris.append({
            "Saham": kode,
            "Sinyal": len(g),
            "Buka %": g["ret_buka"].mean(),
            "Awal %": g.loc[g["tanggal"] <= tgl_potong, "ret_buka"].mean(),
            "Akhir %": g.loc[g["tanggal"] > tgl_potong, "ret_buka"].mean(),
            "Status": "penemuan" if kode in SAHAM_PENEMUAN else "SAHAM BARU",
        })
    print(f"\n=== RINCIAN PER SAHAM: {nama} ===")
    if baris:
        print(pd.DataFrame(baris).set_index("Saham").sort_values("Sinyal", ascending=False).round(2).to_string())
    else:
        print("Tidak ada sinyal.")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    kunci = sys.argv[1].upper() if len(sys.argv) > 1 else "A"

    df = muat()
    tgl_potong = df["tanggal"].quantile(0.7)
    print(f"Data: {len(df)} sinyal dari {df['kode'].nunique()} saham | "
          f"awal sampai {tgl_potong.date()}, akhir sesudahnya")
    print(f"Hasil jual di harga buka besok, sudah dikurangi biaya (perkiraan {TOTAL_BIAYA:.2f}% pulang-pergi)\n")

    laporan(df, tgl_potong)
    per_saham(df, kunci, tgl_potong)

    print("\nCara membaca 'Vonis':")
    print("  LOLOS  = untung setelah biaya di periode awal, akhir, batas bawah 95% > 0, DAN di saham baru")
    print("  tidak  = salah satu syarat di atas gagal")
    print("  belum diuji di saham baru = lolos semua kecuali belum ada cukup sinyal dari saham baru")
    print("Catatan: sinyal di hari yang sama saling berkaitan, jadi batas bawah 95% cenderung terlalu optimis.")