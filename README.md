# JogjaTrip Recommender

Aplikasi website rekomendasi tempat wisata Yogyakarta berbasis Python, Flask, SQLite, dan dataset `data_jogja.csv`.

## Fitur

1. User memilih kategori wisata seperti candi, gunung, tebing, pantai, museum, wisata air, dan lainnya.
2. User memasukkan keyword wisata, misalnya `candi Borobudur`, `candi`, atau `tebing breksi`.
3. Sistem mengambil GPS/lokasi user menggunakan browser Geolocation API.
4. Sistem menampilkan 5 rekomendasi wisata berdasarkan:
   - kecocokan kategori,
   - kecocokan keyword,
   - jarak terdekat dari user,
   - rating wisata.
5. User dapat membuka detail wisata berisi foto, deskripsi, HTM weekday/weekend, rating, jumlah rating/pengunjung, maps, dan tombol itinerary.
6. Tombol itinerary akan membuat rencana perjalanan. Jika `GEMINI_API_KEY` tersedia, itinerary dibuat dengan GenAI. Jika tidak, sistem memakai template lokal.

## Struktur Project

```text
wisata_recommender/
├── app.py
├── requirements.txt
├── .env.example
├── wisata.db             
├── data/
│   └── data_jogja.csv
├── templates/
│   ├── base.html
│   ├── index.html
│   └── detail.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── location.js
```

## Data Preparation

Tahap data preparation dilakukan di fungsi `prepare_data()` pada `app.py`:

- validasi kolom wajib dataset,
- konversi kolom numerik seperti rating, HTM, latitude, dan longitude,
- drop data tanpa koordinat valid,
- mengisi nilai kosong,
- menghapus duplikasi berdasarkan nama dan koordinat,
- normalisasi teks untuk pencarian,
- membuat kategori turunan seperti `candi`, `gunung`, dan `tebing`,
- membuat kolom `search_text` untuk pencocokan keyword.

## Rumus Jarak

Jarak user ke tempat wisata dihitung menggunakan rumus Haversine karena data lokasi berbentuk latitude dan longitude.

## Skor Rekomendasi

Skor akhir dihitung dengan bobot:

```text
35% kecocokan kategori
35% kecocokan keyword
20% jarak terdekat
10% rating wisata
```

## Cara Menjalankan

### 1. Buat virtual environment

```bash
python -m venv venv
```

### 2. Aktifkan virtual environment

Windows PowerShell:

```bash
venv\Scripts\activate
```

Mac/Linux:

```bash
source venv/bin/activate
```

### 3. Install dependency

```bash
pip install -r requirements.txt
```

### 4. Jalankan aplikasi

```bash
python app.py
```

Buka di browser:

```text
http://127.0.0.1:5000
```

## Konfigurasi GenAI Opsional

Salin file `.env.example` menjadi `.env`:

```bash
cp .env.example .env
```

Isi API key:

```text
GEMINI_API_KEY=isi_api_key
```

Jika API key tidak diisi, fitur itinerary tetap berjalan menggunakan template lokal.
