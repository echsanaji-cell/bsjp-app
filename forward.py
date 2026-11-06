"""
forward.py
Uji ke depan (forward test) aturan F, tanpa uang sungguhan.

Tiap sore setelah bursa tutup, saham yang memenuhi aturan F dicatat ke jurnal.db.
Besok paginya, harga buka dicatat dan hasil bersihnya dihitung dengan rumus yang sama
seperti backtest.py (hasil_bersih), jadi angkanya bisa dibandingkan langsung.

Jalankan:  python forward.py      (catat sinyal baru + isi hasil yang sudah bisa diisi)
"""

import math
import sys
from datetime import date

import pandas as pd

from backtest import baca_daftar, hasil_bersih
from data_source import ambil_harga
from jurnal import koneksi
from kalkulator import bulatkan
from screener import MIN_DATA_HARI, MIN_HARGA, analisa_saham, bursa_sudah_tutup

# ===== ATURAN F DAN KRITERIA: DIKUNCI, JANGAN DIUBAH SELAMA UJI BERJALAN =====
PERUBAHAN_MIN = 3.0            # naik minimal 3% hari itu
POSISI_CLOSE_MAX = 0.8         # close di bawah 80% rentang harian (tidak di puncak)
TANGGAL_MULAI = date(2026, 11, 6)   # hanya sinyal pada atau setelah tanggal ini (data baru)

AMBANG_LOLOS = 0.3             # rata-rata hasil bersih minimal (%), setara perkiraan spread
MIN_INDIKASI = 100             # di bawah ini: terlalu awal untuk menilai apa pun
MIN_VONIS = 300                # vonis resmi baru diberikan mulai jumlah sinyal selesai ini


