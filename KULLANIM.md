# Otomatik Koltuk Seçici — Kullanım Kılavuzu

## 1. Kurulum

```bash
pip install -r requirements.txt
```

## 2. Ayarlar (seat_selector.py dosyasını aç)

| Ayar | Açıklama | Varsayılan |
|------|----------|------------|
| `ENGELLI_FILTRE` | Sadece engelli koltuklarını ara | `True` |
| `TERCIH_BLOK` | Belirli bir blok (ör. `"K-KUZEY"`) | `None` (hepsi) |
| `TERCIH_KAT` | Belirli bir kat numarası | `None` (hepsi) |
| `TARAMA_ARALIGI` | Kaç saniyede bir kontrol etsin | `2` |
| `MAKSIMUM_DENEME` | Toplam deneme (~10 dk) | `300` |

## 3. Çalıştırma

```bash
python seat_selector.py
```

## 4. Ne Olur?

1. Chrome otomatik açılır ve passo.com.tr sayfasına gider
2. Her 2 saniyede bir boş koltuk arar
3. Boş koltuk bulunca **otomatik tıklar ve seçer**
4. Terminalde `KOLTUK SECILDI!` mesajı çıkar
5. Sen bilgilerini girersin, ödemeyi yaparsın
6. ENTER'a basınca tarayıcı kapanır

## 5. Sorun Giderme

**"Koltuk bulunamadı" diyorsa:**
- `ENGELLI_FILTRE = False` yaparak tüm boş koltuklara genişlet
- Sayfayı manuel açıp koltuk elementinin class adını bak (F12 → Inspector)
- `seat_selector.py` içindeki `BOSH_KOLTUK_SELECTORS` listesine o class'ı ekle

**Site bot engeli koyduysa:**
- Tarayıcıyı manuel aç, oturum aç, sonra script'i çalıştır
- `TARAMA_ARALIGI` değerini 3-5 saniyeye çıkar
