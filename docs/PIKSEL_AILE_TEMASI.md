# Piksel oyun ailesi — tema uyarlaması

Referans: [Piksel Atölyesi](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game),
özellikle `src/pixel_coloring/ui/theme.py` ve `collection_browser.py`.

Nonogram arayüzü, referansın antrasit zeminini (`#23272E`), panel rengini
(`#2D333B`), mercan ana eylemlerini (`#F06C3B`) ve yeşil seçim alanlarını
(`#315B51`) kullanır. Yalnızca karanlık tema sunulur.
Başlıklar, kartlar, kategori çubuğu, oyun araçları, editör ve
açılış logosu bu paletle uyumludur. Windows'ta Segoe UI kullanılır.

Görünen oyun adı **Piksel Nonogram** olarak düzenlendi. Kayıt dizini ve ayar
kimlikleri `Pixel Nonograms` olarak korundu; mevcut ilerlemeler aynı yerde okunur.
Eski aydınlık tema tercihleri karanlık temaya geçirilir.
Sağ üstte dil seçici, ayarlar ve çıkış bulunur. Türkçe, Azerice, İspanyolca,
Rusça ve İngilizce desteklenir. Dil tercihi `language` anahtarında saklanır;
değişiklik ekranı yeniden oluşturmadan uygulanır. Oyun hamleleri ve yakınlaştırma
korunur. Bulmaca oluşturma ve öğretici ana ekranın ayarlar penceresindedir.

Bulmaca tahtası beyazdır. Renkli bulmacaların gerçek renkleri ve
tamamlanmamış resimlerin gizlenmesi korunur. Kartlardaki ızgara yalnızca dekorasyondur.

Doğrulama: dil değişimi, tercih kalıcılığı, kayıt hatasında çıkışın engellenmesi,
beş dilde araç çubuğu ve çeviri değişkenleri otomatik testlerle kontrol edilir.
Gerçek Qt bileşenleriyle 820×640 boyutunda beş dil kontrol edildi.
Güncel görseller `dil_*.png` dosyalarındadır; `aile_*.png` önceki tasarımın kaydıdır.
