"""
jurnal.py
Jurnal transaksi sederhana (SQLite). Data tersimpan di file jurnal.db.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from kalkulator import FEE_BELI_PCT, FEE_JUAL_PCT, LEMBAR_PER_LOT

DB = Path("jurnal.db")


@contextmanager
def koneksi():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with koneksi() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode TEXT NOT NULL,
                tgl_beli TEXT NOT NULL,
                harga_beli REAL NOT NULL,
                lot INTEGER NOT NULL,
                stop_loss REAL,
                target REAL,
                tgl_jual TEXT,
                harga_jual REAL,
                catatan TEXT DEFAULT ''
            )"""
        )


def tambah_beli(kode, tgl, harga, lot, stop_loss, target, catatan) -> None:
    with koneksi() as c:
        c.execute(
            "INSERT INTO transaksi (kode, tgl_beli, harga_beli, lot, stop_loss, target, catatan) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kode, tgl, harga, lot, stop_loss, target, catatan),
        )


def tutup_posisi(id_: int, tgl: str, harga: float) -> None:
    with koneksi() as c:
        c.execute(
            "UPDATE transaksi SET tgl_jual = ?, harga_jual = ? WHERE id = ?",
            (tgl, harga, id_),
        )


def hapus(id_: int) -> None:
    with koneksi() as c:
        c.execute("DELETE FROM transaksi WHERE id = ?", (id_,))


def semua() -> tuple[list[dict], list[dict]]:
    """Hasil: (posisi terbuka, riwayat selesai). Untung/rugi dihitung bersih setelah biaya."""
    with koneksi() as c:
        baris = [
            dict(r)
            for r in c.execute("SELECT * FROM transaksi ORDER BY tgl_beli DESC, id DESC")
        ]
    terbuka, riwayat = [], []
    for b in baris:
        lembar = b["lot"] * LEMBAR_PER_LOT
        b["modal_keluar"] = b["harga_beli"] * lembar * (1 + FEE_BELI_PCT / 100)
        if b["harga_jual"] is None:
            terbuka.append(b)
        else:
            hasil = b["harga_jual"] * lembar * (1 - FEE_JUAL_PCT / 100)
            b["untung"] = hasil - b["modal_keluar"]
            b["untung_pct"] = b["untung"] / b["modal_keluar"] * 100
            riwayat.append(b)
    return terbuka, riwayat


def ringkasan(riwayat: list[dict]) -> dict | None:
    if not riwayat:
        return None
    n = len(riwayat)
    menang = [r["untung"] for r in riwayat if r["untung"] > 0]
    kalah = [r["untung"] for r in riwayat if r["untung"] <= 0]
    total = sum(r["untung"] for r in riwayat)
    return {
        "jumlah": n,
        "menang_pct": len(menang) / n * 100,
        "total": total,
        "rata_untung": sum(menang) / len(menang) if menang else 0,
        "rata_rugi": sum(kalah) / len(kalah) if kalah else 0,
        "per_transaksi": total / n,
    }