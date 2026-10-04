# ArusTren — Deploy Realtime

## Pilihan paling mudah: Render
1. Buat repository Git dan masukkan folder `ArusTren-Realtime`.
2. Push folder ini ke repository.
3. Di Render pilih **New > Blueprint** dan pilih repository.
4. Render akan membaca `render.yaml`.
5. Pastikan disk `/data` aktif agar SQLite tidak hilang saat instance restart.
6. Setelah deploy, buka `/health`. Respons harus berisi `"ok": true`.

## Lokal
```bash
python server.py
```
Buka `http://localhost:3000`.

## Penting
- Jangan menghapus disk database produksi.
- `JWT_SECRET` harus berbeda dari contoh dan tidak dibagikan.
- Untuk trafik besar, pindahkan database dari SQLite ke PostgreSQL.
- AdSense revenue tetap berasal dari laporan Google AdSense, bukan perhitungan views.