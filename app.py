import os
import re
import math
import sqlite3
import requests
import markdown
from difflib import SequenceMatcher
from datetime import datetime

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, abort
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "data_jogja.csv")
DB_PATH = os.path.join(BASE_DIR, "wisata.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

CATEGORY_RULES = {
    "candi": [
        "candi", "prambanan", "borobudur", "ratu boko", "ratuboko", "ijo",
        "sambisari", "kalasan", "plaosan", "barong", "gebang", "banyunibo",
    ],
    "gunung": [
        "gunung", "merapi", "merbabu", "bukit", "puncak", "hill", "kaliurang",
        "lereng", "jurang", "hutan pinus", "pegunungan",
    ],
    "tebing": ["tebing", "breksi", "cliff", "karang", "ngarai"],
    "pantai": ["pantai", "beach", "laut", "pasir"],
    "museum": ["museum", "monumen", "galeri"],
    "wisata air": ["air terjun", "sungai", "waterpark", "embung", "waduk", "goa pindul"],
    "agrowisata": ["agrowisata", "kebun", "pertanian", "perkebunan"],
    "kuliner": ["kuliner", "makanan", "resto", "restaurant", "warung"],
}

CATEGORY_OPTIONS = [
    "candi", "gunung", "tebing", "pantai", "museum", "wisata air", "agrowisata",
    "budaya dan sejarah", "alam", "buatan", "religi", "kuliner", "desa wisata",
]


def normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value).lower().strip()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def currency(value: int | float | None) -> str:
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "Gratis / belum tersedia"
    return "Rp {:,}".format(value).replace(",", ".")


@app.template_filter("rupiah")
def rupiah_filter(value):
    return currency(value)


@app.template_filter("short")
def short_filter(value, length=150):
    text = str(value or "")
    return text if len(text) <= length else text[:length].rsplit(" ", 1)[0] + "..."


def derive_category(row: pd.Series) -> str:
    nama = normalize_text(row.get("nama", ""))
    tipe = normalize_text(row.get("type", ""))
    desc = normalize_text(row.get("description", ""))
    full_text = f"{nama} {tipe} {desc}"

    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in full_text for keyword in keywords):
            return category

    if tipe in ["budaya dan sejarah", "budaya sejarah"]:
        return "budaya dan sejarah"
    return tipe or "lainnya"


