# Sade kütüphane ve açılış

Kütüphanede yalnız Tümü / Kolay / Orta / Uzman filtreleri bulunur. Zor bulmacalar
Tümü listesinde görünmeye devam eder. Boyut, renk, durum, sıralama, koleksiyon,
albüm ve isim tercihi kontrolleri ile bunların UI kodu kaldırıldı.
Bulmaca isimleri kartlarda ve oyun başlığında sürekli görünür.
Tema seçimi 145 piksel minimum genişlikte, Aydınlık / Karanlık etiketiyle görünür.

Açılış ekranı uygulama simgesinden önce gösterilir. Editör ve oyun ekranı modülleri
ilk açılış yerine ilgili ekrana girildiğinde yüklenir. Servis dışa aktarımları da
isteğe bağlı yüklenir; görsel içe aktarımı açılışta Pillow yüklemez.
Kütüphane filtreleme aynı kayıtları ikinci kez okumaz.

Yerel arayüzsüz ölçüm: önce splash 1,522 s / ana pencere 3,042 s;
sonra splash 1,393 s / ana pencere 2,383 s. Bu değerler birer yerel ölçümdür;
ilk DLL yüklemesi ve disk önbelleği süreyi etkiler. Yükleme sırasında gereksiz
bekleme veya yapay splash süresi eklenmedi.
