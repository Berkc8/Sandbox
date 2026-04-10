"""
Passo.com.tr - Termux/Android Koltuk Seçici
Tarayıcı gerektirmez. Sadece: pip install requests
"""

import requests
import time
import json
import re
import sys

# ─── BİLGİLER ───────────────────────────────────────────────────────────────
EMAIL  = "ardabas2001@gmail.com"
SIFRE  = "Arda-2001"
ETKINLIK_ID = "634746"   # URL'deki ID
URL_KOLTUK = "https://www.passo.com.tr/tr/kombine/galatasaray-kombine-bilet/634746/koltuk-secim"

ENGELLI_FILTRE  = True   # Sadece engelli koltukları seç
TARAMA_ARALIGI  = 3      # saniye
MAKSIMUM_DENEME = 600    # ~30 dakika
# ────────────────────────────────────────────────────────────────────────────

BASE = "https://www.passo.com.tr"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": BASE,
    "Origin": BASE,
})


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def giris_yap():
    log("Giriş yapılıyor...")

    # Önce ana sayfayı aç — CSRF token ve cookie al
    try:
        r = session.get(BASE + "/tr/giris", timeout=15)
        # CSRF token ara (varsa)
        csrf = None
        for pattern in [
            r'name=["\']_csrf["\'] value=["\']([^"\']+)["\']',
            r'name=["\']csrf_token["\'] value=["\']([^"\']+)["\']',
            r'"csrfToken"\s*:\s*"([^"]+)"',
            r'_token["\']:\s*["\']([^"\']+)',
        ]:
            m = re.search(pattern, r.text)
            if m:
                csrf = m.group(1)
                log(f"CSRF token bulundu: {csrf[:20]}...")
                break
    except Exception as e:
        log(f"Ön sayfa hatası (devam): {e}")

    # Olası giriş endpoint'leri — sırayla dener
    giris_endpoints = [
        "/api/auth/login",
        "/api/v1/auth/login",
        "/api/user/login",
        "/api/account/login",
        "/tr/api/giris",
        "/account/login",
    ]

    payload_base = {
        "email": EMAIL,
        "password": SIFRE,
        "username": EMAIL,
    }
    if csrf:
        payload_base["_csrf"] = csrf
        payload_base["_token"] = csrf

    for endpoint in giris_endpoints:
        try:
            log(f"  Deneniyor: {endpoint}")
            r = session.post(
                BASE + endpoint,
                json={"email": EMAIL, "password": SIFRE},
                timeout=15,
            )
            if r.status_code in (200, 201):
                try:
                    data = r.json()
                    if any(k in data for k in ("token", "access_token", "user", "success")):
                        # Bearer token varsa header'a ekle
                        token = data.get("token") or data.get("access_token")
                        if token:
                            session.headers["Authorization"] = f"Bearer {token}"
                            log(f"Token alındı, giriş BASARILI!")
                        else:
                            log("Giriş BASARILI (cookie tabanlı)!")
                        return True
                except Exception:
                    pass
                if "giris" not in r.url and "login" not in r.url:
                    log("Giriş BASARILI (yönlendirme)!")
                    return True
            elif r.status_code == 401:
                log("  Email/şifre hatalı!")
                return False
        except Exception as e:
            log(f"  Hata: {e}")
            continue

    # Form tabanlı giriş dene
    log("Form tabanlı giriş deneniyor...")
    try:
        data = {"email": EMAIL, "password": SIFRE}
        if csrf:
            data["_token"] = csrf
        r = session.post(BASE + "/tr/giris", data=data, timeout=15, allow_redirects=True)
        if "giris" not in r.url and "login" not in r.url:
            log("Form girişi BASARILI!")
            return True
        if "hata" in r.text.lower() or "error" in r.text.lower():
            log("Giriş başarısız — email/şifre kontrol et!")
            return False
    except Exception as e:
        log(f"Form giriş hatası: {e}")

    log("Giriş yapılamadı ama devam ediliyor (session denenecek)...")
    return False


def koltuk_sayfasini_parse_et(html):
    """HTML içinden koltuk verisi çekmeye çalışır."""
    koltuklar = []

    # JSON veri bloklarını ara
    json_patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'window\.__APP_STATE__\s*=\s*({.+?});',
        r'var seatData\s*=\s*({.+?});',
        r'"seats"\s*:\s*(\[.+?\])',
        r'"seatMap"\s*:\s*({.+?})',
    ]

    for pat in json_patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                log(f"JSON veri bulundu: {pat[:40]}")
                return data, koltuklar
            except Exception:
                continue

    return None, koltuklar


def koltuk_api_sorgula():
    """Koltuk durumu API'sini doğrudan sorgular."""
    api_endpoints = [
        f"/api/v1/events/{ETKINLIK_ID}/seats",
        f"/api/events/{ETKINLIK_ID}/seats",
        f"/api/v1/seatmap/{ETKINLIK_ID}",
        f"/api/seatmap/{ETKINLIK_ID}",
        f"/api/v1/kombine/{ETKINLIK_ID}/seats",
        f"/api/seats?eventId={ETKINLIK_ID}",
        f"/api/v1/seat-selection/{ETKINLIK_ID}",
    ]

    for endpoint in api_endpoints:
        try:
            r = session.get(BASE + endpoint, timeout=10)
            if r.status_code == 200:
                try:
                    data = r.json()
                    log(f"API yanıtı: {endpoint}")
                    return data
                except Exception:
                    pass
        except Exception:
            continue
    return None


