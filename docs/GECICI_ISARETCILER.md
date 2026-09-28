# Geçici işaretçiler

Kalem düğmesinin yanındaki listeden nokta, A, B, C, ünlem, soru işareti,
yin yang, çizgi ve dört yön oku seçilebilir. Seçim kalem aracını etkinleştirir.

- Aynı sembole yeniden tıklama siler; farklı sembol mevcut notu değiştirir.
- Sürükleme ve yön kilidi desteklenir. Sürükleme tek hamlede geri alınır.
- Dolu veya X hücreleri üzerine not yazılmaz. Doldurma, X ve silgi notu kaldırır.
- Notlar çözüm, hata sayısı ve ipucu çıkarımlarında bilinmeyen hücre olarak kalır.
- Deneme Modunda kabul/iptal ile birlikte davranır.
- Notlar geçici çıkarımlardır ancak oyunu kapatıp açınca kaybolmaz.

Kayıt biçimi 3, SQLite şeması 7. Hücre başına dört bayt korunur; üçüncü bayt
0=not yok, 1=nokta, sonraki değerler sabit sembol sırasıdır. Eski 1 ve 2
biçimleri okunur. Şema göçü mevcut otomatik yedek mekanizmasını kullanır.

Testler: sembol kayıt döngüsü, eski sürüm göçü, geçersiz kodların reddi,
Deneme Modu, geri alma, tıklama/sürükleme ve araç seçimi.

## Sembol düğmeleri ve çift oklar

İşaretçi seçimi yazısız düğmelerle yapılır; açıklamalar araç ipucunda ve erişilebilir addadır.
Sol ve sağ veya yukarı ve aşağı okları aynı hücreye sırayla eklenebilir.
Mevcut çiftin bir yönünü tekrar seçip hücreye basmak yalnız o yönü kaldırır.
Çift oklar farklı renklerde çizilir; yön farkı yalnız renge bağlı değildir.
Kayıt sembol tablosuna iki birleşik ok kodu eklendi; eski kodların sırası korunur.
