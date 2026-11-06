// Service worker BSJP. Sengaja minimal:
// - Halaman dan data TIDAK disimpan (harga saham basi lebih berbahaya daripada halaman gagal dimuat).
// - Kalau jaringan putus saat membuka halaman, tampilkan halaman offline sederhana.
const VERSI = "bsjp-v1";
const HALAMAN_OFFLINE = "/static/offline.html";
const SIMPAN_AWAL = [HALAMAN_OFFLINE, "/static/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(VERSI)
      .then((c) => c.addAll(SIMPAN_AWAL))
      .catch(() => {})                 // gagal menyimpan jangan membatalkan pemasangan
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((nama) => Promise.all(nama.filter((n) => n !== VERSI).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;   // hanya urusi pembukaan halaman
  e.respondWith(
    fetch(e.request).catch(() =>
      caches.match(HALAMAN_OFFLINE).then(
        (r) => r || new Response("Tidak ada koneksi.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } })
      )
    )
  );
});