# Security Notes — ArusTren

## Jangan commit secret
Jangan pernah memasukkan password, API key, JWT secret, credential database, atau token ke Git.

Gunakan `.env` di mesin lokal/server dan jadikan `.env.example` hanya sebagai template.

## AI API keys
API key provider AI harus disimpan di server/backend untuk deployment publik. Jangan mengandalkan localStorage sebagai penyimpanan secret produksi.

## JWT
Set `JWT_SECRET` melalui environment variable pada production. Jika tidak diset, server membuat secret acak saat proses berjalan; semua token akan tidak berlaku setelah proses restart.

## Database
File SQLite production harus berada di persistent storage dan tidak boleh di-commit ke repository.

## Pelaporan
Jika menemukan credential yang terlanjur ter-commit, segera revoke/rotate credential tersebut dan hapus dari seluruh riwayat repository bila diperlukan.