# FAZ 12 — Yardımcı envanter

Envanter bulmaca çözümüne bağlı, isteğe bağlı bir yardım sistemidir. Para, enerji,
malzeme, kaynak üretimi, rastgele ödül veya satın alma içermez. Her bulmacanın
`reward_item_id` alanı boş olabilir. Doluysa yalnızca ilk tamamlanmasında bir adet
belirtilen yardımcı öğeyi verir.

Mevcut altı yerleşik bulmacanın her biri farklı bir yardımcı öğeyi ilk tamamlamada
verir; sonraki tamamlamalar stok artırmaz.

## Öğeler

| Kimlik | Oyuncuya gösterilen bilgi |
| --- | --- |
| `analysis_lens` | Seçilen satır veya sütunun durumu ve olası yerleşim sayısı |
| `logic_hint` | İpuçlarından çıkan bir sonraki kesin hamle ve açıklaması |
| `error_check` | Kayıtlı çözümle uyuşmayan ilk oyuncu işareti |
| `row_scanner` | Seçilen satırdaki en çok üç kesin, işaretlenmemiş hücre |
| `column_scanner` | Seçilen sütundaki en çok üç kesin, işaretlenmemiş hücre |
| `second_look` | İpuçlarıyla çelişen ilk satır veya sütun |

Çizgi tarayıcıları ve mantık ipucu çözüm ızgarasını okumaz; clue kısıtlarını
kullanır. Hata Kontrolü, gerçekten yanlış bir işareti göstermek için kayıtlı
çözümle karşılaştırır. Öğeler hücreleri otomatik değiştirmez. Sonuç yoksa öğe
harcanmaz. Deneme Modunda ve tamamlanmış bulmacada kullanım kapalıdır.

## Kalıcılık ve tek seferlik ödül

SQLite şema sürümü 3, `inventory` ve `reward_claims` tablolarını ekler. Tamamlama
kaydı, ödül hakkı ve stok artışı tek işlemde gerçekleşir. `reward_claims.puzzle_id`
birincil anahtardır; geri alma, yeniden çözme veya uygulamayı yeniden başlatma
ikinci ödül vermez. Önceden tamamlanmış bir bulmacaya sonradan ödül tanımlanması
geriye dönük ödül üretmez. Yardımcı kullanımı, stok eksiltme ve güncel ipucu sayısı
da tek SQLite işleminde kaydedilir.

`.nono` dosyası yalnızca ödül tanımını taşıyabilir. Oyuncunun stokları, kullanım
sayıları ve kazanılmış ödül kayıtları yalnızca yerel SQLite veritabanındadır.
