# Faz 25 — Ödüller, görevler ve profil rozetleri

## Oyuncuya görünen davranış

- Her farklı bulmacanın ilk tamamlanması bir kalıcı yıldız kazandırır. Yıldız sayısı farklı tamamlamaların sayısıdır; harcanan bir para birimi değildir.
- Önceden tanımlı eşya ödülleri aynı şekilde envantere eklenir. Her bulmacada eşya ödülü bulunması gerekmez.
- Süresiz görevler: ilk bulmaca, 3 farklı bulmaca, ilk renkli bulmaca, başlangıç üçlüsü, 10 farklı bulmaca.
- Görev ödülleri sırasıyla İlk Adım, Desen Kaşifi, Renk Ustası, Koleksiyoncu ve Mozaik Ustası profil rozetleridir.
- Başlangıç üçlüsü sabittir: İlk Adım, Elmas ve Kalp. Yeni bulmaca eklenmesi bu görevin hedefini değiştirmez. Kütüphanede ayrı koleksiyon filtresi ve rozet durumu bulunur.
- Görevler ve rozetler penceresinde sayaçlar, hedefler ve ödüller görünür. Açılmış rozet seçilebilir veya kaldırılabilir; seçim yeniden açılışta korunur ve kütüphanedeki profil özetinde gösterilir.
- Bitiş ekranı yeni yıldızı, yeni açılan rozetleri ve sıradaki hedefi gösterir. Yeniden çözmede yeni ödül bildirimi verilmez.
- Yardım kullanmak görevleri engellemez. Kozmetikler çözüm kurallarını değiştirmez. Bu fazın kozmetik kapsamı profil rozetleridir; ek tahta temaları ve hücre stilleri eklenmedi.

## Kayıt ve eski sürümler

SQLite şeması 6: `completions`, `milestone_claims`, `player_profile` tabloları.
Tamamlama geçmişi, görev açılımı, mevcut eşya ödülü ve oyun kaydı aynı işlemde yazılır.
Görev ve bulmaca kimliklerinin birincil anahtarları tekrar kazanmayı engeller.
Geri almak veya tamamlanmamış durum kaydetmek kazanılmış ilerlemeyi silmez.

Göç öncesi mevcut otomatik SQLite yedeği alınır. Eski tamamlanmış kayıtlar ve eşya ödülü geçmişi yıldızlara sayılır; eski eşya ödülleri tekrar verilmez. Eski kayıt biçiminde renk bilgisi olmadığından, kütüphane açılırken mevcut bulmacayla uyumlu tamamlanmış kayıtlar üzerinden renk bilgisi tamamlanır. Eksik veya uyumsuz eski bulmacalar için renk varsayılmaz.

## Doğrulama

- Geri alma, yeniden çözme ve yeniden açılışta tek ödül.
- Kilitli rozetin seçilememesi; seçili rozetin kalıcılığı.
- Tüm görev eşikleri, sabit başlangıç koleksiyonu, renkli kayıt uyumluluğu.
- İşlem hatasında oyun kaydı, yıldız, görev ve eşya ödülünün geri alınması.
- Sürüm 5 göçü, yedek ve eski envanterin korunması.
- Görev seçim arayüzü ve bitiş bildirimlerinin tekrarlanmaması.
- Arayüzsüz Qt ekran görüntüsü: kütüphane, görev penceresi, bitiş ekranı.
