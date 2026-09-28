# Faz 22 — Uygulamalı öğretici ve açıklamalı ipuçları

Durum: Tamamlandı (28 Eylül 2026).

## Öğretici

Kütüphanedeki “Oynamayı öğren · Ücretsiz alıştırmalar” düğmesinden veya
oyun ekranında Ayarlar → Uygulamalı öğretici yolundan açılır.

Dört tekrar oynanabilir alıştırma:

1. Beş hücrelik dolu blok ve sürükleme.
2. İki ayrı blok arasında kesin boşu X ile belirtme.
3. Renkli bulmacada aynı renk blokların arasına boşluk koyma.
4. Farklı renk blokların boşluk bırakmadan bitişebilmesi.

Gerçek BoardWidget kontrolleri, doldurma/X/silme, renk seçimi, geri alma,
baştan deneme ve önceki adım kullanılır. Doğru işaretler tamamlanmadan
sonraki adım açılmaz. Boş hücreyi X ile işaretlemek ilgili alıştırmalarda
özellikle gerekir. Yanlış işaretler düzeltilebilir; hata cezası uygulanmaz.

Öğretici kendi geçici GameSession nesnelerini kullanır. Envanter tüketmez,
bulmaca ilerlemesine kayıt yazmaz ve ödül vermez. Asıl oyundan açılması
mevcut hamleleri korur. Dört adım bitince yalnız tutorial/completed tercihi
kaydedilir; tekrar açılış ilk alıştırmadan başlar. Zorunlu ilk açılış ekranı yoktur.

## İpuçları

Alıştırmalarda aynı mantık motorunun üç ücretsiz adımı sunulur:
çizgiyi bul → mantığı anla → kesin hücreyi gör. Hücre otomatik boyanmaz;
oyuncu hamleyi uygular. Tahta değişince eski açıklama zinciri temizlenir.

Asıl oyunda yardım paneli yeni yardımın bir eşya kullandığını, yararlı sonuç
yoksa harcanmadığını ve mevcut zincirin sonraki adımlarının ücretsiz olduğunu
açıkça yazar. Üçüncü adımda da aynı zinciri yeniden satın alma düğmesi
kapalıdır. Tahta değiştiğinde önceki harcamanın geri alınmadığı belirtilir.

## Doğrulama

- Tüm testler: 324 geçti (31,22 saniye).
- Ruff: bütün kontroller geçti.
- Dört alıştırma gerçek fare girdisiyle tamamlandı; yanlış işaret, X gereksinimi,
  renk geçişi, tekrar açma ve erken kapatma test edildi.
- Ücretsiz ipuçlarının hücreleri veya hint_count değerini değiştirmediği,
  hamle sonrasında zincirin temizlendiği doğrulandı.
- Asıl oyun durumu, geri alma geçmişi ve envanter korunması test edildi.
- Stok varken bile bitmiş ipucu zincirinin yeniden satın alınamaması test edildi.
- 680×540 öğretici ve renkli kural ekranı arayüzsüz Qt görüntüsüyle incelendi.

Sıradaki faz: 23 — kütüphane koleksiyonları, kaldığın yerden devam,
resim albümü, sonraki bulmaca ve bitiş animasyonu.
