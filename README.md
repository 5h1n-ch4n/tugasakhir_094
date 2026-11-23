# Aplikasi Monitoring AWS & Prediksi Cuaca SVM

Aplikasi web untuk memantau kondisi cuaca mikro di kandang ayam pejantan
berdasarkan data Automatic Weather Station (ESP32) yang dikirim ke Firebase
Realtime Database, sekaligus menampilkan hasil prediksi Support Vector Machine
yang dihitung otomatis oleh pipeline Python melalui GitHub Actions.

## Isi Folder

```
app.py              -> entry point & routing halaman
app_config.py       -> konfigurasi, path, daftar fitur & target
firebase_client.py  -> akses Firebase Realtime Database (REST)
auth_service.py     -> autentikasi (Firebase Auth / mode lokal)
data_service.py     -> perhitungan domain (THI, rekomendasi kipas)
station_service.py  -> manajemen stasiun AWS
ui_components.py    -> komponen tampilan bersama
pages_auth.py       -> halaman sign up / sign in / lupa sandi
pages_dashboard.py  -> dashboard cuaca saat ini + prediksi
pages_prediction.py -> rincian hasil prediksi SVM
pages_history.py    -> grafik riwayat sensor
pages_stations.py   -> manajemen AWS multi-stasiun
pages_profile.py    -> profil pengguna
```

## Menjalankan di Windows

Cara tercepat — jalankan skrip setup sekali:

```powershell
cd "C:\Users\LENOVO\Documents\Tugas Akhir\streamlit_app"
powershell -ExecutionPolicy Bypass -File setup_windows.ps1
```

Skrip tersebut membuat virtual environment `.venv`, memasang seluruh
dependensi, memverifikasi impor, lalu menampilkan perintah jalannya.

### Cara manual

```powershell
cd "C:\Users\LENOVO\Documents\Tugas Akhir\streamlit_app"

# 1. Pakai virtual environment yang sudah ada, atau buat baru
#    (skrip setup dan jalankan.bat mengenali keduanya: .venv atau venv)
.\venv\Scripts\Activate.ps1

# 2. Pasang dependensi
pip install --upgrade pip
pip install -r requirements.txt

# 3. Jalankan
streamlit run app.py
```

Tanpa aktivasi venv, jalankan langsung:

```powershell
.\venv\Scripts\streamlit.exe run app.py
```

Aplikasi terbuka di `http://localhost:8501`.

> Folder `venv/` di dalam `streamlit_app/` sudah ada dan berisi Streamlit,
> tetapi belum berisi `plotly`, `joblib`, dan `firebase-admin`. Jalankan
> `pip install -r requirements.txt` di dalamnya, atau klik ganda
> `jalankan.bat` yang akan melengkapinya secara otomatis.

## Troubleshooting

### Diagnosis cepat

Error beruntun seperti ini:

```
ModuleNotFoundError: No module named 'streamlit'
ModuleNotFoundError: No module named 'plotly'
```

berarti Anda memakai virtual environment yang **belum lengkap**, bukan
kode yang rusak. Periksa dulu apa yang sebenarnya terpasang:

```powershell
.\venv\Scripts\python.exe -m pip list
```

Bila `plotly` tidak ada di daftar itu, jalankan:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

atau klik ganda `jalankan.bat` yang akan melengkapinya otomatis.

### `ModuleNotFoundError: No module named 'streamlit'` atau `'plotly'`

Dependensi belum terpasang pada interpreter yang dipakai. Jalankan skrip
perbaikan otomatis — skrip ini bisa dijalankan dengan Python apa pun,
termasuk yang belum punya Streamlit:

```powershell
python perbaiki_dependensi.py
```

Skrip akan memasang semua paket yang kurang (streamlit, plotly, pandas,
numpy, joblib, requests, scikit-learn, firebase-admin), lalu menguji impor
seluruh modul aplikasi. Bila dijalankan dari dalam virtual environment,
paket terpasang ke environment itu:

```powershell
.\venv\Scripts\python.exe perbaiki_dependensi.py
```

Untuk memastikan aplikasi memakai interpreter yang benar, cek dulu:

```powershell
python -c "import sys; print(sys.executable)"
```

-Path-nya harus mengarah ke `...Tugas Akhir\streamlit_app\venv\Scripts\python.exe`
atau `.venv\Scripts\python.exe`.

Cara paling aman: klik ganda `jalankan.bat`. Skrip itu mencari virtual
environment yang sudah ada (`.venv` atau `venv`), melengkapi dependensi,
lalu menjalankan aplikasi.

> Catatan: `plotly` **bukan** dependensi bawaan Streamlit. Sekadar
> `pip install streamlit` tidak akan memasangnya, sehingga error berikutnya
> akan muncul pada `import plotly.express as px` di `pages_dashboard.py`.
> Karena itu seluruh dependensi aplikasi ada di `requirements.txt` dan
> dipasang sekaligus.

### `ModuleNotFoundError: No module named 'firebase_admin'`

Paket ini opsional. Aplikasi tetap berjalan memakai Firebase REST API.
Pasang bila Anda memang memakai Firebase Admin SDK:

```powershell
pip install firebase-admin
```

### `OSError: [Errno 49] The name was used for a different file`

Proses Streamlit lama masih berjalan. Hentikan dulu:

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
```

### Halaman Stuck di "Connecting..."

Biasanya karena `secrets.toml` tidak terbaca atau URL Firebase salah.
Periksa `.streamlit/secrets.toml`:

```toml
[firebase]
database_url = "https://<PROJECT_ID>.firebaseio.com"
api_key = "<WEB_API_KEY>"
```

### Mode Lokal (tanpa Firebase)

Bila `secrets.toml` tidak ada, aplikasi berjalan pada mode lokal: autentikasi
disimpan di `.auth_db.json`, dan data sensor diambil dari snapshot lokal.
Cocok untuk demonstrasi antarmuka.

## Struktur Data

Pipeline Python menulis prediksi ke `predictions/{station_id}`, sedangkan data
sensor mentah ditulis ESP32 ke `AWS_Monitoring`. `firebase_client.py`
menormalkan beberapa variasi penamaan kunci agar kompatibel dengan data
yang sudah tersimpan, termasuk `daya_ina226`, `gps`, dan kecepatan angin
dalam m/s maupun km/jam.

## Catatan Keamanan

Berkas `.streamlit/secrets.toml`, `.auth_db.json`, dan `serviceAccountKey.json`
berisi kredensial. Semua sudah masuk `.gitignore` — pastikan tidak pernah
di-commit ke repositori publik.
