# Uji aturan F di saham baru

Ditulis sebelum melihat hasil.

- Aturan: naik >= 3% hari itu + posisi_close < 0.8 (tidak diubah)
- Saham baru: 40 saham ditambahkan lewat menu Daftar Saham
- Perintah: python backtest.py 3y 2 3, lalu python analisa_aturan.py F
- Lolos: Sinyal baru >= 100 dan Buka baru % > 0,3
- Belum meyakinkan: 0 sampai 0,3
- Gagal: <= 0
- Aturan, ambang, dan daftar saham tidak diubah setelah melihat hasil


## Hasil (40 saham baru, 3y, stop 2 target 3)

- Sinyal baru: 1023
- Buka baru %: 0,15 (setelah spread: sekitar -0,15)
- Per periode: awal +0,15, akhir +0,16
- Kesimpulan: belum meyakinkan (di bawah ambang 0,3). Aturan F tidak diubah dan tidak dipakai untuk uang sungguhan.
- Skor 0-100 aplikasi tidak terbukti: skor tinggi justru lebih buruk.


## Forward test aturan F (mulai 6 November 2026)

- Aturan F tidak diubah: naik >= 3% dan posisi_close < 0,8
- Hanya sinyal pada atau setelah 6 November 2026 yang dihitung
- Hasil: beli di close, jual di harga buka besok, setelah fee (rumus sama dengan backtest)
- Di bawah 100 sinyal selesai: terlalu awal, tidak menyimpulkan apa pun
- 100-299 sinyal: indikasi awal saja, tidak untuk uang sungguhan
- Mulai 300 sinyal: Lolos jika rata-rata > 0,3% dan batas bawah 95% > 0; Belum meyakinkan jika 0-0,3%; Gagal jika <= 0