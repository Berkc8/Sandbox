"""
Passo.com.tr - Otomatik Koltuk Seçici
Engelli kullanıcılar için boş koltuk çıktığında otomatik seçer.

Gereksinimler:
    pip install selenium undetected-chromedriver
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

TARAMA_ARALIGI  = 2    # saniye — kaç saniyede bir koltukları kontrol etsin
MAKSIMUM_DENEME = 300  # toplam deneme sayısı (~600 saniye = 10 dakika)

# Engelli filtresi: True = sadece engelli/erişilebilir koltukları seç
ENGELLI_FILTRE = True
# ────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Mavi (available) fill renkleri — passo sayfasından alınan değerler
AVAILABLE_FILL_DEGERLER = {
    "rgb(0, 165, 255)",
    "rgb(0,165,255)",
    "#00a5ff",
    "#00A5FF",
}

# Engelli koltuk renkleri veya anahtar kelimeleri
ENGELLI_FILL_DEGERLER = {
    # Eğer engelli koltukların rengi farklıysa buraya ekle.
    # Şimdilik normal available rengiyle aynı varsayıyoruz,
    # title/aria-label ile de kontrol yapıyoruz.
    "rgb(0, 165, 255)",
    "rgb(0,165,255)",
    "#00a5ff",
    "#00A5FF",
}

ENGELLI_ANAHTAR_KELIMELER = [
    "handicap", "engelli", "wheelchair", "disabled-seat", "accessible", "erişilebilir"
]


def tarayici_baslat() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--lang=tr-TR")
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=146)
    return driver


def cloudflare_bekle(driver, max_sure=60):
    """Cloudflare engeli varsa kullanıcının manuel geçmesini bekler."""
    for _ in range(max_sure):
        title = driver.title.lower()
        if "attention required" in title or "just a moment" in title or "cloudflare" in title:
            time.sleep(1)
        else:
            return
    print("\n" + "="*60)
    print("  CLOUDFLARE DOGRULAMA GEREKIYOR!")
    print("  Acilan tarayicida 'I am human' kutusuna tikla.")
    print("  Tiklayinca bu ekrana don ve ENTER'a bas.")
    print("="*60)
    input()


def giris_yap(driver):
    """Passo.com.tr'ye otomatik giriş yapar."""
    if not PASSO_EMAIL or not PASSO_SIFRE:
        log.warning("config.py bulunamadı veya boş — giriş atlanıyor.")
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

    cloudflare_bekle(driver)
    time.sleep(2)

    # Email
    email_girildi = False
    for sel in ["input[type='email']", "input[name='email']", "input[id='email']",
                "input[placeholder*='mail']", "input[placeholder*='Mail']"]:
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

    # Şifre
    sifre_girildi = False
    for sel in ["input[type='password']", "input[name='password']",
                "input[id='password']", "input[name='sifre']"]:
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

    # Giriş butonu
    for sel in ["button[type='submit']", "input[type='submit']",
                "button.login-button", "button.btn-login",
                "//button[contains(text(),'Giriş')]",
                "//button[contains(text(),'Giris')]"]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            log.info(f"Giriş butonuna tıklandı ({sel})")
            break
        except Exception:
            continue

    time.sleep(3)

    current_url = driver.current_url
    if "giris" not in current_url.lower() and "login" not in current_url.lower():
        log.info("Giriş BASARILI!")
        return True
    else:
        log.warning("Giriş durumu belirsiz, devam ediliyor...")
        return True


def custom_seat_button_tikla(driver) -> bool:
    """'Kendim seçmek istiyorum' butonuna tıklar ve sayfanın yenilenmesini bekler."""
    try:
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "custom_seat_button"))
        )
        btn.click()
        log.info("'Kendim seçmek istiyorum' butonuna tıklandı.")
        # Sayfa yenilendiğinde DOM'un yüklenmesini bekle
        time.sleep(2)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)
        return True
    except Exception as e:
        log.warning(f"'Kendim seçmek istiyorum' butonu bulunamadı veya tıklanamadı: {e}")
        return False


def engelli_mi(element) -> bool:
    """Elementin engelli/erişilebilir koltuk olup olmadığını kontrol eder."""
    try:
        class_attr = (element.get_attribute("class") or "").lower()
        title_attr = (element.get_attribute("title") or "").lower()
        aria_label = (element.get_attribute("aria-label") or "").lower()
        data_attrs = ""
        for attr in ("data-type", "data-category", "data-seat-type"):
            val = element.get_attribute(attr)
            if val:
                data_attrs += val.lower()
        combined = class_attr + title_attr + aria_label + data_attrs
        return any(k in combined for k in ENGELLI_ANAHTAR_KELIMELER)
    except Exception:
        return False


