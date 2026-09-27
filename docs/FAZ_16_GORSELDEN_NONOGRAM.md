# Faz 16 — Görselden Nonogram

Editörde **Görselden Oluştur** ile yerel PNG, JPEG veya WEBP seçilir. Kullanıcı
10×10, 15×15, 20×20, 25×25 ya da 30×30 ızgara; siyah beyaz veya renkli mod;
doluluk eşiği ve renkli modda 2–8 renk belirler.

Dönüşüm sırası: dosyayı doğrula → EXIF yönünü uygula → alfa kanalını beyaz zemine
birleştir → en boy oranını koruyarak küçült ve beyaz boşlukla kareye yerleştir →
gri ton/eşik veya renk nicemlemesi → hücre ızgarası → satır/sütun ipuçları → solver
doğrulaması. Eşik değeri yükseldikçe daha açık pikseller de dolu sayılır.

Sonuç, editörde düzenlenebilir taslak olarak açılır. Solver sonucu hemen gösterilir;
tek çözüm şartı mevcut **Doğrula ve Kaydet** işleminde yeniden denetlenir.
Belirsiz bir görsel doğrudan kaydedilemez; oyuncu çizimi düzenleyebilir.

İçe aktarıcı Qt'den bağımsızdır. Kaynak dosya 20 MB ve 20 milyon piksel ile
sınırlıdır. Desteklenmeyen, bozuk veya eşik altında dolu hücresi olmayan görseller
editörde açıklayıcı hata verir ve mevcut taslağı değiştirmez.
