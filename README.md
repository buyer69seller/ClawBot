# Claw Royale Bot

Bot otomatis untuk Claw Royale berdasarkan `skill.md`. Menggunakan strategi hybrid 4 mode.

## Setup
- Buat file `.env` dari `config/.env.example`, isi `CLAW_API_KEY`.
- Jalankan `pip install -r requirements.txt`
- Jalankan `python -m src.main`

## Struktur
- `src/lifecycle/`: state router dan driver utama
- `src/strategy/`: logika keputusan
- `src/ai/`: persepsi dan analisis
- `src/client/`: REST dan WebSocket
- `src/game/`: state dan action

## Catatan
- Mendukung deteksi kematian via `meta.youDied`
- Handle resume target dead (1013)
- Menggunakan ETag cache untuk REST