def bosh_koltuk_bul_html():
    """Koltuk sayfasını HTML olarak çekip analiz eder."""
    try:
        r = session.get(URL_KOLTUK, timeout=15)
        html = r.text

        # API'ye istek yap
        api_data = koltuk_api_sorgula()
        if api_data:
            return api_yontemle_bul(api_data)

        # HTML parse et
        _, koltuklar = koltuk_sayfasini_parse_et(html)
        return koltuklar

    except Exception as e:
        log(f"Sayfa hatası: {e}")
        return []


def api_yontemle_bul(data):
    """API verisinden boş koltukları çıkarır."""
    koltuklar = []

    def tara(obj, yol=""):
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                tara(item, f"{yol}[{i}]")
        elif isinstance(obj, dict):
            durum = str(obj.get("status", obj.get("state", obj.get("availability", "")))).lower()
            is_engelli = any(
                str(obj.get(k, "")).lower() in ("true", "1", "engelli", "handicap", "wheelchair")
                for k in ("isHandicapped", "handicapped", "accessible", "engelli", "wheelchair")
            )
            is_bos = durum in ("available", "bos", "empty", "free", "open", "0")

            if is_bos:
                if not ENGELLI_FILTRE or is_engelli:
                    koltuklar.append(obj)
                    log(f"  Bos koltuk: {obj.get('id', obj.get('seatId', yol))}"
                        f"{' [ENGELLİ]' if is_engelli else ''}")

            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    tara(v, f"{yol}.{k}")

    tara(data)
    return koltuklar


def koltuğu_rezerve_et(koltuk):
    """Koltuğu sepete ekler / rezerve eder."""
    koltuk_id = (koltuk.get("id") or koltuk.get("seatId") or
                 koltuk.get("seat_id") or koltuk.get("seatCode"))

    if not koltuk_id:
        log("Koltuk ID bulunamadı!")
        return False

    log(f"Koltuk rezerve ediliyor: {koltuk_id}")

    rezerve_endpoints = [
        f"/api/v1/cart/add",
        f"/api/cart/add",
        f"/api/v1/seats/select",
        f"/api/seats/select",
        f"/api/v1/basket/add",
        f"/api/basket/add",
        f"/api/v1/kombine/{ETKINLIK_ID}/select",
    ]

    payload = {
        "seatId": koltuk_id,
        "seat_id": koltuk_id,
        "eventId": ETKINLIK_ID,
        "event_id": ETKINLIK_ID,
        "quantity": 1,
    }

    for endpoint in rezerve_endpoints:
        try:
            r = session.post(BASE + endpoint, json=payload, timeout=15)
            if r.status_code in (200, 201):
                try:
                    resp = r.json()
                    if resp.get("success") or resp.get("status") == "ok" or resp.get("cartId"):
                        log(f"REZERVASYON BASARILI! ({endpoint})")
                        return True
                except Exception:
                    pass
                if r.status_code == 200:
                    log(f"Rezervasyon yanıtı 200 ({endpoint}) — başarılı sayılıyor")
                    return True
        except Exception as e:
            log(f"  {endpoint} hatası: {e}")
            continue

    return False


def ana():
    print("=" * 50)
    print("  PASSO OTOMATIK KOLTUK SECICI")
    print("  Telefonu ekranda tut, kapatma!")
    print("=" * 50)
    print()

    giris_basarili = giris_yap()
    if not giris_basarili:
        print("\nGiris yapilamadi. Email/sifre kontrol et!")
        print("Devam etmek ister misin? (e/h): ", end="")
        cevap = input().strip().lower()
        if cevap != "e":
            sys.exit(1)

    print(f"\nKoltuk taramasi basliyor...")
    print(f"Engelli filtresi: {'ACIK' if ENGELLI_FILTRE else 'KAPALI'}")
    print(f"Her {TARAMA_ARALIGI} saniyede kontrol edilecek\n")

    for deneme in range(1, MAKSIMUM_DENEME + 1):
        log(f"Deneme {deneme}/{MAKSIMUM_DENEME} — aranıyor...")

        koltuklar = bosh_koltuk_bul_html()

        if koltuklar:
            log(f"*** {len(koltuklar)} BOS KOLTUK BULUNDU! ***")
            koltuk = koltuklar[0]
            basarili = koltuğu_rezerve_et(koltuk)

            if basarili:
                print()
                print("=" * 50)
                print("  *** KOLTUK SEPETE EKLENDI! ***")
                print()
                print("  Simdi telefon tarayicindan:")
                print("  passo.com.tr/tr/sepet")
                print("  adresine git ve odemeyi tamamla!")
                print("=" * 50)
                input("\nBittikten sonra ENTER'a bas...")
                return
            else:
                log("Rezervasyon basarisiz, tekrar deneniyor...")
        else:
            log("Bos koltuk yok, bekleniyor...")

        time.sleep(TARAMA_ARALIGI)

    print("\nSure doldu. Tekrar calistirabilirsin.")


if __name__ == "__main__":
    ana()
