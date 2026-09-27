# `.nono` dosya biçimi — sürüm 1

`.nono`, tek bir bulmacanın tanımını taşıyan ZIP arşividir. Oyuncunun hücre işaretleri, süreleri,
istatistikleri ve diğer ilerleme verileri dosyada bulunmaz; mevcut `SaveManager` bunları puzzle
kimliğine bağlı olarak SQLite'ta saklar.

## Arşiv içeriği

Arşiv kökünde tam olarak şu dört dosya bulunur. Alt klasörler, başka dosyalar ve yinelenen adlar
kabul edilmez.

| Dosya | İçerik |
| --- | --- |
| `metadata.json` | UTF-8 JSON nesnesi; bulmacanın kimliği ve açıklayıcı alanları |
| `palette.json` | `#RRGGBB` dizgelerinden oluşan JSON dizisi |
| `solution.npy` | Şekli `(height, width)` olan C düzenli `uint8` NumPy dizisi |
| `preview.webp` | Tek karelik WebP görseli |

Çözümde `0` boş hücre, `1..N` ise `palette.json` içindeki bir tabanlı renk kimliğidir.
Satır ve sütun ipuçları çözümden hesaplanır; arşivde ayrıca tutulmaz.

## Metadata

Zorunlu alanlar: `format_version`, `id`, `title`, `author`, `width`, `height`,
`difficulty`, `tags`. İsteğe bağlı alanlar: `description`, `created_at`, `revision`,
`source`, `license`, `solution_sha256`, `reward_item_id`. Bilinmeyen veya yinelenen alanlar kabul edilmez.

`reward_item_id` varsa yalnızca sabit yardımcı öğe kimliklerinden biri olabilir:
`analysis_lens`, `logic_hint`, `error_check`, `row_scanner`, `column_scanner`,
`second_look`. Bu alan yalnızca ödül tanımıdır; kazanılmış miktar ve ödülün daha önce
alınıp alınmadığı SQLite'ta tutulur.

```json
{
  "format_version": 1,
  "id": "kapadokya-20",
  "title": "Kapadokya",
  "author": "Örnek Yazar",
  "description": "",
  "width": 20,
  "height": 20,
  "difficulty": "medium",
  "tags": ["manzara"],
  "created_at": "2026-01-02T03:04:00+00:00",
  "revision": 1,
  "source": "local",
  "license": "CC0",
  "solution_sha256": "<solution.npy dosyasının küçük harfli SHA-256 özeti>"
}
```

Zorluk değerleri mevcut modelde `easy`, `medium`, `hard`, `expert` olabilir.
`created_at` varsa saat dilimi içeren ISO 8601 tarih olmalıdır. `solution_sha256`
varsa ham `solution.npy` baytlarının SHA-256 özeti ile eşleşmelidir. Yazıcı bu iki
isteğe bağlı alanı da üretir.

## Sınırlar ve güvenlik

| Sınır | Değer |
| --- | ---: |
| ZIP dosyası | 2.500.000 bayt |
| Girdi sayısı | Tam 4 |
| Toplam açılmış içerik | 1.500.000 bayt |
| Metadata | 32.768 bayt |
| Palette | 8.192 bayt |
| Çözüm NPY | 65.536 bayt |
| Önizleme | 1.000.000 bayt; her kenar en çok 512 piksel |
| Sıkıştırma oranı | Girdi başına en çok 500:1 |
| Bulmaca | Her eksen 1–100 hücre |
| Palette | 1–255 benzersiz renk |

Okuyucu arşivi diske açmaz; yalnızca izin verilen adları, ZIP yapı ve boyutlarını,
şifreleme/simge bağlantısı durumunu, JSON alanlarını ve renkleri denetler. NPY başlığı
veri yüklenmeden önce denetlenir. `np.load` daima `allow_pickle=False` ve sınırlı başlık
boyutuyla kullanılır. Desteklenen NPY sürümleri 1.0 ve 2.0; ZIP sıkıştırmaları `STORED`
ve `DEFLATED` biçimleridir.

## Python API

```python
from pixel_nonograms.importer import read_puzzle, write_puzzle

write_puzzle(puzzle, "bulmaca.nono")
loaded = read_puzzle("bulmaca.nono")
```

`write_puzzle` var olan dosyanın üstüne varsayılan olarak yazmaz; `overwrite=True`
verilirse geçici dosyayı tamamladıktan sonra atomik olarak değiştirir. Önizleme
verilmezse çözümden üretilir. Geçersiz içerik `PuzzleFormatError` ile reddedilir.