def init_tabel() -> None:
    with koneksi() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sinyal_f (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode TEXT NOT NULL,
                tgl_sinyal TEXT NOT NULL,
                harga_close REAL NOT NULL,
                harga_beli REAL NOT NULL,
                perubahan_pct REAL NOT NULL,
                posisi_close REAL NOT NULL,
                tgl_buka TEXT,
                harga_buka REAL,
                ret_buka REAL,
                UNIQUE (kode, tgl_sinyal)
            )"""
        )


def cari_sinyal(df: pd.DataFrame, final: bool) -> list[dict]:
    """Hari-hari di df yang memenuhi aturan F. Hanya data sampai hari itu yang dipakai."""
    batas = len(df) if final else len(df) - 1   # buang candle hari ini kalau belum final
    hasil = []
    for i in range(MIN_DATA_HARI, batas):
        if df.index[i].date() < TANGGAL_MULAI:
            continue
        h = analisa_saham(df.iloc[: i + 1], data_final=True)
        if h is None or h["close"] < MIN_HARGA:
            continue
        if h["perubahan_pct"] >= PERUBAHAN_MIN and h["posisi_close"] < POSISI_CLOSE_MAX:
            hasil.append(h)
    return hasil


def simpan_sinyal(h: dict) -> bool:
    """Simpan satu sinyal. True kalau baru, False kalau sudah pernah dicatat."""
    with koneksi() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO sinyal_f "
            "(kode, tgl_sinyal, harga_close, harga_beli, perubahan_pct, posisi_close) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (h["kode"], h["tanggal"].isoformat(), h["close"], bulatkan(h["close"]),
             h["perubahan_pct"], h["posisi_close"]),
        )
        return cur.rowcount > 0


def isi_hasil(kode: str, df: pd.DataFrame) -> int:
    """Isi harga buka hari bursa berikutnya untuk sinyal yang belum punya hasil."""
    terisi = 0
    with koneksi() as c:
        kosong = c.execute(
            "SELECT id, tgl_sinyal, harga_beli FROM sinyal_f WHERE kode = ? AND ret_buka IS NULL",
            (kode,),
        ).fetchall()
        for r in kosong:
            berikut = df[df.index > pd.Timestamp(r["tgl_sinyal"])]
            if berikut.empty:
                continue
            buka = float(berikut.iloc[0]["Open"])
            c.execute(
                "UPDATE sinyal_f SET tgl_buka = ?, harga_buka = ?, ret_buka = ? WHERE id = ?",
                (berikut.index[0].date().isoformat(), buka,
                 hasil_bersih(r["harga_beli"], buka), r["id"]),
            )
            terisi += 1
    return terisi


def perbarui() -> tuple[int, list[str]]:
    """Catat sinyal baru dan isi hasil yang tertunda. Hasil: (jumlah sinyal baru, kode gagal)."""
    init_tabel()
    final = bursa_sudah_tutup()
    baru, gagal = 0, []
    for kode in baca_daftar():
        df = ambil_harga(kode, "6mo")
        if df.empty:
            gagal.append(kode)
            continue
        for h in cari_sinyal(df, final):
            if simpan_sinyal(h):
                baru += 1
        isi_hasil(kode, df)
    return baru, gagal


def vonis(n: int, rata: float, bawah: float) -> tuple[str, str, str]:
    """Hasil: (judul, penjelasan, kelas CSS notif). Kriteria dikunci di atas file."""
    if n < MIN_INDIKASI:
        return ("Terlalu awal",
                f"Baru {n} sinyal selesai. Butuh minimal {MIN_INDIKASI} untuk indikasi awal "
                f"dan {MIN_VONIS} untuk vonis. Jangan menyimpulkan apa pun dulu.", "peringatan")
    if n < MIN_VONIS:
        return ("Indikasi awal",
                f"{n} sinyal selesai. Rata-rata masih bisa bergeser banyak. Vonis resmi "
                f"baru diberikan mulai {MIN_VONIS} sinyal. Jangan pakai uang sungguhan.", "peringatan")
    if rata > AMBANG_LOLOS and bawah > 0:
        return ("Lolos",
                f"Rata-rata {rata:+.2f}% (> {AMBANG_LOLOS}%) dan batas bawah 95% positif. "
                "Aturan F layak diuji lanjut dengan uang kecil.", "ok")
    if rata > 0:
        return ("Belum meyakinkan",
                f"Rata-rata {rata:+.2f}% masih di bawah {AMBANG_LOLOS}% (belum menutup spread), "
                "atau batas bawahnya belum positif. Tidak dipakai untuk uang sungguhan.", "peringatan")
    return ("Gagal",
            f"Rata-rata {rata:+.2f}% tidak positif. Aturan F dibuang.", "error")


def ringkasan(batas_baris: int = 60) -> dict:
    init_tabel()
    with koneksi() as c:
        baris = [dict(r) for r in c.execute(
            "SELECT * FROM sinyal_f ORDER BY tgl_sinyal DESC, kode LIMIT ?", (batas_baris,))]
        total = c.execute("SELECT COUNT(*) FROM sinyal_f").fetchone()[0]
        ret = [r[0] for r in c.execute("SELECT ret_buka FROM sinyal_f WHERE ret_buka IS NOT NULL")]
        hari = c.execute(
            "SELECT COUNT(DISTINCT tgl_sinyal) FROM sinyal_f WHERE ret_buka IS NOT NULL").fetchone()[0]

    n = len(ret)
    rata = sum(ret) / n if n else 0.0
    if n > 1:
        sd = math.sqrt(sum((x - rata) ** 2 for x in ret) / (n - 1))
        bawah = rata - 1.96 * sd / math.sqrt(n)
    else:
        bawah = float("nan")
    judul, teks, kelas = vonis(n, rata, bawah)
    return {
        "tercatat": total,
        "selesai": n,
        "menunggu": total - n,
        "hari": hari,
        "rata": rata,
        "bawah": bawah,
        "setelah_spread": rata - 0.3,
        "naik_pct": (sum(1 for x in ret if x > 0) / n * 100) if n else 0.0,
        "vonis_judul": judul,
        "vonis_teks": teks,
        "vonis_kelas": kelas,
        "min_indikasi": MIN_INDIKASI,
        "min_vonis": MIN_VONIS,
        "baris": baris,
    }


if __name__ == "__main__":
    print("Mencatat sinyal aturan F dan mengisi hasil... (sekitar satu menit)")
    baru, gagal = perbarui()
    print(f"{baru} sinyal baru dicatat.")
    if gagal:
        print("Data gagal diambil untuk:", ", ".join(gagal))
    s = ringkasan()
    print(f"Tercatat {s['tercatat']} | selesai {s['selesai']} | menunggu {s['menunggu']}")
    if s["selesai"]:
        print(f"Rata-rata hasil bersih (jual di buka): {s['rata']:+.2f}%")
    print(f"Status: {s['vonis_judul']}. {s['vonis_teks']}")
    sys.exit(0)