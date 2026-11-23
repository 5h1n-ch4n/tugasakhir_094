"""Bangkitkan data simulasi AWS mikroklimat (1 menit) yang realistis dan kontinu.

Model generatif
----------------
Data dibangkitkan dari *regime cuaca* yang persisten (markov chain per jam),
bukan dari noise per menit. Setiap regime menentukan profil sensor, sehingga:

  1. Nilai tidak pernah "tiba-tiba" berubah/spike (semua transisi halus).
  2. Cuaca pada jam t+1 dapat diprediksi dari jam t (regime bertahan
     beberapa jam) -> model SVM punya_signal yang bisa dipelajari.
  3. Label pseudo-weather di config.py (label_from_features) konsisten
     dengan kondisi fisis: RH, curah hujan, dan intensitas cahaya.

Regime
------
  ``Cerah``        RH 56-72, tanpa hujan, lux tinggi saat siang
  ``Berawan``      RH 74-86, tanpa hujan, lux tertutup
  ``Gerimis``      RH 72-85, hujan 0.3-1.5 mm/jam  -> "Hujan Ringan"
  ``Hujan Sedang`` RH 86-92, hujan 2.0-4.5 mm/jam  -> "Berang-berang"
  ``Hujan Lebat``  RH 84-96, hujan 5.5-12 mm/jam   -> "Hujan Lebat"

Kolom keluaran
--------------
  timestamp, suhu, kelembapan, tekanan, cahaya, hujan, kecepatan_angin,
  tegangan_v, arus_ma, daya_mw
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Definisi regime
# ---------------------------------------------------------------------------
#: Parameter tiap regime cuaca.
#:
#: rh_day/rh_night sengaja diberi margin agar label pseudo-weather pada
#: config.py (label_from_features) konsisten di siang maupun malam:
#:   - "Gerimis"      -> RH < 86  -> kelas "Hujan Ringan"
#:   - "Hujan Sedang" -> RH >= 86 -> kelas "Berang-berang"
#:   - "Hujan Lebat"  -> curah >= 5 mm/jam -> kelas "Hujan Lebat"
REGIMES = {
    "Cerah": dict(rh_day=63.0, rh_night=70.0, cloud=(0.03, 0.22)),
    "Berawan": dict(rh_day=80.0, rh_night=84.0, cloud=(0.55, 0.88)),
    "Gerimis": dict(rh_day=78.0, rh_night=79.0, cloud=(0.85, 1.00)),
    "Hujan Sedang": dict(rh_day=88.0, rh_night=89.0, cloud=(0.90, 1.00)),
    "Hujan Lebat": dict(rh_day=90.0, rh_night=91.0, cloud=(0.95, 1.00)),
}

#: Durasi regime (jam) -> menghasilkan sifat "persisten".
REGIME_DURATION = {
    "Cerah": (5, 12),
    "Berawan": (3, 8),
    "Gerimis": (2, 6),
    "Hujan Sedang": (2, 5),
    "Hujan Lebat": (1, 4),
}

#: Curah hujan per jam (mm) per regime.
RAIN_HOURLY = {
    "Cerah": (0.0, 0.0),
    "Berawan": (0.0, 0.0),
    "Gerimis": (0.35, 1.60),
    "Hujan Sedang": (2.20, 4.60),
    "Hujan Lebat": (5.50, 12.00),
}


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """Interpolasi halus (smoothstep) tanpa turunan diskontinu."""
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _build_regime_hours(rng: np.random.Generator, n_hours: int) -> np.ndarray:
    """Susun regime cuaca per jam memakai pola harian.

    Setiap hari diberi satu "tipe cuaca" yang membentuk urutan regime
    tertentu (mis. pagi cerah -> siang berawan -> sore hujan). Dengan cara
    ini semua kelas cuaca muncul secara merata di sepanjang rentang waktu,
    sehingga portion uji pada split temporal 80:20 tetap berisi seluruh
    kelas (bukan hanya kelas dominan di paruh akhir deret).
    """
    # (nama hari, bobot, urutan regime, durasi tiap blok dalam jam)
    day_patterns = [
        (
            "Cerah Penuh",
            0.30,
            [("Cerah", 11), ("Berawan", 4), ("Gerimis", 2), ("Berawan", 3), ("Cerah", 4)],
        ),
        (
            "Cerah Berawan",
            0.22,
            [("Cerah", 7), ("Berawan", 5), ("Gerimis", 3), ("Berawan", 5), ("Cerah", 4)],
        ),
        (
            "Berawan Dominan",
            0.18,
            [("Berawan", 6), ("Gerimis", 4), ("Berawan", 5), ("Cerah", 4), ("Berawan", 5)],
        ),
        (
            "Hujan Ringan",
            0.14,
            [("Berawan", 4), ("Gerimis", 6), ("Gerimis", 4), ("Berawan", 4), ("Cerah", 6)],
        ),
        (
            "Hujan Sedang",
            0.10,
            [("Berawan", 3), ("Gerimis", 3), ("Hujan Sedang", 5), ("Gerimis", 3),
             ("Berawan", 4), ("Cerah", 6)],
        ),
        (
            "Hujan Lebat",
            0.06,
            [("Gerimis", 3), ("Hujan Sedang", 4), ("Hujan Lebat", 4),
             ("Hujan Sedang", 3), ("Gerimis", 3), ("Berawan", 3), ("Cerah", 4)],
        ),
    ]
    names = [item[0] for item in day_patterns]
    probs = np.array([item[1] for item in day_patterns], dtype=float)
    probs = probs / probs.sum()

    # Jumlah hari yang dibutuhkan untuk menutup seluruh rentang jam.
    n_days = int(np.ceil(n_hours / 24)) + 1
    chosen = list(rng.choice(names, size=n_days, p=probs))

    # Jaminan cakupan kelas: setiap hari ke-4 adalah hari hujan, dengan
    # intensitas yang berputar (gerimis -> sedang -> lebat). Tanpa jaminan ini
    # kelas "Hujan Lebat" bisa tidak muncul sama sekali di portion uji
    # (20% akhir deret waktu) sehingga metrik per kelas tidak terukur.
    rain_cycle = ["Hujan Ringan", "Hujan Sedang", "Hujan Lebat"]
    for day_idx in range(0, n_days, 4):
        kind = rain_cycle[(day_idx // 4) % len(rain_cycle)]
        chosen[day_idx] = kind

    hours: list[str] = []
    for day_name in chosen:
        pattern = next(item[2] for item in day_patterns if item[0] == day_name)
        for regime, dur in pattern:
            hours.extend([regime] * dur)
            # Durasi tiap blok dimodifikasi sedikit agar tidak terlalu seragam.
            if rng.random() < 0.35 and dur > 2:
                hours.extend([regime] * int(rng.integers(1, 3)))

    return np.array(hours[:n_hours], dtype=object)


def generate_aws_dataset(days: int = 45, output_path: str = "data/raw_history.csv") -> pd.DataFrame:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    rng = np.random.default_rng(42)

    end_time = pd.Timestamp.now(tz="Asia/Jakarta").floor("h")
    start_time = end_time - pd.Timedelta(days=days)
    timestamps = pd.date_range(start=start_time, end=end_time, freq="1min")
    n = len(timestamps)
    hour_float = (timestamps.hour + timestamps.minute / 60.0).to_numpy()

    # -------------------------------------------------------------------------
    # Regime per jam
    # -------------------------------------------------------------------------
    n_hours = int(np.ceil(n / 60))
    regime_hours = _build_regime_hours(rng, n_hours)
    regime_minute = np.repeat(regime_hours, 60)[:n]
    # Rata-ratakan bila panjang tidak genap.
    if len(regime_minute) < n:
        regime_minute = np.pad(regime_minute, (0, n - len(regime_minute)), mode="edge")

    def regime_values(key: str, second: str | None = None) -> np.ndarray:
        """Ambil nilai parameter regime untuk setiap menit."""
        out = np.empty(n)
        for name, spec in REGIMES.items():
            mask = regime_minute == name
            if not mask.any():
                continue
            if second is None:
                out[mask] = spec[key]
            else:
                lo, hi = spec[key]
                out[mask] = rng.uniform(lo, hi, int(mask.sum()))
        return out

    # -------------------------------------------------------------------------
    # Cahaya (lux)
    # -------------------------------------------------------------------------
    solar_elev = np.maximum(0.0, np.sin((hour_float - 6.0) * np.pi / 12.0))
    daylight = _smoothstep(0.0, 0.09, solar_elev)

    cloud_minute = np.empty(n)
    for name, spec in REGIMES.items():
        mask = regime_minute == name
        if mask.any():
            cloud_minute[mask] = rng.uniform(*spec["cloud"], int(mask.sum()))
    # Haluskan perubahan awan antar menit (perubahan mendadak -> tidak realistis).
    kernel = np.ones(9) / 9.0
    cloud_minute = np.convolve(cloud_minute, kernel, mode="same")
    cloud_minute = np.clip(cloud_minute, 0.0, 1.0)

    n_days = int(np.ceil(n_hours / 24)) + 1
    moon_phase = rng.uniform(0.3, 1.0, n_days)
    day_of_run = np.minimum(timestamps.normalize().factorize()[0], len(moon_phase) - 1)
    ambient = 0.4 + 3.2 * moon_phase[day_of_run] * np.clip(solar_elev + 0.12, 0.0, 1.0) ** 0.5

    solar_light = (solar_elev ** 1.28) * (1.0 - 0.85 * cloud_minute) * 84000.0
    cahaya = solar_light * daylight + ambient * (1.0 - daylight)
    cahaya = np.clip(cahaya + rng.normal(0, 90, n), 0.0, 130000.0)

    # -------------------------------------------------------------------------
    # Curah hujan (mm/menit) dengan profil intra-jam halus
    # -------------------------------------------------------------------------
    hourly_rain_target = np.empty(n_hours)
    for name in REGIMES:
        lo, hi = RAIN_HOURLY[name]
        hours_idx = np.where(regime_hours[:n_hours] == name)[0]
        hourly_rain_target[hours_idx] = rng.uniform(lo, hi, len(hours_idx))

    # Profil intensitas dalam 1 jam (puncak di tengah, berbasis sinus).
    intra = 0.55 + 0.45 * np.sin(np.linspace(0.0, np.pi, 60))
    rain_minute = np.repeat(hourly_rain_target, 60)[:n] * np.tile(intra, n_hours)[:n]
    # Normalisasi agar jumlah per jam kembali sesuai target.
    hour_index = np.minimum(np.arange(n) // 60, n_hours - 1)
    hour_sum = np.bincount(hour_index, weights=rain_minute, minlength=n_hours)
    scale = np.where(hour_sum > 0, hourly_rain_target / np.maximum(hour_sum, 1e-9), 0.0)
    rain_minute = rain_minute * scale[hour_index]
    hujan = np.clip(rain_minute, 0.0, 0.6)

    # -------------------------------------------------------------------------
    # Suhu, kelembapan, tekanan, angin
    # -------------------------------------------------------------------------
    day_factor = rng.uniform(-1.1, 1.5, n_days)
    day_of_run_full = np.minimum(timestamps.normalize().factorize()[0], len(day_factor) - 1)

    suhu = (
        28.4
        + 4.4 * np.sin((hour_float - 8.0) * np.pi / 12.0)
        + day_factor[day_of_run_full]
        + rng.normal(0, 0.25, n)
    )

    rh_day = regime_values("rh_day")
    rh_night = regime_values("rh_night")
    daylight_mask = (hour_float >= 8.0) & (hour_float <= 17.0)
    rh_target = np.where(daylight_mask, rh_day, rh_night)
    # Drift lambat antar jam agar RH tidak terlihat stepwise.
    rh_target = pd.Series(rh_target).rolling(120, min_periods=1, center=True).mean().to_numpy()
    kelembapan = np.clip(rh_target + rng.normal(0, 1.6, n), 45.0, 99.3)

    tekanan = 1010.4 + 1.5 * np.cos((hour_float - 10.0) * np.pi / 6.0) + rng.normal(0, 0.16, n)

    kecepatan_angin = np.clip(
        5.6 + 3.0 * np.sin((hour_float - 11.0) * np.pi / 12.0) + rng.normal(0, 1.0, n),
        0.6,
        22.0,
    )

    # -------------------------------------------------------------------------
    # Efek hujan pada suhu, RH, dan angin (transisi halus di awal/akhir hujan)
    # -------------------------------------------------------------------------
    rain_hour = pd.Series(hourly_rain_target).rolling(6, min_periods=1).mean().to_numpy()
    rain_hour_min = np.repeat(rain_hour, 60)[:n]
    active_rain = np.clip(rain_hour_min / 1.2, 0.0, 1.0)
    suhu = suhu - active_rain * 2.4
    kelembapan = np.clip(kelembapan + active_rain * 4.0, 45.0, 99.4)
    kecepatan_angin = np.clip(kecepatan_angin + active_rain * 2.6, 0.6, 24.0)
    cahaya = cahaya * (1.0 - 0.45 * active_rain)

    # -------------------------------------------------------------------------
    # Anomali fisis (degradasi bertahap, bukan spike)
    # -------------------------------------------------------------------------
    # Bayangan parsial di atas sensor lux.
    for _ in range(int(days * 0.35)):
        i0 = rng.integers(120, max(121, n - 90))
        length = rng.integers(12, 45)
        sl = slice(i0, i0 + length)
        if float(np.mean(cahaya[sl])) > 2000.0:
            fade = _smoothstep(0, 6, np.arange(length, dtype=float)) * (
                1 - _smoothstep(length - 8, length, np.arange(length, dtype=float))
            )
            cahaya[sl] *= 1.0 - 0.35 * fade

    # Anemometer macet sementara (bacaan stagnan).
    for _ in range(int(days * 0.12)):
        i0 = rng.integers(200, max(201, n - 40))
        length = rng.integers(8, 22)
        sl = slice(i0, i0 + length)
        stuck = float(np.median(kecepatan_angin[sl]))
        kecepatan_angin[sl] = stuck + rng.normal(0, 0.07, length)

    # -------------------------------------------------------------------------
    # Konsumsi daya modul ESP32 + sensor (INA226)
    # -------------------------------------------------------------------------
    tegangan_v = 3.30 + rng.normal(0, 0.018, n)
    daya_mw = 108.0 + rng.normal(0, 6.0, n)
    daya_mw += 25.0 * np.clip(solar_elev, 0.0, 1.0)
    fan_trigger = (suhu >= 29.5) | (kelembapan <= 55.0)
    daya_mw = np.where(fan_trigger, daya_mw + 280.0 + rng.uniform(40, 220, n), daya_mw)
    daya_mw = np.where(suhu >= 31.0, daya_mw + rng.uniform(120, 180, n), daya_mw)

    for _ in range(int(days * 0.22)):
        i0 = rng.integers(50, max(51, n - 15))
        length = rng.integers(3, 12)
        fade = _smoothstep(0, 3, np.arange(length, dtype=float))
        daya_mw[i0 : i0 + length] *= 1.0 - 0.12 * fade
        tegangan_v[i0 : i0 + length] -= 0.04 * fade

    # -------------------------------------------------------------------------
    # Siang panas ekstrem beberapa hari (trigger THI bahaya)
    # -------------------------------------------------------------------------
    for day in rng.choice(np.unique(day_of_run_full), size=min(8, n_days), replace=False):
        mask = day_of_run_full == day
        hf = hour_float[mask]
        hot = (hf >= 11.0) & (hf <= 15.5)
        idx = np.where(mask)[0][hot]
        if len(idx):
            suhu[idx] += rng.uniform(1.6, 2.9)
            kelembapan[idx] -= rng.uniform(3.0, 7.0)

    # -------------------------------------------------------------------------
    # Ringkasan & simpan
    # -------------------------------------------------------------------------
    suhu = np.clip(suhu, 22.5, 34.8)
    kelembapan = np.clip(kelembapan, 45.0, 99.4)
    tekanan = np.clip(tekanan, 1003.0, 1018.0)
    kecepatan_angin = np.clip(kecepatan_angin, 0.6, 28.0)
    tegangan_v = np.clip(tegangan_v, 3.15, 3.42)
    daya_mw = np.clip(daya_mw, 85.0, 720.0)
    arus_ma = daya_mw / tegangan_v

    epoch_ms = (timestamps - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")

    df = pd.DataFrame(
        {
            "timestamp": epoch_ms.astype(np.int64),
            "suhu": np.round(suhu, 2),
            "kelembapan": np.round(kelembapan, 2),
            "tekanan": np.round(tekanan, 2),
            "cahaya": np.round(cahaya, 1),
            "hujan": np.round(hujan, 4),
            "kecepatan_angin": np.round(kecepatan_angin, 2),
            "tegangan_v": np.round(tegangan_v, 3),
            "arus_ma": np.round(arus_ma, 2),
            "daya_mw": np.round(daya_mw, 1),
        }
    )

    df.to_csv(output_path, index=False)

    print(f"[OK] {len(df)} rekaman mikroklimat -> {output_path}")
    print(
        f"[INFO] cahaya=0: {100 * (df['cahaya'] == 0).mean():.2f}% | "
        f"hujan=0: {100 * (df['hujan'] == 0).mean():.2f}% | "
        f"jam hujan>0: {100 * (df['hujan'] > 0).mean():.2f}% | "
        f"lux>10k: {100 * (df['cahaya'] > 10000).mean():.2f}%"
    )
    print(
        f"[INFO] min | cahaya={df['cahaya'].min():.1f}Lux  hujan={df['hujan'].min():.4f}mm  "
        f"RH={df['kelembapan'].min():.1f}%  tegangan={df['tegangan_v'].min():.3f}V  daya={df['daya_mw'].min():.1f}mW"
    )
    print(f"[INFO] NaN total: {int(df.isna().sum().sum())}")
    print(f"[INFO] Sebaran regime: {pd.Series(regime_minute).value_counts().to_dict()}")
    return df


if __name__ == "__main__":
    generate_aws_dataset()
