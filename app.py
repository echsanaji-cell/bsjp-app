"""
app.py
Web app BSJP (Flask). Jalankan:  python app.py
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
from flask import Flask, flash, redirect, render_template, request, url_for

from data_source import DAFTAR_SAHAM_AWAL, ambil_harga
from screener import analisa_saham, bursa_sudah_tutup, jalankan_screener
from kalkulator import hitung_rencana
import forward
import jurnal

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kunci-lokal-hanya-untuk-pengembangan")
jurnal.init_db()
forward.init_tabel()

FILE_DAFTAR = Path("daftar_saham.json")
CACHE_DETIK = 300  # hasil screener disimpan 5 menit supaya halaman cepat
_cache = {"waktu": 0, "hasil": None, "jam": "-"}


def baca_daftar() -> list[str]:
    if FILE_DAFTAR.exists():
        try:
            return json.loads(FILE_DAFTAR.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return list(DAFTAR_SAHAM_AWAL)


def simpan_daftar(daftar: list[str]) -> None:
    FILE_DAFTAR.write_text(json.dumps(daftar, indent=2), encoding="utf-8")


def hasil_screener(paksa: bool = False) -> list[dict]:
    sekarang = time.time()
    if paksa or _cache["hasil"] is None or sekarang - _cache["waktu"] > CACHE_DETIK:
        _cache["hasil"] = jalankan_screener(baca_daftar())
        _cache["waktu"] = sekarang
        _cache["jam"] = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%H:%M:%S")
    return _cache["hasil"]

def angka_modal(teks, default=0) -> int:
    """Ambil angka dari teks, mis. 'Rp 10.000.000' menjadi 10000000."""
    bersih = "".join(c for c in (teks or "") if c.isdigit())
    return int(bersih) if bersih else default


def angka_persen(teks, default: float) -> float:
    """Ambil persen dari teks, mis. '2,5' menjadi 2.5. Harus antara 0 sampai 50."""
    try:
        nilai = float((teks or "").replace(",", ".").strip())
    except ValueError:
        return default
    return nilai if 0 < nilai <= 50 else default

@app.route("/")
def index():
    hasil = hasil_screener(paksa=request.args.get("segarkan") == "1")
    return render_template(
        "index.html",
        hasil=hasil,
        final=bursa_sudah_tutup(),
        jam=_cache["jam"],
        total=len(baca_daftar()),
    )


@app.route("/saham/<kode>")
def detail(kode):
    kode = kode.upper()
    df = ambil_harga(kode, "6mo")
    if df.empty:
        flash(f"Data {kode} tidak ditemukan.", "error")
        return redirect(url_for("index"))

    h = analisa_saham(df, bursa_sudah_tutup())
    if h is None:
        flash(f"Data {kode} terlalu sedikit untuk dianalisa.", "error")
        return redirect(url_for("index"))

    df["MA20"] = df["Close"].rolling(20).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Harga",
        )
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA20"], name="Rata-rata 20 hari", line=dict(width=2))
    )
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08),
    )
    grafik = fig.to_html(full_html=False, include_plotlyjs="cdn")
    form = {
        "modal": request.args.get("modal", ""),
        "harga": request.args.get("harga", ""),
        "stop": request.args.get("stop", "2"),
        "target": request.args.get("target", "3"),
        "risiko": request.args.get("risiko", "2"),
    }
    rencana = None
    modal = angka_modal(form["modal"])
    if modal > 0:
        rencana = hitung_rencana(
            modal=modal,
            harga_beli=angka_modal(form["harga"]) or h["close"],
            stop_pct=angka_persen(form["stop"], 2.0),
            target_pct=angka_persen(form["target"], 3.0),
            risiko_pct=angka_persen(form["risiko"], 2.0),
        )
    return render_template("detail.html", h=h, grafik=grafik, form=form, rencana=rencana)


@app.route("/daftar", methods=["GET", "POST"])
def halaman_daftar():
    daftar = baca_daftar()
    if request.method == "POST":
        aksi = request.form.get("aksi")
        kode = request.form.get("kode", "").strip().upper().replace(".JK", "")
        if aksi == "tambah":
            mentah = request.form.get("kode", "").upper().replace(".JK", "")
            kandidat = [k for k in re.split(r"[\s,;]+", mentah) if k]
            baru, ditolak = [], []
            for k in kandidat:
                if k.isalpha() and len(k) == 4 and k not in daftar and k not in baru:
                    baru.append(k)
                else:
                    ditolak.append(k)
            if baru:
                daftar.extend(baru)
                simpan_daftar(daftar)
                _cache["hasil"] = None
                flash(f"{len(baru)} saham ditambahkan: {', '.join(baru)}", "ok")
            if ditolak:
                flash("Dilewati (salah format atau sudah ada): " + ", ".join(ditolak), "error")
        elif aksi == "hapus" and kode in daftar:
            daftar.remove(kode)
            simpan_daftar(daftar)
            _cache["hasil"] = None
            flash(f"{kode} dihapus.", "ok")
        return redirect(url_for("halaman_daftar"))
    return render_template("daftar.html", daftar=daftar)

@app.route("/jurnal", methods=["GET", "POST"])
def halaman_jurnal():
    hari_ini = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d")

    if request.method == "POST":
        aksi = request.form.get("aksi")
        tanggal = request.form.get("tanggal") or hari_ini

        if aksi == "beli":
            kode = request.form.get("kode", "").strip().upper().replace(".JK", "")
            harga = angka_modal(request.form.get("harga"))
            lot = angka_modal(request.form.get("lot"))
            if not kode.isalpha() or len(kode) != 4 or harga <= 0 or lot <= 0:
                flash("Isi kode saham (4 huruf), harga beli, dan lot dengan benar.", "error")
            else:
                jurnal.tambah_beli(
                    kode, tanggal, harga, lot,
                    angka_modal(request.form.get("stop")) or None,
                    angka_modal(request.form.get("target")) or None,
                    request.form.get("catatan", "").strip(),
                )
                flash(f"Pembelian {kode} dicatat.", "ok")

        elif aksi == "jual":
            harga = angka_modal(request.form.get("harga"))
            if harga <= 0:
                flash("Isi harga jual dengan benar.", "error")
            else:
                jurnal.tutup_posisi(int(request.form.get("id", 0)), tanggal, harga)
                flash("Penjualan dicatat.", "ok")

        elif aksi == "hapus":
            jurnal.hapus(int(request.form.get("id", 0)))
            flash("Catatan dihapus.", "ok")

        return redirect(url_for("halaman_jurnal"))

    terbuka, riwayat = jurnal.semua()
    return render_template(
        "jurnal.html",
        terbuka=terbuka,
        riwayat=riwayat,
        stat=jurnal.ringkasan(riwayat),
        hari_ini=hari_ini,
    )

@app.route("/uji-depan", methods=["GET", "POST"])
def halaman_uji_depan():
    if request.method == "POST":
        baru, gagal = forward.perbarui()
        flash(f"{baru} sinyal baru dicatat. Hasil yang sudah bisa diisi sudah diperbarui.", "ok")
        if gagal:
            flash("Data gagal diambil untuk: " + ", ".join(gagal), "error")
        return redirect(url_for("halaman_uji_depan"))
    return render_template("uji_depan.html", stat=forward.ringkasan())

if __name__ == "__main__":
    # Port 5001 karena port 5000 sering dipakai AirPlay di Mac
    app.run(debug=True, port=5001)