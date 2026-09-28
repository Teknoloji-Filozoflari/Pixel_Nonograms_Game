# Faz 18–26 — Katana esintili oyun deneyimi

Tarih: 28 Eylül 2026

Amaç: Mevcut Python/PySide6 oyununu koruyarak keşif, okunabilirlik ve rahat
kontroller üzerine kurulu bir Nonogram deneyimi geliştirmek. Özgün görseller
ve simgeler kullanılacak. Web bulmaca deneyimi ile Android lonca genişlemesi
ayrı kapsamlar olarak ele alınacak.

Referanslar: https://nonograms-katana.com/play/#list ve https://nonograms-katana.com/

## Uygulama sırası

| Faz | Kapsam | Tamamlama ölçütü |
| --- | --- | --- |
| 18 | Gizli resim ve keşif | Başlanmamış/hatalı kayıt kartında soru işareti; devam eden kartta yalnız oyuncu hamleleri; tamamlananda resim. İsim tercihi kalıcı ve oyun başlığında da geçerli. Bitiş ekranında resim. |
| 19 | Tema ve görsel düzen | Ortak tema sistemi; açık kâğıt ve gece teması; özgün kenar süslemeleri; sade araç çubuğu; renk örnekli palet; okunabilir kontrast. |
| 20 | Hassas kontroller ve büyük tahtalar | Sürüklemede eksen kilidi ve hücre sayacı; tek hareketi tek geri alma; sabitlenebilir/genişletilebilir ipucu şeritleri; yazı boyutu; 50×50 yakınlaştırma/taşıma doğrulaması. |
| 21 | Yardım tercihleri ve güvenli işaretler | Otomatik X, otomatik sayı çizme ve hata uyarıları ayrı tercihler. Elle ve otomatik X kaynağı ayrılır; ipucu çizgisi kaldırılınca elle konmuş X kaybolmaz. Kalem/nokta notları ve belirgin deneme modu. |
| 22 | Öğretici ve açıklamalı ipucu | Küçük uygulamalı öğretici; renkli blok kuralları; üç aşamalı mantık açıklaması; ipucu tüketiminin açık gösterimi. Yardımlar kapalıyken bulmacalar oynanabilir. |
| 23 | Kütüphane ve sonuç akışı | Kaldığın yerden devam; boyut/tür koleksiyonları; tamamlanma sayacı; resim albümü; sonraki bulmaca; kısa resim açığa çıkma animasyonu ve azaltılmış hareket tercihi. |
| 24 | Bulmaca kalitesi ve editör | Tek çözüm ile mantıkla çözülebilirlik ayrı doğrulanır; çıkarım türüne göre zorluk; görselden üretimde gürültü denetimi; öğretici sıra; büyük bulmaca analizinde süre sınırı. |
| 25 | Ödül ve koleksiyon ilerlemesi | Mevcut envanter üzerine ilk tamamlama ödülleri, görevler ve kozmetik açma. Tekrar açma/geri alma ile aynı ödül çoğalmaz; yardımsız oyun mümkün kalır. |
| 26 | İsteğe bağlı lonca/yerleşim | Yerel kayıtlı görev, malzeme, mozaik ve yerleşim ilerlemesi; bulmaca ödülleriyle beslenir. Ayrı ve kapatılabilir bir ekran. Tam bir zindan/RPG ve çevrimiçi servisler bu planın kapsamında değil. |

Bağımlılıklar: 18 → 19 → 20 → 21 → 22 → 23 → 24 → 25 → 26.
Her faz mevcut kayıtları korur. Veri modeli değişiyorsa kayıt göçü ve eski
kayıtla açılış kontrolü gerekir. Faz 26, önceki fazların kullanılabilirliği
doğrulandıktan sonra geliştirilir.

## Faz 18 — Uygulama durumu

- [x] Önizleme varsayılan olarak çözümü göstermiyor.
- [x] Kütüphane girdisi kaydedilmiş oyuncu hücrelerini taşıyor; ikinci kayıt okuması yok.
- [x] Devam eden kartta doğru/yanlış ayrımı yapılmadan gerçek oyuncu boyamaları görünüyor.
- [x] Tamamlanmış kartlar resmi ve adını gösteriyor.
- [x] İsim gösterme tercihi kalıcı; kütüphane ve oyun başlığında uygulanıyor.
- [x] Bitiş penceresinde büyük resim gösteriliyor.
- [x] Keşif durumları, yeniden açma ve isim tercihi için regresyon testleri eklendi.
- [x] Otomatik testler ve arayüzsüz Qt ekran görüntüleriyle görsel doğrulama.

Animasyon Faz 23'te tamamlandı; açık tema Faz 19'da tamamlandı. Bu dosyadaki işaretler
uygulanan ve test edilen kodu belirtir. Faz 18–25 tamamlandı; sıradaki iş Faz 26. Faz 25 ayrıntıları: FAZ_25_ODUL_VE_GOREVLER.md. Faz 24 ayrıntıları: FAZ_24_BULMACA_KALITESI.md. Faz 23 ayrıntıları: FAZ_23_KUTUPHANE_VE_SONUC.md. Faz 22 ayrıntıları: FAZ_22_OGRETICI_VE_IPUCLARI.md. Faz 21 ayrıntıları: FAZ_21_YARDIM_VE_KALEM.md. Faz 20 ayrıntıları: FAZ_20_HASSAS_KONTROLLER.md. Faz 19 ayrıntıları: FAZ_19_TEMA_VE_GORSEL_DUZEN.md.

## Kontrol planı

Faz 18: `python -m pytest tests/test_collection_ui.py tests/test_board_ui.py
tests/test_puzzle_library.py`. Ardından ilgili sonuçlara göre tam regresyon
ve `python -m ruff check src tests`.

Görsel kontrol: yeni, yarım, tamamlanmış ve bozuk kayıt kartları; isim tercihini
değiştirip uygulamayı tekrar açma; renkli bulmaca önizlemesi; 820×640 minimum
pencerede bitiş ekranı. Mevcut kayıtlara yazmadan geçici test verisi kullanılmalı.

## Doğrulama sonucu — 28 Eylül 2026

- Faz 18 odaklı testler: 32 geçti.
- Tüm test paketi: 291 geçti (36,37 saniye).
- Ruff: tüm kontroller geçti.
- Qt ekran görüntülerinde gizli, devam eden ve tamamlanmış kartlar kontrol edildi.
- Bitiş penceresi 820×640 test penceresinde 360×472 boyutunda görüntülendi.
- Windows üzerinde bulunan mevcut .nono kayıt hatası düzeltildi: fsync için geçici dosya yazılabilir modda açılıyor. Dosya biçimi değişmedi.
- Test ortamı yalnızca proje içindeki .venv/runtime altında kuruldu.

Yerel çalıştırma (PowerShell):

```powershell
& '.venv/runtime/Scripts/python.exe' -m pixel_nonograms
& '.venv/runtime/Scripts/python.exe' -m pytest -q
& '.venv/runtime/Scripts/python.exe' -m ruff check src tests
```
