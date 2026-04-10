"""
Passo.com.tr - Otomatik Koltuk Seçici
Engelli kullanıcılar için boş koltuk çıktığında otomatik seçer.

Gereksinimler:
    pip install selenium webdriver-manager
"""

import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    from config import PASSO_EMAIL, PASSO_SIFRE
except ImportError:
    PASSO_EMAIL = None
    PASSO_SIFRE = None

# ─── AYARLAR ────────────────────────────────────────────────────────────────
URL = "https://www.passo.com.tr/tr/kombine/galatasaray-kombine-bilet/634746/koltuk-secim"

# Koltuk seçim tercihler (sırayla dener, ilk uygun bulduğunu seçer)
TERCIH_BLOK   = None   # Örnek: "K-KUZEY" — belirli bir blok istiyorsan yaz, yoksa None bırak
TERCIH_KAT    = None   # Örnek: "1"       — belirli bir kat istiyorsan yaz, yoksa None bırak
ENGELLI_FILTRE = True  # True: sadece engelli koltukları dene, False: herhangi boş koltuğu seç

TARAMA_ARALIGI = 2     # saniye — kaç saniyede bir koltukları kontrol etsin
MAKSIMUM_DENEME = 300  # toplam deneme sayısı (~600 saniye = 10 dakika)
# ────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Passo'da kullanılan olası boş koltuk CSS seçicileri
BOSH_KOLTUK_SELECTORS = [
    # SVG tabanlı koltuk haritası
    "g.seat.available",
    "g.seat:not(.sold):not(.disabled):not(.reserved)",
    "circle.seat.available",
    "rect.seat.available",
    # Div tabanlı koltuk haritası
    "div.seat.available",
    "div.seat.empty",
    "div.seat:not(.sold):not(.disabled):not(.reserved):not(.selected)",
    # Genel buton/link tabanlı
    "button.seat:not([disabled])",
    "a.seat.available",
    # Engelli koltukları
    "g.seat.handicapped:not(.sold)",
    "div.seat.handicapped:not(.sold)",
    "div.seat.wheelchair:not(.sold)",
]

# Engelli'ye özel ek filtre kelimeleri (element class/title/aria içinde arar)
ENGELLI_ANAHTAR_KELIMELER = [
    "handicap", "engelli", "wheelchair", "disabled-seat", "accessible"
]


def tarayici_baslat() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--lang=tr-TR")
    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver


def engelli_mi(element) -> bool:
    """Elementin engelli/erişilebilir koltuk olup olmadığını kontrol eder."""
    try:
        class_attr = (element.get_attribute("class") or "").lower()
        title_attr = (element.get_attribute("title") or "").lower()
        aria_label = (element.get_attribute("aria-label") or "").lower()
        combined   = class_attr + title_attr + aria_label
        return any(k in combined for k in ENGELLI_ANAHTAR_KELIMELER)
    except Exception:
        return False


def blok_uygun_mu(element) -> bool:
    """Tercih edilen blok/kat filtresi."""
    if not TERCIH_BLOK and not TERCIH_KAT:
        return True
    try:
        parent_text = element.find_element(By.XPATH, "./ancestor::*[@data-block or @data-section][1]")
        data_block  = (parent_text.get_attribute("data-block") or "").upper()
        data_kat    = (parent_text.get_attribute("data-floor") or "")
        if TERCIH_BLOK and TERCIH_BLOK.upper() not in data_block:
            return False
        if TERCIH_KAT and TERCIH_KAT not in data_kat:
            return False
    except Exception:
        pass  # Blok bilgisi bulunamazsa geçir
    return True


def bosh_koltuk_bul(driver) -> list:
    """Sayfadaki boş koltukları döndürür."""
    koltuklar = []
    for selector in BOSH_KOLTUK_SELECTORS:
        try:
            elemanlar = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elemanlar:
                if not el.is_displayed():
                    continue
                if ENGELLI_FILTRE and not engelli_mi(el):
                    continue
                if not blok_uygun_mu(el):
                    continue
                koltuklar.append(el)
            if koltuklar:
                log.info(f"Koltuk bulundu — selector: '{selector}', adet: {len(koltuklar)}")
                break
        except Exception:
            continue
    return koltuklar


