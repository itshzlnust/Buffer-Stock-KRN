# Sistem Buffer Stock

Sistem manajemen inventaris untuk memantau stok, pemakaian, dan pengajuan pembelian barang di warehouse.

## Fitur

- **Dashboard** - Ringkasan stok, PR pending, dan peringatan stok menipis
- **Daftar Barang** - Kelola data master barang (CRUD)
- **Stok Barang** - Monitor stok saat ini, safety stock, dan reorder point
- **Pemakaian Barang** - Input data pemakaian barang per bulan dan per tahun
- **Pengajuan Pembelian (PR)** - Buat, approve, dan lacak pengajuan pembelian barang
- **Rekomendasi Buffer** - Prioritas buffer stock berdasarkan perhitungan SAW
- **Export CSV** - Download semua data dalam format CSV
- **Perhitungan SAW** - Menghitung nilai preferensi dengan metode Simple Additive Weighting
- **Kriteria SAW** - Konfigurasi bobot kriteria untuk perhitungan

## Kriteria SAW

| Kode | Nama | Bobot | Tipe |
|------|------|-------|------|
| C1 | Average Demand | 0.25 | Benefit |
| C2 | Lead Time | 0.20 | Cost |
| C3 | Item Cost | 0.15 | Cost |
| C4 | Stock Out Frequency | 0.20 | Benefit |
| C5 | Criticality Level | 0.20 | Benefit |

## Cara Menjalankan

```bash
# 1. Buat virtual environment
python -m venv venv

# 2. Install dependencies
venv\Scripts\pip install flask flask-sqlalchemy numpy pandas werkzeug

# 3. Seed database dengan data dummy
venv\Scripts\python seeder.py

# 4. Jalankan aplikasi
venv\Scripts\python run.py
```

Buka browser dan akses: **http://localhost:5000**

## Struktur Project

```
sistem_saw_buffer_stock/
├── app/
│   ├── __init__.py
│   ├── models.py          # Database models (Item, Stock, Usage, PR, dll)
│   ├── routes.py          # Flask routes
│   ├── saw_algorithm.py   # Perhitungan SAW
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/         # HTML templates
├── instance/warehouse.db
├── seeder.py
└── run.py
```

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Math**: NumPy

## Data Dummy

Sistem dilengkapi dengan 48 barang warehouse, 576 data pemakaian (12 bulan × 48 barang), dan 15 pengajuan pembelian.
