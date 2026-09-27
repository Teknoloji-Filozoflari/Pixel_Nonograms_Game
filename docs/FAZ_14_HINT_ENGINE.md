# FAZ 14 — Öğretici ipuçları

Mantık İpucu, solver'ın bulduğu **tek bir kesin hamle** için üç aşamalı bir
açıklama oluşturur. Çözüm ızgarasından rastgele hücre açılmaz.

1. Bakılacak satır/sütun gösterilir ve tahtada vurgulanır.
2. Clue kısıtlarıyla gerekçe açıklanır. Blokların olası başlangıçları aynı
   hücreleri kaplıyorsa blok uzunluğu, başlangıç sayısı ve henüz işaretlenmemiş
   ortak hücre sayısı belirtilir. Tamamlanmış blok, imkânsız konum ve satır/sütun
   kesişimi için ayrı açıklamalar vardır.
3. Kesin hücrenin koordinatı ve işareti gösterilir; hücre tahtada çerçevelenir.

İpucu öğesi ilk aşama açılırken bir kez harcanır ve `hint_count` bir artar.
İkinci ve üçüncü aşama yeni öğe harcamaz. Mantıksal hamle yoksa veya mevcut
işaretler çelişiyorsa öğe harcanmaz. İpucu planı açıldığı tahta durumuna bağlıdır;
tahta değişirse zincir kapanır. Plan yalnızca aktif oyun ekranında tutulur,
uygulama yeniden açıldığında devam ettirilmez.

`create_hint_plan()` ve `get_hint()` Qt'den bağımsızdır. Hesaplama zaman sınırı
vardır; sınır aşılırsa tahmini hücre döndürülmez.
