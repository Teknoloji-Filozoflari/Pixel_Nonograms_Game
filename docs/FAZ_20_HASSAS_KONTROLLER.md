# Faz 20 — Hassas kontroller ve büyük tahtalar

Durum: Tamamlandı (28 Eylül 2026).

## Kontroller

- Sürükleme ilk hücre geçişinde baskın yatay/dikey eksene kilitlenir; eşit çapraz harekette yatay eksen seçilir.
- Ayarlar menüsündeki sürükleme kilidi kapatılırsa serbest çizim kullanılabilir.
- Başlıktaki sayaç, bir sürüklemede geçilen farklı hücreleri sayar. Aynı hücreye geri dönmek sayacı artırmaz; sayaç değiştirilen hücre sayısı değildir.
- Boyama, X ve silme aynı sürükleme altyapısını kullanır. Sürükleme tek geri alma işlemi olarak kaydedilir.
- Kilitli çizim dışarı çıkıp geri girince ilk ekseni ve hücre sürekliliğini korur. Tahta dışında başlayan tıklama çizim başlatmaz.
- Fare bırakma konumu da işlenir. Odak kaybı/kayıt öncesinde çizim tamamlanır ve sayaç temizlenir.
- Çizim sürerken fare tekerleği kamerayı oynatmaz.

## Görünüm ayarları

Oyun ekranının sağ üstündeki Ayarlar menüsünde:

- İpucu şeritlerini sabitle: kaydırırken sayılar görünür kenarda tutulur; kapatıldığında tahtayla kayar.
- Geniş ipucu şeritleri: daha fazla sayı için alan ayırır; küçük pencerede ızgaraya yer bırakacak şekilde sınırlandırılır.
- İpucu yazı boyutu: küçük/normal/büyük/çok büyük (12/15/18/22 piksel üst sınırı).
- İpuçlarını okuyacak kadar yakınlaştır: seçilen yazı boyutuna yetecek hücre boyutuna geçer.

Yazı boyutu değiştirilince okunabilir yakınlaştırma uygulanır. Ekrana sığdır
seçeneği tüm tahtayı tekrar gösterir; küçük hücrelerde sayıların üst üste
binmemesi için yazı küçülür. Uzun ipucu dizileri şerit üzerinde tekerlekle
kaydırılabilir; aktif satır/sütunun bütün sayıları alt bilgi alanında görünür.
Ayarlar controls/axis_lock ve view/* altında kalıcıdır; bulmaca kayıt biçimi değişmez.

## Doğrulama

- Tam paket: 305 test geçti (29,19 saniye).
- Son dışarı çıkma/geri giriş düzeltmesinden sonra tahta ve tema paketi: 37 test geçti.
- Ruff: bütün kontroller geçti.
- Yatay/dikey kayma, sol/sağ tık, benzersiz hücre sayacı, tek geri alma/ileri alma, serbest çizim, bırakma konumu, dışarıdan tıklama, kalıcı ayarlar ve 50×50 ipucu hit testi denetlendi.
- 50×50 tahtada sabitleme, geniş şeritler, okunabilir yakınlaştırma ve ekrana sığdırma test edildi.
- 820×640 boyutunda, çok büyük yazılı 50×50 tahta arayüzsüz Qt ekran görüntüsü üzerinden incelendi; fiziksel ekranda etkileşimli oturum yapılmadı.

Sıradaki faz: 21 — yardım tercihleri, elle/otomatik X kaynağının ayrılması,
kalem notları ve deneme modunun geliştirilmesi.