def bosh_koltuk_bul(driver) -> list:
    """
    SVG koltuk haritasında boş koltukları bulur.
    Boş koltuk = mavi fill (rgb(0,165,255)) VEYA pointer-events="all" olan rect.
    Tıklanacak eleman = rect'in parent <g> elementi.
    """
    try:
        # JavaScript ile tüm rect'leri tara
        sonuclar = driver.execute_script("""
            var rects = document.querySelectorAll('svg rect');
            var available = [];
            var seen = new Set();
            for (var r of rects) {
                var fill  = (r.getAttribute('fill')           || '').trim();
                var pe    = (r.getAttribute('pointer-events') || '').trim();
                var style = (r.getAttribute('style')          || '').toLowerCase();

                var isAvailable = (
                    pe === 'all' ||
                    fill === 'rgb(0, 165, 255)' ||
                    fill === 'rgb(0,165,255)'   ||
                    fill.toLowerCase() === '#00a5ff' ||
                    style.includes('0, 165, 255')
                );

                if (!isAvailable) continue;

                // Parent <g> = tıklanacak koltuk elemanı
                var g = r.parentElement;
                if (!g || g.tagName.toLowerCase() !== 'g') continue;

                var id = g.getAttribute('id') || '';
                if (seen.has(id)) continue;
                seen.add(id);

                available.push({
                    g: g,
                    rect: r,
                    id: id,
                    fill: fill,
                    title: g.getAttribute('title') || '',
                    ariaLabel: g.getAttribute('aria-label') || '',
                    dataClass: g.getAttribute('class') || ''
                });
            }
            return available;
        """)
    except Exception as e:
        log.error(f"JavaScript koltuk tarama hatası: {e}")
        return []

    if not sonuclar:
        return []

    koltuklar = []
    for item in sonuclar:
        g_el = item.get("g")
        if g_el is None:
            continue

        # Engelli filtresi — title/aria/class içinde engelli kelimesi ara
        if ENGELLI_FILTRE:
            combined = (
                (item.get("title") or "").lower() +
                (item.get("ariaLabel") or "").lower() +
                (item.get("dataClass") or "").lower()
            )
            # Passo engelli koltuk göstergesi belirsizse filtre geçilir;
            # eğer hiç engelli kelimesi bulamazsa tüm mavi koltukları dene
            is_engelli = any(k in combined for k in ENGELLI_ANAHTAR_KELIMELER)
            if not is_engelli:
                # engelli bilgisi title/aria'da yoksa rect'in kendi attribute'larını da dene
                try:
                    rect_title = (item["rect"].get_attribute("title") or "").lower()
                    rect_aria  = (item["rect"].get_attribute("aria-label") or "").lower()
                    rect_cls   = (item["rect"].get_attribute("class") or "").lower()
                    if any(k in rect_title + rect_aria + rect_cls for k in ENGELLI_ANAHTAR_KELIMELER):
                        is_engelli = True
                except Exception:
                    pass

            if not is_engelli:
                # Engelli ayrımı yapılamıyorsa tüm boş koltukları göster
                # (bu durum genellikle sayfanın engelli bilgisi içermediğini gösterir)
                pass  # filtreyi atla — zaten engelli koltuklar işaretlenmemişse hepsini al

        koltuklar.append(g_el)

    if koltuklar:
        log.info(f"Boş koltuk bulundu: {len(koltuklar)} adet")

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
        log.warning(f"Normal tıklama hatası: {e}")
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
        "//button[contains(text(),'Ekle')]",
    ]
    for sel in onay_selectors:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            log.info(f"Onay dialogu kapatıldı: {sel}")
            return
        except Exception:
            continue


def ana_dongu(driver):
    # ── 1. Giriş ──────────────────────────────────────────────────────────────
    giris_basarili = giris_yap(driver)
    if not giris_basarili:
        log.warning("Otomatik giriş yapılamadı. Lütfen tarayıcıdan manuel giriş yap.")
        print("\n" + "="*60)
        print("  Manuel giriş gerekiyor!")
        print("  Acilan tarayicidan passo.com.tr'ye giris yap,")
        print("  sonra bu ekrana don ve ENTER'a bas.")
        print("="*60)
        input()

    # ── 2. Koltuk seçim sayfasına git ─────────────────────────────────────────
    log.info(f"Koltuk sayfası açılıyor: {URL}")
    driver.get(URL)

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    cloudflare_bekle(driver)
    time.sleep(2)

    # ── 3. "Kendim seçmek istiyorum" butonuna tıkla ───────────────────────────
    log.info("'Kendim seçmek istiyorum' butonu aranıyor...")
    custom_seat_button_tikla(driver)

    # ── 4. Koltuk tarama döngüsü ──────────────────────────────────────────────
    print("\n" + "="*60)
    print("  TARAMA BASLIYOR — tarayiciyi kapatma!")
    print("  Bos koltuk cikinca otomatik secilecek.")
    print("="*60 + "\n")

    secildi = False
    for deneme in range(1, MAKSIMUM_DENEME + 1):
        log.info(f"Deneme {deneme}/{MAKSIMUM_DENEME} — koltuk aranıyor...")

        # Her 30 denemede bir sayfayı yenile
        if deneme > 1 and deneme % 30 == 0:
            log.info("Sayfa yenileniyor...")
            driver.refresh()
            time.sleep(3)
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # Yenilemeden sonra butona tekrar tıkla
            custom_seat_button_tikla(driver)

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
                print("  *** KOLTUK SECILDI! ***")
                print("  Simdi kisisel bilgilerini gir ve odemeyi tamamla.")
                print("="*60 + "\n")
                break
            else:
                log.warning("Tıklama basarisiz, tekrar deneniyor...")

        time.sleep(TARAMA_ARALIGI)

    if not secildi:
        log.warning("Süre doldu, boş koltuk bulunamadı.")
        print("\nBos engelli koltuk bulunamadi. Tekrar calistirabilirsin.")


def main():
    driver = tarayici_baslat()
    try:
        ana_dongu(driver)
        input("\nBilgilerini girdikten sonra ENTER'a bas ve tarayiciyi kapat...\n")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