def prepare_data(csv_path: str = CSV_PATH) -> pd.DataFrame:
    """Data preparation agar dataset siap dipakai aplikasi rekomendasi."""
    df = pd.read_csv(csv_path)

    required_columns = [
        "no", "nama", "type", "vote_average", "vote_count", "htm_weekday",
        "htm_weekend", "latitude", "longitude", "image", "description",
    ]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Kolom dataset tidak lengkap: {missing}")

    df = df[required_columns].copy()

    df["nama"] = df["nama"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip().str.replace("_", " ", regex=False)
    df["image"] = df["image"].astype(str).str.strip()
    df["description"] = df["description"].astype(str).str.strip()

    numeric_columns = ["vote_average", "vote_count", "htm_weekday", "htm_weekend", "latitude", "longitude"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["nama", "latitude", "longitude"])
    df = df[(df["latitude"].between(-90, 90)) & (df["longitude"].between(-180, 180))]

    df["vote_average"] = df["vote_average"].fillna(0).clip(0, 5)
    df["vote_count"] = df["vote_count"].fillna(0).astype(int)
    df["htm_weekday"] = df["htm_weekday"].fillna(0).astype(int)
    df["htm_weekend"] = df["htm_weekend"].fillna(0).astype(int)
    df["image"] = df["image"].replace("nan", "")
    df["description"] = df["description"].replace("nan", "Deskripsi belum tersedia.")

    # Menghapus duplikat berdasarkan nama dan koordinat.
    df = df.drop_duplicates(subset=["nama", "latitude", "longitude"], keep="first")

    # Feature engineering untuk rekomendasi.
    df["derived_category"] = df.apply(derive_category, axis=1)
    df["search_text"] = (
        df["nama"].map(normalize_text) + " "
        + df["type"].map(normalize_text) + " "
        + df["derived_category"].map(normalize_text) + " "
        + df["description"].map(normalize_text)
    )

    df = df.reset_index(drop=True)
    df.insert(0, "id", df.index + 1)
    return df


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False) -> None:
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    df = prepare_data(CSV_PATH)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS wisata")
    cur.execute(
        """
        CREATE TABLE wisata (
            id INTEGER PRIMARY KEY,
            no INTEGER,
            nama TEXT NOT NULL,
            type TEXT,
            derived_category TEXT,
            vote_average REAL,
            vote_count INTEGER,
            htm_weekday INTEGER,
            htm_weekend INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            image TEXT,
            description TEXT,
            search_text TEXT
        )
        """
    )

    columns = [
        "id", "no", "nama", "type", "derived_category", "vote_average", "vote_count",
        "htm_weekday", "htm_weekend", "latitude", "longitude", "image", "description", "search_text",
    ]
    df[columns].to_sql("wisata", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def keyword_score(keyword: str, nama: str, search_text: str) -> float:
    keyword = normalize_text(keyword)
    if not keyword:
        return 1.0

    text = normalize_text(search_text)
    name = normalize_text(nama)
    keyword_tokens = set(keyword.split())
    text_tokens = set(text.split())

    substring_score = 1.0 if keyword in text else 0.0
    overlap_score = len(keyword_tokens & text_tokens) / max(len(keyword_tokens), 1)
    name_similarity = SequenceMatcher(None, keyword, name).ratio()

    return max(substring_score, overlap_score, name_similarity)


def category_score(category: str, row: sqlite3.Row) -> float:
    category = normalize_text(category)
    if not category:
        return 1.0

    derived = normalize_text(row["derived_category"])
    tipe = normalize_text(row["type"])
    text = normalize_text(row["search_text"])

    if category == derived or category == tipe or category in text:
        return 1.0

    # Sinonim sederhana agar input user seperti "budaya" tetap cocok dengan Budaya dan Sejarah.
    if category == "budaya" and "budaya" in text:
        return 1.0
    if category == "alam" and (derived in ["gunung", "tebing", "pantai", "wisata air"] or "alam" in text):
        return 0.85

    return 0.0


def get_all_wisata():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM wisata").fetchall()
    conn.close()
    return rows


def get_wisata_by_id(wisata_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM wisata WHERE id = ?", (wisata_id,)).fetchone()
    conn.close()
    return row


def recommend_wisata(category: str, keyword: str, user_lat: float | None, user_lon: float | None, limit: int = 5):
    rows = get_all_wisata()
    scored = []

    has_location = user_lat is not None and user_lon is not None

    for row in rows:
        c_score = category_score(category, row)
        k_score = keyword_score(keyword, row["nama"], row["search_text"])
        rating_norm = float(row["vote_average"] or 0) / 5

        if has_location:
            distance = haversine_km(user_lat, user_lon, row["latitude"], row["longitude"])
            # Radius Jogja dan sekitarnya biasanya < 100 km. Semakin dekat, skor semakin besar.
            distance_norm = max(0.0, 1 - min(distance, 100) / 100)
        else:
            distance = None
            distance_norm = 0.5

        # Skor akhir mempertimbangkan kategori, keyword, jarak, dan rating.
        final_score = (
            0.35 * c_score
            + 0.35 * k_score
            + 0.20 * distance_norm
            + 0.10 * rating_norm
        )

        # Jika user mengisi filter, prioritaskan kandidat yang masih punya kecocokan.
        if category or keyword:
            if c_score <= 0 and k_score < 0.35:
                continue

        item = dict(row)
        item["distance_km"] = distance
        item["score"] = round(final_score * 100, 2)
        item["category_score"] = round(c_score, 2)
        item["keyword_score"] = round(k_score, 2)
        scored.append(item)

    scored.sort(key=lambda x: (x["score"], x["vote_average"], x["vote_count"]), reverse=True)
    return scored[:limit]


def generate_rule_based_itinerary(wisata: sqlite3.Row) -> str:
    category = normalize_text(wisata["derived_category"])
    nama = wisata["nama"]

    if category in ["candi", "budaya dan sejarah", "museum", "religi"]:
        focus = "eksplorasi sejarah, foto arsitektur, dan membaca informasi lokasi"
        tips = "Gunakan pakaian nyaman, datang pagi agar tidak terlalu panas, dan siapkan air minum."
    elif category in ["gunung", "tebing", "alam", "pantai", "wisata air"]:
        focus = "menikmati pemandangan, foto, jalan santai, dan istirahat di area terbaik"
        tips = "Gunakan alas kaki nyaman, cek cuaca, dan hindari area berbahaya saat hujan."
    else:
        focus = "menikmati fasilitas utama, berfoto, dan mencoba aktivitas yang tersedia"
        tips = "Datang lebih awal agar waktu kunjungan lebih fleksibel."

    return f"""
### Itinerary 1 Hari ke {nama}

**07.00 - 08.00** — Berangkat dari lokasi awal menuju {nama}.  
**08.00 - 08.30** — Tiba di lokasi, membeli tiket, dan orientasi area wisata.  
**08.30 - 10.30** — Aktivitas utama: {focus}.  
**10.30 - 11.30** — Istirahat, membeli minuman/makanan ringan, dan mengambil foto tambahan.  
**11.30 - 13.00** — Makan siang di area sekitar wisata.  
**13.00 - 14.30** — Eksplorasi area tambahan atau spot foto terbaik.  
**14.30 - 15.00** — Review foto, membeli oleh-oleh kecil jika tersedia, lalu persiapan pulang.  
**15.00 - selesai** — Perjalanan pulang.

**Tips:** {tips}
""".strip()

def generate_ai_itinerary(wisata: sqlite3.Row) -> str:
    """
    Membuat itinerary wisata menggunakan Gemini REST API.
    Jika Gemini gagal, sistem memakai itinerary lokal.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        return generate_rule_based_itinerary(wisata) + "\n\nCatatan: GEMINI_API_KEY belum terbaca dari file .env."

    prompt = f"""
Kamu adalah asisten perjalanan wisata di Yogyakarta.

Buatkan itinerary wisata 1 hari dalam Bahasa Indonesia.
Gunakan format markdown tabel yang rapi.
Jangan beri respon 'Tentu, ini dia itinerary wisata 1 hari ke ...' langsung saja ke rekomndasi itinerarynya

Data wisata:
- Nama tempat: {wisata['nama']}
- Kategori: {wisata['derived_category']}
- Deskripsi: {wisata['description']}
- HTM weekday: {currency(wisata['htm_weekday'])}
- HTM weekend: {currency(wisata['htm_weekend'])}
- Rating: {wisata['vote_average']} dari 5
- Jumlah rating/pengunjung: {wisata['vote_count']}

Format output wajib seperti ini:

## Itinerary 1 Hari ke {wisata['nama']}

| Waktu | Kegiatan | Keterangan |
|---|---|---|
| 07.00 - 08.00 | ... | ... |
| 08.00 - 10.00 | ... | ... |
| 10.00 - 12.00 | ... | ... |
| 12.00 - 13.00 | ... | ... |
| 13.00 - 15.00 | ... | ... |

## Tips Kunjungan

- ...
- ...
- ...

## Estimasi Biaya

| Kebutuhan | Estimasi |
|---|---|
| Tiket masuk | ... |
| Makan/minum | ... |
| Transportasi | ... |
| Total perkiraan | ... |

Jangan membuat informasi yang terlalu berlebihan.
Jika data tidak tersedia, tulis sebagai estimasi.
"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            return (
                generate_rule_based_itinerary(wisata)
                + f"\n\nCatatan: Gemini gagal digunakan. Status code: {response.status_code}. Response: {response.text}"
            )

        data = response.json()

        itinerary_text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if itinerary_text:
            return itinerary_text

        return generate_rule_based_itinerary(wisata) + "\n\nCatatan: Gemini tidak mengembalikan teks."

    except Exception as error:
        return generate_rule_based_itinerary(wisata) + f"\n\nCatatan: Gemini gagal digunakan. Error: {error}"

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    form = {"category": "", "keyword": "", "lat": "", "lon": ""}

    if request.method == "POST":
        form["category"] = request.form.get("category", "").strip()
        form["keyword"] = request.form.get("keyword", "").strip()
        form["lat"] = request.form.get("lat", "").strip()
        form["lon"] = request.form.get("lon", "").strip()

        try:
            lat = float(form["lat"])
            lon = float(form["lon"])
        except (TypeError, ValueError):
            lat = lon = None

        results = recommend_wisata(form["category"], form["keyword"], lat, lon, limit=5)

    return render_template(
        "index.html",
        categories=CATEGORY_OPTIONS,
        results=results,
        form=form,
        now=datetime.now().year,
    )


@app.route("/detail/<int:wisata_id>")
def detail(wisata_id):
    wisata = get_wisata_by_id(wisata_id)
    if not wisata:
        abort(404)
    lat = request.args.get("lat", "")
    lon = request.args.get("lon", "")
    return render_template("detail.html", wisata=wisata, lat=lat, lon=lon, itinerary=None, now=datetime.now().year)


@app.route("/itinerary/<int:wisata_id>")
def itinerary(wisata_id):
    wisata = get_wisata_by_id(wisata_id)
    if not wisata:
        abort(404)
    lat = request.args.get("lat", "")
    lon = request.args.get("lon", "")
    
    itinerary_text = generate_ai_itinerary(wisata)
    itinerary_html = markdown.markdown(itinerary_text, extensions=["tables"])

    return render_template(
        "detail.html",
        wisata=wisata,
        lat=lat,
        lon=lon,
        itinerary=itinerary_html,
        now=datetime.now().year
    )


@app.route("/api/recommend")
def api_recommend():
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except ValueError:
        lat = lon = None

    results = recommend_wisata(category, keyword, lat, lon, limit=5)
    return {"total": len(results), "results": results}


@app.cli.command("prepare-db")
def prepare_db_command():
    init_db(force=True)
    print(f"Database berhasil dibuat: {DB_PATH}")

@app.route("/panduan")
def panduan():
    """
    Menampilkan halaman About Us yang berisi informasi sistem,
    spesifikasi teknologi pendukung, serta panduan manual penggunaan aplikasi.
    """
    # Mengirim parameter 'now' agar tahun pada footer di base.html tetap ter-render dinamis
    return render_template("panduan.html", now=datetime.now().year)

@app.route("/about")
def about():
    """
    Menampilkan halaman profil resmi JogjaTrip Recommender yang berisi
    latar belakang proyek, visi, misi, dan nilai pengembangan platform.
    """
    return render_template("about.html", now=datetime.now().year)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/map-explorer")
def map_explorer():
    """Mengambil semua titik koordinat wisata untuk dipetakan ke Leaflet.js"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nama, type, latitude, longitude, vote_average, image FROM wisata")
    wisata_data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template("map.html", wisata_list=wisata_data, now=datetime.now().year)

@app.route("/analytics")
def analytics():
    """Mengagregasi data wisata untuk visualisasi Chart.js"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Hitung total destinasi per kategori
    cursor.execute("SELECT type, COUNT(*) as jumlah FROM wisata GROUP BY type")
    kategori_rows = cursor.fetchall()
    kategori_data = {row['type'].replace('_', ' ').title(): row['jumlah'] for row in kategori_rows}
    
    # 2. Ambil 5 wisata dengan ulasan terbanyak
    cursor.execute("SELECT nama, vote_count FROM wisata ORDER BY vote_count DESC LIMIT 5")
    populer_rows = cursor.fetchall()
    populer_data = {row['nama']: row['vote_count'] for row in populer_rows}
    
    conn.close()
    return render_template("analytics.html", kategori=kategori_data, populer=populer_data, now=datetime.now().year)

# Database otomatis dibuat saat aplikasi pertama kali dijalankan.
init_db(force=True)

if __name__ == "__main__":
    app.run(debug=True)