def koltuğu_sec(driver, koltuk) -> bool:
    """Koltuğa tıklar; başarılı ise True döner."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", koltuk)
        time.sleep(0.3)
        koltuk.click()
        log.info("Koltuğa tıklandı!")
        return True
    except Exception as e:
        log.warning(f"Tıklama hatası: {e}")
        try:
            driver.execute_script("arguments[0].click();", koltuk)
            log.info("JavaScript ile tıklandı!")
            return True
        except Exception as e2:
            log.error(f"JS tıklama da başarısız: {e2}")
            return False


def onay_dialogunu_kapat(driver):
    """Passo'nun koltuk onay popup'ını otomatik kabul eder."""
    onay_selectors = [
        "button.confirm-button",
        "button.btn-primary",
        "button[data-action='confirm']",
        "//button[contains(text(),'Onayla')]",
        "//button[contains(text(),'Seç')]",
        "//button[contains(text(),'Devam')]",
    ]
    for sel in onay_selectors:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            log.info(f"Onay dialogu kapatıldı: {sel}")
            return
        except Exception:
            continue


def cloudflare_bekle(driver, max_sure=60):
    """Cloudflare engeli varsa kullanıcının manuel geçmesini bekler."""
    for _ in range(max_sure):
        title = driver.title.lower()
        if "attention required" in title or "just a moment" in title or "cloudflare" in title:
            time.sleep(1)
        else:
            return  # Cloudflare geçildi
    # Hala engelliyse kullanıcıya sor
    print("\n" + "="*60)
    print("  CLOUDFLARE DOGRULAMA GEREKIYOR!")
    print("  Acilan tarayicida 'I am human' kutusuna tikla.")
    print("  Tiklayinca bu ekrana don ve ENTER'a bas.")
    print("="*60)
    input()


def giris_yap(driver):
    """Passo.com.tr'ye otomatik giriş yapar."""
    if not PASSO_EMAIL or not PASSO_SIFRE:
        log.warning("config.py bulunamadı, giriş atlanıyor.")
        return False

    giris_url = "https://www.passo.com.tr/tr/giris"
    log.info(f"Giriş sayfası açılıyor: {giris_url}")
    driver.get(giris_url)

    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    # Cloudflare varsa kullanıcı manuel geçsin
    cloudflare_bekle(driver)

    time.sleep(2)  # Sayfa tam render olsun

    # Email alanını doldur
    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[id='email']",
        "input[placeholder*='mail']",
        "input[placeholder*='Mail']",
    ]
    email_girildi = False
    for sel in email_selectors:
        try:
            el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            el.clear()
            el.send_keys(PASSO_EMAIL)
            log.info(f"Email girildi ({sel})")
            email_girildi = True
            break
        except Exception:
            continue

    if not email_girildi:
        log.error("Email alanı bulunamadı!")
        return False

    # Şifre alanını doldur
    sifre_selectors = [
        "input[type='password']",
        "input[name='password']",
        "input[id='password']",
        "input[name='sifre']",
    ]
    sifre_girildi = False
    for sel in sifre_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.clear()
            el.send_keys(PASSO_SIFRE)
            log.info(f"Şifre girildi ({sel})")
            sifre_girildi = True
            break
        except Exception:
            continue

    if not sifre_girildi:
        log.error("Şifre alanı bulunamadı!")
        return False

    # Giriş butonuna tıkla
    giris_buton_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button.login-button",
        "button.btn-login",
        "//button[contains(text(),'Giriş')]",
        "//button[contains(text(),'Giris')]",
        "//input[@value='Giriş Yap']",
    ]
    for sel in giris_buton_selectors:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            log.info(f"Giriş butonuna tıklandı ({sel})")
            break
        except Exception:
            continue

    # Giriş sonrası yüklenmesini bekle
    time.sleep(3)

    # Giriş başarılı mı kontrol et
    current_url = driver.current_url
    if "giris" not in current_url.lower() and "login" not in current_url.lower():
        log.info("Giriş BASARILI!")
        return True
    else:
        # Hata mesajı var mı bak
        try:
            hata = driver.find_element(By.CSS_SELECTOR, ".error-message, .alert-danger, .login-error")
            log.error(f"Giriş hatası: {hata.text}")
        except Exception:
            log.warning("Giriş durumu belirsiz, devam ediliyor...")
        return True  # Yine de devam et


def ana_dongu(driver):
    # Önce giriş yap
    giris_basarili = giris_yap(driver)
    if not giris_basarili:
        log.warning("Giriş yapılamadı, sayfa yine de açılıyor...")

    log.info(f"Koltuk sayfası açılıyor: {URL}")
    driver.get(URL)

    # Sayfanın yüklenmesi için bekle
    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    # Koltuk sayfasında da Cloudflare olabilir
    cloudflare_bekle(driver)

    log.info("Sayfa yüklendi. Boş koltuk taranıyor...")
    log.info(
        f"Ayarlar — Engelli filtresi: {ENGELLI_FILTRE} | "
        f"Blok: {TERCIH_BLOK or 'Herhangi'} | "
        f"Kat: {TERCIH_KAT or 'Herhangi'}"
    )
    print("\n" + "="*60)
    print("  TARAMA BASLIYOR — tarayiciyi kapatma!")
    print("  Bos koltuk cikinca otomatik secilecek.")
    print("  Koltuk sectikten sonra bilgilerini girebilirsin.")
    print("="*60 + "\n")

    secildi = False
    for deneme in range(1, MAKSIMUM_DENEME + 1):
        log.info(f"Deneme {deneme}/{MAKSIMUM_DENEME} — koltuk aranıyor...")

        # Sayfayı yenile (bazı ticketing siteleri WebSocket yerine yenileme ister)
        if deneme > 1 and deneme % 30 == 0:
            log.info("Sayfa yenileniyor...")
            driver.refresh()
            time.sleep(3)

        koltuklar = bosh_koltuk_bul(driver)

        if koltuklar:
            koltuk = koltuklar[0]
            log.info(f"BULDUK! Toplam {len(koltuklar)} bos koltuk var. Ilki seciliyor...")
            basarili = koltuğu_sec(driver, koltuk)

            if basarili:
                time.sleep(1)
                onay_dialogunu_kapat(driver)
                secildi = True
                print("\n" + "="*60)
                print("  KOLTUK SECILDI!")
                print("  Simdi bilgilerini girebilirsin.")
                print("="*60 + "\n")
                break
            else:
                log.warning("Tıklama basarisiz, tekrar deneniyor...")

        time.sleep(TARAMA_ARALIGI)

    if not secildi:
        log.warning("Süre doldu, boş koltuk bulunamadı.")
        print("\nBos koltuk bulunamadi. Sayfayi yenileyip tekrar calistirabilirsin.")


def main():
    driver = tarayici_baslat()
    try:
        ana_dongu(driver)
        # Koltuk seçildikten sonra tarayıcıyı açık tut
        input("\nBilgilerini girdikten sonra ENTER'a bas ve tarayiciyi kapat...\n")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
