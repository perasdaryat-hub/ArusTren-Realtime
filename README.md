# ArusTren Realtime

Platform berita/publisher ArusTren dengan frontend HTML, backend Python, database SQLite, autentikasi server, analytics, komentar/reaksi, dan realtime update melalui Server-Sent Events (SSE).

## Struktur project

```text
ArusTren-Realtime/
├── public/
│   └── index.html
├── server.py
├── requirements.txt
├── Dockerfile
├── render.yaml
├── package.json
├── .env.example
├── .gitignore
├── .dockerignore
├── SECURITY.md
├── CONTRIBUTING.md
├── README.md
└── DEPLOY.md
```

## Fitur

- Registrasi/login akun Gmail dengan password yang di-hash.
- Session JWT dari backend.
- Artikel disimpan di database.
- View dicatat dari kunjungan nyata dan dicegah duplikasinya per visitor/session.
- Presence/online reader menggunakan heartbeat.
- Komentar dan reaksi tersimpan di database.
- Dashboard membaca statistik dari database.
- Update realtime melalui SSE.
- Health check pada `/health`.
- Tidak menghitung pendapatan AdSense dengan CPM/view palsu.

## Menjalankan lokal

Pastikan Python 3.11+ tersedia.

```bash
python -m venv .venv
```

Aktifkan environment, lalu jalankan:

```bash
python server.py
```

Buka `http://localhost:3000`.

### Environment

Salin `.env.example` menjadi `.env` dan isi secret sendiri. Contoh:

```text
PORT=3000
DB_PATH=./arustren.sqlite
JWT_SECRET=isi-dengan-secret-acak-panjang
```

`.env` tidak boleh di-commit.

## Pemeriksaan sebelum push

```bash
python -m py_compile server.py
```

Pastikan tidak ada database lokal atau secret yang akan ikut commit:

```bash
git status
```

## Deployment

Project sudah menyediakan `Dockerfile`, `render.yaml`, dan `DEPLOY.md` untuk deployment berbasis Render.

Untuk skala yang lebih besar atau multi-instance, database sebaiknya dimigrasikan dari SQLite ke PostgreSQL.

## Catatan keamanan

Baca `SECURITY.md` sebelum menghubungkan repository ke hosting publik.