# Faz 17 — Seviye boyutları ve zorluk planı

## Hedef düzen

Paketli oyun seviyeleri kare ızgara kullanır. Ara aralıklar, uçları da kapsayan
tam sayı boyutlarıdır: örneğin 15–20, 15×15, 16×16, …, 20×20 anlamına gelir.

| Zorluk | Paketli seviye boyutları |
| --- | --- |
| Kolay | 5×5, 10×10 |
| Orta | 15×15 ile 20×20 arası, her tam sayı boyut |
| Zor | 25×25 ile 30×30 arası, her tam sayı boyut |
| Uzman | 30×30 ile 50×50 arası, her tam sayı boyut |

30×30 hem Zor hem Uzman seviyesinde bulunabilir. Bu boyutta zorluk, yalnızca
hücre sayısıyla değil, çözüm için gereken çıkarım sayısı ve türüyle belirlenir.
21×21–24×24 boyutları bu paketli seviye dizisinde yer almaz. 5×5–10×10,
10×10–15×15 ve 20×20–25×25 aralarındaki diğer boyutlar da paketli katalogda
yer almaz. Kullanıcının kendi bulmacaları mevcut esnek boyut sınırını korur;
bu dağılım paketli oyun seviyeleri içindir.

## İlk içerik dağılımı

İlk katalogda her zorlukta **üç bulmaca** bulunur:

| Zorluk | Bulmacalar |
| --- | --- |
| Kolay | İlk Adım 5×5, Elmas 10×10, Kalp 10×10 |
| Orta | Renkli Uçurtma 15×15, Lale 17×17, Kapadokya 20×20 |
| Zor | Deniz Feneri 25×25, Yelkenli 27×27, Kale 30×30 |
| Uzman | Mozaik 30×30, Yıldız Haritası 40×40, Büyük Çiçek 50×50 |

Eski 12×12 Renkli Uçurtma, yeni paketli boyut dizisinde gösterilmez. Eski
oyuncu kaydı veritabanında korunur; yeni 15×15 sürümü ayrı kimlik kullanır.
İleride içerik eklendikçe aralıklardaki diğer tam sayı boyutları da temsil
edilebilir.

## Uygulama sırası

1. Paketli katalog için boyut/zorluk eşlemesini tek yerde tanımla. Katalog
   doğrulaması yeni paketli bulmacaları bu kurala göre denetlesin; kullanıcı
   yapımı veya içe aktarılan bulmacalara bu kısıt uygulanmasın.
2. Yeni bulmacaları ekle. Her biri için ipuçlarının tek çözüme götürdüğünü
   doğrula ve 30×30 ortak sınırında mantıksal zorluk incelemesi yap.
3. Kütüphanedeki boyut filtresinin mevcut bulmacalardan türetilen seçeneklerini
   koru. Gerekirse çok sayıdaki seçenek için boyut aralığı filtresi ekle;
   zorluk ve boyut filtreleri birlikte çalışsın.
4. Görselden oluşturma akışı şu anda yalnızca 10, 15, 20, 25 ve 30 karelerini
   sunuyor. Paketli içerik üretiminde bu akış kullanılacaksa 5–50 içindeki
   hedef boyutları destekle ve büyük ızgaralarda dönüştürme/çözme süresini ölç.
5. Katalog dağılımı, sınır boyutları, 30×30 çift sınıfı, tek çözüm ve eski
   kayıtların korunması için otomatik kontroller ekle. 50×50 için çizim,
   kaydırma, yakınlaştırma ve ipucu okunabilirliğini masaüstünde denetle.

## Tamamlama ölçütü

Paketli katalogda ilk etapta her zorlukta üç bulmaca bulunur; boyut ve zorluk
etiketleri tabloyla uyumludur; tüm bulmacalar tek çözümlüdür; mevcut oyuncu
ilerlemesi kaybolmaz; 50×50 ızgara yakınlaştırma ve taşıma ile oynanabilir.
