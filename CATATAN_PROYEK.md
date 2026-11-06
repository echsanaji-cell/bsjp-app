# Catatan proyek BSJP (serah terima ke chat baru)

Per 6 November 2026.

## Tujuan dan alur kerja
- Aplikasi analisa saham BSJP (beli sore jual pagi) untuk pemula, web app Flask.
- Dikembangkan di Mac (VS Code, python3 + venv), kode di GitHub, dijalankan di homeserver Ubuntu.
- Cara kerja dengan Claude: kode lengkap atau potongan yang diganti ditulis di chat, saya tempel sendiri di VS Code. Di akhir selalu ada instruksi git add/commit/push. Langkah teknis ditulis sebagai teks biasa (bukan widget), bahasa Indonesia.

## Struktur
data_source.py (yfinance), screener.py (skor 0-100 + alasan), kalkulator.py (lot/stop/target, fee 0,15% beli, 0,25% jual),
jurnal.py (SQLite), backtest.py, analisa_aturan.py, forward.py (uji ke depan), buat_ikon.py (ikon PWA),
app.py + templates/ + static/ (termasuk manifest, sw.js, ikon).

## Temuan backtest
- 10 saham awal (3 tahun, jual di harga buka besok, setelah biaya): skor gabungan belum terbukti, "Layak dipantau" lebih buruk dari "Hindari". Aturan A-E mendekati 0. Aturan F (naik >= 3% + posisi_close < 0,8) +0,24%, tapi lahir dari data yang sama (hipotesis).
- 40 saham baru (python backtest.py 3y 2 3): aturan F 1023 sinyal, +0,15% setelah fee (awal +0,15, akhir +0,16). Dengan spread 0,3% sekitar -0,15%. Kesimpulan: belum meyakinkan.
- Skor 0-100 aplikasi terbalik: skor tinggi justru hasil rencananya lebih buruk. Teks aplikasi sudah diubah supaya tidak menyiratkan skor itu sinyal beli.
- Tidak boleh mengubah atau menambah aturan setelah melihat hasil saham baru.

## Uji ke depan aturan F (forward.py, halaman /uji-depan)
- Aturan dikunci: naik >= 3% dan posisi_close < 0,8. Hanya sinyal pada atau setelah 6 November 2026.
- Hasil: beli di close, jual di harga buka besok, setelah fee (rumus sama dengan backtest). Tabel sinyal_f di jurnal.db.
- Kriteria dikunci: di bawah 100 sinyal selesai = terlalu awal; 100-299 = indikasi awal (bukan untuk uang sungguhan); mulai 300 = Lolos jika rata-rata > 0,3% dan batas bawah 95% > 0; belum meyakinkan jika 0 sampai 0,3%; gagal jika <= 0.
- Perkiraan: sekitar 1,4 sinyal per hari, jadi 100 sinyal sekitar Februari 2027 dan 300 sinyal sekitar September 2027.
- JANGAN mengubah forward.py, aturan F, atau daftar saham selama uji berjalan.

## Deploy (homeserver)
- Service systemd "bsjp" (gunicorn, 127.0.0.1:5003, 1 worker, timeout 180) di ~/bsjp-app.
- Timer "bsjp-forward": Senin-Jumat 16.30 WIB menjalankan forward.py.
- Publik di bsjp.rndsolution.id lewat Cloudflare Tunnel, dilindungi Cloudflare Access (hanya email pemilik).
- Backup jurnal.db: skrip /usr/local/bin/backup-bsjp.sh jam 02.50 (simpan 14 hari), unggah ke Google Drive lewat rclone jam 03.10.
- PWA sudah dikodekan (manifest, service worker minimal tanpa menyimpan data, ikon). Tersisa: pasang di HP.

## Status "selesai versi 1"
- [x] deploy di homeserver, Access, backup jurnal.db, kode PWA
- [ ] satu minggu timer tanpa error (cek sekitar 13 November 2026):
      journalctl -u bsjp-forward --since "7 days ago" --no-pager | grep -i -E "error|traceback|gagal"
- [ ] pasang PWA di HP dan konfirmasi

## Sengaja ditunda
- Login multi-pengguna (Access sudah cukup untuk satu pengguna).
- Notifikasi sore otomatis (tunggu aturan F lolos).
- Auto-deploy dari GitHub (opsi: self-hosted runner, repo harus private).
- Dibagikan ke pengguna lain: tunggu hasil uji ke depan.

## Tidak ada di zip (sengaja)
.env, jurnal.db, venv, .git.