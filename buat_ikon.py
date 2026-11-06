"""
buat_ikon.py
Membuat ikon PWA (PNG) untuk BSJP. Cukup dijalankan sekali:  python buat_ikon.py
Hanya memakai numpy (sudah terpasang bersama pandas) dan modul bawaan Python.
Hasil: static/icons/icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png
"""

import struct
import zlib
from pathlib import Path

import numpy as np

LATAR = (0x12, 0x32, 0x4A)      # biru tua, sama dengan menu atas aplikasi
PUTIH = (255, 255, 255)
HIJAU = (0x1E, 0x9E, 0x5A)      # hijau, sama dengan warna "naik"

# Tiga batang naik (kiri, kanan, atas, bawah) dalam skala 0..1. Semua di zona aman tengah.
BATANG = [
    ((0.23, 0.37), 0.56, PUTIH),
    ((0.43, 0.57), 0.44, PUTIH),
    ((0.63, 0.77), 0.30, HIJAU),
]
DASAR = 0.74


def cakupan_kotak_bulat(x, y, kiri, kanan, atas, bawah, radius):
    """Nilai 0..1 per piksel (anti-alias) untuk kotak dengan sudut membulat."""
    cx, cy = (kiri + kanan) / 2, (atas + bawah) / 2
    hw, hh = (kanan - kiri) / 2, (bawah - atas) / 2
    qx = np.abs(x - cx) - (hw - radius)
    qy = np.abs(y - cy) - (hh - radius)
    luar = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    dalam = np.minimum(np.maximum(qx, qy), 0)
    jarak = luar + dalam - radius          # negatif = di dalam bentuk
    return np.clip(0.5 - jarak * UKURAN, 0, 1)


def gambar(ukuran: int, bulat: bool) -> np.ndarray:
    """Hasil: array RGBA. bulat=True -> sudut transparan; False -> penuh sampai tepi."""
    global UKURAN
    UKURAN = ukuran
    kisi = (np.arange(ukuran) + 0.5) / ukuran
    x, y = np.meshgrid(kisi, kisi)
    rgba = np.zeros((ukuran, ukuran, 4), dtype=np.float64)

    if bulat:
        alfa = cakupan_kotak_bulat(x, y, 0, 1, 0, 1, 0.22)
    else:
        alfa = np.ones((ukuran, ukuran))
    for k in range(3):
        rgba[..., k] = LATAR[k]
    rgba[..., 3] = alfa * 255

    for (kiri, kanan), atas, warna in BATANG:
        c = cakupan_kotak_bulat(x, y, kiri, kanan, atas, DASAR, 0.035)[..., None]
        rgba[..., :3] = rgba[..., :3] * (1 - c) + np.array(warna) * c
    return np.clip(rgba.round(), 0, 255).astype(np.uint8)


def simpan_png(path: Path, rgba: np.ndarray) -> None:
    tinggi, lebar, _ = rgba.shape
    mentah = b"".join(b"\x00" + rgba[i].tobytes() for i in range(tinggi))

    def potongan(jenis: bytes, data: bytes) -> bytes:
        isi = jenis + data
        return struct.pack(">I", len(data)) + isi + struct.pack(">I", zlib.crc32(isi) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += potongan(b"IHDR", struct.pack(">IIBBBBB", lebar, tinggi, 8, 6, 0, 0, 0))
    png += potongan(b"IDAT", zlib.compress(mentah, 9))
    png += potongan(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    folder = Path("static/icons")
    folder.mkdir(parents=True, exist_ok=True)
    daftar = [
        ("icon-192.png", 192, True),
        ("icon-512.png", 512, True),
        ("icon-maskable-512.png", 512, False),   # penuh sampai tepi, Android yang memotong bentuknya
        ("apple-touch-icon.png", 180, False),    # iOS tidak mendukung transparan
    ]
    for nama, ukuran, bulat in daftar:
        simpan_png(folder / nama, gambar(ukuran, bulat))
        print("dibuat:", folder / nama)