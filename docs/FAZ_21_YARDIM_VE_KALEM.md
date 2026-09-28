# Faz 21 — Yardım tercihleri, güvenli X ve kalem notları

Durum: Tamamlandı (28 Eylül 2026).

## Oyuncu akışı

Ayarlar → Yardım tercihleri altında dört bağımsız seçenek var:

1. Tamamlanan çizgilerin boşlarını otomatik X yap (varsayılan kapalı).
2. Son sayıyı çizince kalan hücreleri X yap (varsayılan açık).
3. Kesin tamamlanan sayıları otomatik çiz (varsayılan kapalı).
4. Çizgide fazla dolu hücre uyarısı göster (varsayılan açık).

Otomatik sayı çizimi ipucu analizinden türetilir; elle yapılan çiziklerden
ayrıdır ve tek başına X üretmez. Bir sayı otomatik çizilmişse hücreler
artık onu doğrulamadığında görünüm güncellenir. Fazla dolu hücre uyarısı
cevabı açıklamaz; yalnız satır/sütundaki dolu hücre sayısını ipuçlarıyla
karşılaştırır. Yardımlar kapatıldığında temel oyun devam eder.

Araç çubuğundaki Kalem notu, bilinmeyen hücreye küçük halka koyar. Aynı
notun üzerinden başlayan sürükleme notları siler. Dolu/X hücrelerin üzerine
not yazılmaz. Not çözüm ve mantıksal ipucu hesabını etkilemez; boyama veya
X koyma notun yerini alır. Notlar geri alınır, kaydedilir ve yüklenir.

Deneme modunda açıklama bandı görünür ve geçici hücreler kesik çerçeveyle
ayrılır. Deneme notları da kabul/iptal akışına dahildir. Deneme sırasında
kayda yalnız deneme öncesi durum gider.

## X kaynakları ve kayıt geçişi

CellMark, note ve auto_sources alanlarını taşır. Otomatik X kaynakları
satır çizikleri (1), sütun çizikleri (2) ve mantıksal otomatik X (4) olarak
birleşebilir. Elle konan X'in kaynak değeri sıfırdır.

Bir ipucunu yeniden açmak yalnız o eksenin kaynağını kaldırır. Diğer kaynak
varsa X kalır. Otomatik X üzerine elle X koymak işareti elle konmuş sayar.
Geri alma/ileri alma hem işareti hem kaynak bilgisini birlikte korur.
Otomatik X yardımını kapatmak geçmiş işaretleri silmez.

Veritabanı şeması 4 → 5; hücre kayıt biçimi 1 → 2. Geçiş öncesi mevcut
Database altyapısı .bak yedeği alır. Progress tablosu işlem içinde yeniden
oluşturulur; eski satırlar aynı baytlarla korunur. Eski iki baytlık hücreler
okunabilir; sonraki kayıtta dört baytlık yeni biçim kullanılır. Eski X'lerin
kaynağı bilinmediği için elle konmuş sayılır. Favoriler, envanter ve ödül
tabloları değiştirilmez. .nono bulmaca biçimi değişmedi.

## Doğrulama

- Tam test paketi: 320 test geçti (30,98 saniye).
- Son notlu kenar hücresi görünürlüğü düzeltmesinden sonra tahta/tema testleri: 39 geçti.
- Ruff: bütün kontroller geçti.
- Elle X, kesişen kaynaklar, kaynağın elle devralınması, undo/redo, notların mantıktan bağımsızlığı, deneme kabul/iptal ve kayıt dönüşü test edildi.
- Gerçek şema 4 / hücre biçimi 1 kaydı yükseltilerek yedek, eski X korunması ve biçim 2'ye kayıt doğrulandı.
- Geçersiz not/kaynak verileri reddediliyor.
- Bağımsız yardım tercihleri, yeniden açılış, otomatik X geri alma, kalemle sürükleme ve deneme bandı test edildi.
- Açık/gece temalarında 820×640 renkli bulmaca, not ve deneme düğmeleri arayüzsüz Qt görüntüleriyle incelendi.

Sıradaki faz: 22 — uygulamalı öğretici ve açıklamalı ipucu akışı.
