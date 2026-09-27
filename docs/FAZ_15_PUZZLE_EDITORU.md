# Faz 15 — Bulmaca Editörü

## Kullanım

Kütüphanedeki **Kendi Bulmacanı Oluştur** düğmesi editörü açar. Kalem seçili renkle
hücre boyar; silgi ve sağ tık hücreyi boşaltır; dolgu, tıklanan hücreyle aynı renkteki
bağlı alanı değiştirir. Izgara boyutu 1–100 arasında değiştirilebilir. Büyütme mevcut
çizimi korur, küçültme dışarıda kalan hücreleri siler. Önizleme yalnızca sonuç resmini
gösterir. Satır ve sütun ipuçları her çizim işleminden sonra güncellenir.

## Katmanlar ve kayıt

`core.editor.EditorDraft` Qt'den bağımsız geçici çözümü, paleti ve ipuçlarını tutar.
`ui.editor_canvas.EditorCanvas` tek bir QPainter yüzeyi kullanır. `services.editor`
taslağı `Puzzle` modeline çevirir ve mevcut solver ile benzersiz çözümü denetler.
Yalnızca **Tek çözüm** sonucunda yeni bir `.nono` dosyası atomik yazılır ve bulmaca
kütüphaneye eklenir. Oyuncu ilerlemesi dosyanın içine girmez; mevcut SQLite kayıt
sistemi kullanılır. Kullanıcı bulmacaları uygulama veri dizinindeki `puzzles/`
klasöründen bir sonraki açılışta tekrar yüklenir.

Editör **Birden fazla çözüm**, **Çözüm yok** ve doğrulama sınırına ulaşma sonuçlarını
ayrı gösterir. İpuçları doğrudan çizilen çözümden üretildiği için geçerli bir çizimin
ipuçları doğal olarak en az bir çözüme sahiptir; bu akışta **Çözüm yok** normalde
görülmez. Solver bu sonucu döndürürse yine kayıt yapılmaz.

## Sınırlar

- Boş çizim kaydedilemez.
- Solver doğrulaması 5 saniye ve 100.000 düğümle sınırlıdır. Sınır aşılırsa dosya
  kaydedilmez; çizim editörde kalır.
- Kaydedilmiş bir bulmaca editörde yeniden açılıp değiştirilemez. Her kayıt yeni
  kimliğe sahip bir bulmaca oluşturur.
