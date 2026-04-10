"""
Passo.com.tr - DEBUG scripti
Ne döndürdüğünü görmek için çalıştır, çıktıyı bana gönder.
"""

import requests
import json
import re

EMAIL = "ardabas2001@gmail.com"
SIFRE = "Arda-2001"
BASE  = "https://www.passo.com.tr"
URL_KOLTUK = "https://www.passo.com.tr/tr/kombine/galatasaray-kombine-bilet/634746/koltuk-secim"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
})

def sep():
    print("-" * 60)

# ── 1. Giriş sayfası ────────────────────────────────────────────
print("\n=== 1. GIRIS SAYFASI ===")
r = session.get(BASE + "/tr/giris", timeout=15)
print(f"Status: {r.status_code}")
print(f"URL: {r.url}")
print(f"Cookies: {dict(session.cookies)}")
# Script taglarını bul
scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', r.text)
print(f"Script dosyaları ({len(scripts)}):")
for s in scripts[:10]:
    print(f"  {s}")
# API URL ipuçları ara
api_hints = re.findall(r'["\'](/api/[^"\']+)["\']', r.text)
print(f"\nAPI URL ipuçları ({len(api_hints)}):")
for a in list(set(api_hints))[:20]:
    print(f"  {a}")
sep()

# ── 2. Auth endpoint dene ───────────────────────────────────────
print("\n=== 2. AUTH DENEMESI ===")
for endpoint, payload in [
    ("/api/auth/login",    {"email": EMAIL, "password": SIFRE}),
    ("/api/v2/auth/login", {"email": EMAIL, "password": SIFRE}),
    ("/api/users/login",   {"email": EMAIL, "password": SIFRE}),
]:
    try:
        r2 = session.post(BASE + endpoint, json=payload, timeout=10)
        print(f"{endpoint} → {r2.status_code}")
        print(f"  Yanıt: {r2.text[:300]}")
        sep()
    except Exception as e:
        print(f"{endpoint} → HATA: {e}")

# ── 3. Koltuk sayfası ───────────────────────────────────────────
print("\n=== 3. KOLTUK SAYFASI ===")
r3 = session.get(URL_KOLTUK, timeout=15)
print(f"Status: {r3.status_code}")
print(f"URL: {r3.url}")
print(f"\nİlk 1000 karakter:")
print(r3.text[:1000])
sep()
# API URL ipuçları
api2 = re.findall(r'["\'](/api/[^"\']+)["\']', r3.text)
print(f"\nAPI URL ipuçları ({len(api2)}):")
for a in list(set(api2))[:30]:
    print(f"  {a}")
# Koltuk ile ilgili kelimeler
for keyword in ["seat", "koltuk", "available", "handicap", "engelli"]:
    count = r3.text.lower().count(keyword)
    if count:
        print(f"  '{keyword}' kelimesi: {count} kez geçiyor")

# ── 4. Olası API endpoint'leri ──────────────────────────────────
print("\n=== 4. API ENDPOINT TARAMASI ===")
test_urls = [
    f"/api/v1/kombine/{634746}",
    f"/api/v1/events/{634746}/seats",
    f"/api/v1/seat-map/{634746}",
    f"/api/kombine/{634746}/seats",
    f"/api/v2/events/{634746}/seats",
]
for url in test_urls:
    try:
        r4 = session.get(BASE + url, timeout=8)
        print(f"{url} → {r4.status_code} | {r4.text[:200]}")
        sep()
    except Exception as e:
        print(f"{url} → HATA: {e}")

print("\n=== DEBUG BITTI ===")
print("Bu ciktinin tamami bana gonder!")
