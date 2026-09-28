# Bulmaca ve görev ödülleri

Her bulmacanın ilk tamamlaması en az bir yardımcı eşya verir. Özel eşya
belirtilmemişse varsayılan 1 Mantık İpucudur. Editör ve eski .nono dosyaları da
aynı varsayılanı kullanır; bulmaca parmak izi ödül alanını içermediğinden kayıt uyumu korunur.

Görevler mevcut rozete ek olarak şu paketleri verir:

| Görev | Eşya paketi |
|---|---|
| İlk tamamlama | 2 Mantık İpucu |
| 3 farklı bulmaca | 3 Mantık İpucu + 1 Hata Kontrolü |
| İlk renkli bulmaca | 2 Satır Tarayıcı + 2 Sütun Tarayıcı |
| Başlangıç üçlüsü | 4 Mantık İpucu + 2 Analiz Merceği |
| 10 farklı bulmaca | 5 Mantık İpucu + 2 Satır Tarayıcı + 2 Sütun Tarayıcı + 1 İkinci Bakış |

Paketler oyun kaydıyla aynı SQLite işleminde otomatik verilir. Şema 8,
mission_reward_claims tablosu ile her paket yalnızca bir kere verilir.
Önceden açılmış rozetlerin yeni paketleri ilk açılışta bir kez tamamlanır.
Kütüphanede bulunan, geçmişte tamamlanmış ancak eşya ödülü verilmemiş
bulmacaların eksik ödülleri bir kez verilir. Eski envanter korunur; şema göçü yedeklenir.
Bulmaca ve görev ödülleri üst üste kazanılır; tekrar çözme veya geri alma ile çoğalmaz.
