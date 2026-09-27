# Faz 0 — Nonogram masaüstü oyunu teknik tasarımı

Durum: tasarım önerisi. Bu belge uygulama kodu içermez. İç paket adı olarak `pixel_nonograms` kullanılır; görünen ürün adı ayrıca belirlenecektir. İnceleme, referans deponun `98ee0e0d5ee6ad056a090ee16716b38fe7bf74c4` commit'ine dayanır. Çalışma alanında başlangıçta uygulama dosyası yoktur; bu nedenle mevcut çalışan kod değiştirilmeyecektir.

## 1. Ürün sınırı ve temel kurallar

Oyun döngüsü bulmaca seçme, çözme, tamamlama ve yerel istatistik kaydetmeden oluşur. Envanter yalnızca isteğe bağlı çözüm yardımı sağlar. Hesap, ağ, reklam, telemetri, enerji, bekleme süresi, günlük görev, üretim ve ekonomi yoktur. Bütün oynanış çevrimdışı çalışır. Türkçe varsayılan dildir; içerik kimlikleri ve kayıt verisi çevrilen metinlerden bağımsızdır.

İlk bulmaca modeli tek renkli Nonogram'dır. Renkli Nonogram ayrı bir format ve kural sürümü gerektirir; tek renkli kurallara sessizce eklenmez. Bulmaca boyutu için başlangıç üst sınırı 100 × 100 hücredir. Sınır, çözücü ve çizim ölçümleriyle sonraki fazlarda gözden geçirilir. İçe aktarılan resimler Nonogram'a dönüştürülürken özgün resim kullanıcıda kalır; oyun yalnızca kendi bulmaca kopyasını saklar.

## 2. Referans depo incelemesi

| Alan | Gözlenen yapı | Yeni oyuna etkisi |
|---|---|---|
| Core | `Painting` salt okunur hedef renk haritası, değişebilir boyama maskesi ve sayaçları tutuyor. `PaintingEngine` doğru renk dışında boyamıyor; bağlı bölge doldurma ve komut geçmişi içeriyor. `GameSession` seçim ve revizyonları tutuyor, geçen süreyi fiilen `0` döndürüyor. | Hedef maskenin ve oturum ayrımının fikri yararlı. Nonogram için bilinmeyen/dolu/boş durumları, yanlış işaretleme ve ipucu provenance'ı yeni modellenmeli. Boyama motoru taşınmamalı. |
| Canvas ve Camera | Tek `QWidget` görünür karoları `QPainter` ile çiziyor; kamera yakınlaştırma, taşıma, görünür hücre ve koordinat dönüşümünü yönetiyor. Fare sürüklemesindeki boşluklar interpolasyonla kapatılıyor. | Tek widget ve görünür alan çizimi korunabilecek mimari örnektir. İpuçları için sabit satır/sütun başlıkları, dondurulmuş köşe ve klavye odağı ayrıca tasarlanmalı. |
| TileCache | 256 × 256 hücre karoları `QImage` olarak 64 MiB varsayılan LRU önbellekte. Değişen hücrelerin karosu geçersiz kılınıyor. | Nonogram ızgarası küçük olduğundan ilk aşamada doğrudan görünür hücre çizimi daha sade. Profiling gerektirirse sabit arayüz arkasında karo önbelleği eklenir. Referansın renk indeksli karosu doğrudan kullanılmaz. |
| Persistence | SQLite `paintings`, `progress`, `settings`, `statistics`, `achievements` tablolarını kullanıyor; `user_version=1`, WAL ve FK açık. Açılışta `statistics`/`achievements` temizleniyor, ilerlemenin süre alanları sıfırlanıyor. | Şema ve geçişler baştan sürümlenmeli; istatistikler açılışta silinmemeli. Bulmaca tanımı ile oyuncu ilerlemesi ayrı tutulmalı. Referans SQLite dosyasıyla otomatik ortak kullanım yapılmamalı. |
| SaveManager | Ana iş parçacığında `packbits` anlık görüntüsü alıyor; tek işçili kuyruk yazmaları sırayla yapıyor. `flush` hatayı iletiyor. Arayüz süreli kayıt ve çıkışta `flush` çağırıyor. | Anlık görüntü + sıralı yazıcı uygun. Yeni sürümde revizyon, oturum kimliği, kayıt hatası ve tamamlama/ödül işlemi tek transaction olarak ele alınmalı. |
| Services | `samples` paketli resimleri kullanıcı veri alanına kuruyor; katalog ile eşleştiriyor. `bundle_update` değişen resimlerde yedek ve ilerleme dönüşümü uyguluyor. `library` içe aktarılan oyun kopyasını siliyor. | Paketli bulmacalar okunur kaynak olarak kalabilir; DB yalnızca katalog/progress indeksini tutar. Bulmaca revizyonu ilerleme uyumluluğunu açıkça belirlemeli. |
| Importer | Pillow ile EXIF yönü, alfa ve renk azaltma yapıyor. `.pcolor` ZIP: metadata, palette, NumPy hedef, WebP önizleme. Okuyucu boyut limitleri ve `allow_pickle=False` kullanıyor. | Görsel içe aktarma ikili maskeye ve çözülebilirlik kontrolüne dönüşmeli. `.pcolor` biçimi kullanılmaz; yeni `.nono` biçimi sürümlü ve güvenli okunmalı. |
| UI ve tema | `QStackedWidget` ile koleksiyon/oyun/ayar geçişi; `MainWindow` içinde DB, işçi, otomatik kayıt ve navigasyon birikmiş. `theme.py` tek büyük Fusion QSS, `i18n.py` JSON çeviri ve Qt düğme çevirileri kullanıyor. | Ekran bileşenleri ayrılır; tema tokenları ve erişilebilir kontrast tanımlanır. Türkçe varsayılan, dil değişiminde sabit kimlikler kullanılır. |
| Paketleme | Python 3.13+, PySide6 Essentials, NumPy, Pillow; PyInstaller tabanlı AppImage/DEB betikleri ve AppImage smoke testi var. Windows paketi yok. | Ayrı uygulama kimliği, veri dizini ve paket adları gerekir. CI'nin eski `python-package.yml` dosyası 3.9–3.11/flake8 kullanıyor; yeni projede Python 3.13/pytest/ruff ile uyumlu tek kalite kapısı kurulmalı. |
| Testler | İki çekirdek testi doğru/yanlış boyamayı, iki koleksiyon testi 536 paketli dosya ve katalog tutarlılığını kontrol ediyor. | Yeni çekirdeğin sınır durumları, çözücü, kayıt geri yükleme, geçiş ve Qt etkileşimleri için kapsam artırılmalı. Referans testleri Nonogram doğrulaması yerine geçmez. |

Referans kaynaklar: [depo](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game), [mimari belgesi](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game/blob/98ee0e0d5ee6ad056a090ee16716b38fe7bf74c4/docs/ARCHITECTURE.md), [veritabanı](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game/blob/98ee0e0d5ee6ad056a090ee16716b38fe7bf74c4/src/pixel_coloring/persistence/database.py), [Canvas](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game/blob/98ee0e0d5ee6ad056a090ee16716b38fe7bf74c4/src/pixel_coloring/rendering/canvas.py), [paketleme](https://github.com/Teknoloji-Filozoflari/Pixel_Color_Game/tree/98ee0e0d5ee6ad056a090ee16716b38fe7bf74c4/packaging).

[Nonograms Katana'nın yayımladığı özellik listesinde](https://nonograms-katana.com/) boş hücre işaretleri, geri alma, ipuçları, sayıların otomatik işaretlenmesi, satır bitince boşların doldurulması, yakınlaştırma, kilitlenebilir ipucu çubukları ve varsayım denetimi bulunuyor. Bunlar yalnızca etkileşim fikirleridir. İlk tasarım için boş işareti, geri alma, ipucu, yakınlaştırma ve sabit ipucu çubukları seçildi. Otomatik işaretleme ile varsayım denetimi oyuncunun kontrolünü koruyan ayrı, isteğe bağlı yardımcılar olarak değerlendirilecek. Sitedeki lonca/yerleşim/görev gibi oyun sistemleri ürün kapsamı dışındadır.

## 3. Önerilen depo ve bağımlılık yönü

```text
src/pixel_nonograms/
  app.py
  core/          puzzle.py, cell.py, clue.py, game_session.py, validation.py, commands.py
  solver/        possibilities.py, line_solver.py, solver.py, hint_engine.py
  rendering/     board.py, camera.py, clue_renderer.py, grid_renderer.py, tile_cache.py
  persistence/   database.py, migrations.py, save_manager.py
  services/      puzzle_library.py, inventory.py, statistics.py, achievements.py
  importer/      puzzle_reader.py, puzzle_writer.py, image_importer.py
  ui/            main_window.py, home_screen.py, collection_screen.py,
                 game_screen.py, editor_screen.py, statistics_screen.py, settings_screen.py,
                 theme.py, i18n.py
  resources/     icons/, puzzles/, translations/, themes/
tests/           core/, solver/, persistence/, importer/, ui/, packaging/
packaging/       appimage/, deb/, windows/
docs/
```

Bağımlılık yönü: `core` yalnızca Python standart kütüphanesi ve gerektiği yerde NumPy kullanır; `solver` yalnızca `core` kullanır. `persistence`, `importer` ve `services` çekirdek tiplerini kullanır. `rendering` ve `ui` Qt'yi kullanır; çekirdek bunları içe aktarmaz. `app.py` nesneleri kurar. `services` içinden widget veya `QApplication` kullanılmaz. `achievements.py`, `editor_screen.py` ve `tile_cache.py` önerilen yerlerdir; ihtiyaç doğmadan işlev uygulanmaz.

## 4. Domain modeli ve oynanış sözleşmesi

- `Puzzle`: değişmez `id`, `revision`, `ruleset`, `width`, `height`, başlık/etiket, satır ve sütun ipuçları, doğrulanmış çözüm maskesi. Çözüm verisi arayüze doğrudan verilmez. Paketli ve kullanıcı kaynaklı bulmacaların sahipliği ayrıca tutulur.
- `CellState`: `UNKNOWN=0`, `FILLED=1`, `EMPTY=2`. `EMPTY` oyuncunun boş işaretidir. Gerekirse ayrı `note` katmanı eklenir; ana hücre durumuyla karıştırılmaz.
- `Clue`: pozitif run uzunlukları. Boş satır/sütun için boş liste; ekranda `0` gösterimi yalnızca sunum kararıdır. Bir çizgide `sum(runs) + len(runs) - 1 <= line_length` şarttır.
- `GameSession`: oyuncu durum matrisi, hata/yardım sayaçları, etkin süre, durum (`active/completed`), revizyon ve undo/redo komutları. Aynı hücreye sürükleme hareketi tek komut olabilir. Yeniden başlatma açık komuttur.
- Tamamlama: oyuncunun `FILLED` hücreleri çözümdeki dolu hücrelerle birebir aynıysa tamamlanır; diğer hücrelerde `UNKNOWN` veya `EMPTY` olabilir. Yanlış dolu hücre varsa tamamlanmaz. Yanlış boş işareti çözümde dolu hücreyi engeller. Böylece bütün boş hücreleri işaretlemek zorunlu değildir.
- Doğrulama: varsayılan oyun, yanlış girişi anında engellemez; satır/sütun çelişkisi ve hata vurgusu oyuncu ayarına bağlıdır. Açık “hataları denetle” eylemi ile bulmaca çözümü üzerinden kesin kontrol ayrılır. Yardım kullanımının istatistiğe etkisi kaydedilir.
- Tek çözüm politikası: paketli ve editörde yayımlanan bulmacalar yalnızca ipuçlarından tek çözümlü olmalıdır. İçe aktarma birden fazla çözüm bulursa uyarı ve düzenleme akışı gerekir; belirsiz bulmaca otomatik olarak normal koleksiyona eklenmez.

## 5. Çözücü ve ipucu mimarisi

`possibilities.py` bir çizginin ipuçlarına ve mevcut hücre durumlarına uyan yerleşimleri üretir. `line_solver.py` bütün olası yerleşimlerin kesişiminden zorunlu dolu/boş hücreleri çıkarır. `solver.py` satır ve sütun kısıtlarını sabit noktaya kadar yayar; belirsizlikte dallanıp en fazla iki çözüm arar. İkinci çözüm bulunduğunda tekillik kontrolü durur. Zaman/hafıza sınırı aşılırsa sonuç `UNKNOWN` olur; `UNIQUE` varsayılmaz.

`hint_engine.py` önce mantıksal, açıklanabilir bir adım seçer: çizgi ve gerekçe gösterilir, oyuncunun yerine otomatik işaretleme varsayılan değildir. Ayrı bir açık istek, tek hücreyi güvenli biçimde açabilir; bu işlem yardım sayacına yazılır. İpucu motoru mümkünse oyuncu işaretlerine göre çalışır; çelişki durumunda önce çelişkiyi bildirir. Çözüm maskesine dayalı doğrudan açma, mantık ipucundan ayrı bir yardım türüdür. Çözücü arayüz iş parçacığı dışında çalışır; iptal edilebilir ve sonuçlar oturum revizyonu eşleşirse uygulanır.

Tek çözüm ile seçilen mantık kurallarıyla tahminsiz çözülebilme farklı doğrulamalardır. Paketli bulmacalar için ikisi de raporlanır; yalnızca tekillik sonucu “kolayca mantıkla çözülür” anlamına gelmez.

## 6. Bulmaca dosyası ve içe aktarma

Önerilen `.nono` v1, ZIP içinde `metadata.json` ve `solution.bin` taşır. `metadata.json`: `format_version`, sabit `id`, `revision`, `ruleset=monochrome-v1`, `width`, `height`, UTF-8 başlık, isteğe bağlı yazar/etiketler, satır/sütun ipuçları, çözüm SHA-256 özeti ve içerik lisansı. `solution.bin` satır öncelikli 1 bit/hücre maskesidir; son bayttaki kullanılmayan bitler sıfırdır. İpuçları maske üzerinden yeniden hesaplanıp metadata ile karşılaştırılır. Önizleme isteğe bağlıdır; çözüme dair görsel koleksiyonda tamamlanmadan gösterilmez. Oyuncu kaydı dosyanın içinde bulunmaz.

Okuyucu üye adlarını, tekrarları, sıkıştırılmamış toplam boyutu, boyutları, metin uzunluklarını, bit uzunluğunu ve biçim sürümünü kontrol eder; path traversal ve ZIP bombası reddedilir. Yazıcı geçici dosya + atomik değiştirme kullanır. Paketli bulmacalar uygulama kaynaklarında salt okunur kalır; kullanıcı bulmacaları kullanıcı veri dizininde saklanır. Görsel içe aktarma Pillow ile EXIF yönünü uygular, alfayı belirlenen arka plana birleştirir, yeniden boyutlandırma ve eşik ayarını kullanıcıya gösterir; ardından ipuçları ve tekillik doğrulaması yapılır. Referansın `.pcolor` dosyaları otomatik içeri alınmaz: piksel boyama hedefleri Nonogram olarak tek çözümlü oldukları anlamına gelmez.

## 7. SQLite v1 taslağı

Tek kullanıcı yerel DB. `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout` ve sürümlü `PRAGMA user_version`. Geçişler transaction içinde, sırayla ve tekrar çalıştırılabilir biçimde yürütülür. Daha yeni sürümdeki DB açılmaz; eski dosya geçişten önce yedeklenir. Tarihler UTC Unix saniyesi; süreler tam sayı milisaniye. Başlangıç uygulaması ayrı veri dizini kullanır, referans `progress.sqlite3` dosyasına dokunmaz.

| Tablo | Temel alanlar | Kural |
|---|---|---|
| `puzzles` | `id` PK, `revision`, `source`, `file_path`, `content_hash`, `title`, `width`, `height`, `ruleset`, `created_at` | ID ve revizyon kayıt eşleştirir; paketli dosya yolu uygulama kaynağına göre çözülür. |
| `progress` | `puzzle_id` PK/FK, `puzzle_revision`, `state_version`, `cells_blob`, `session_revision`, `saved_revision`, `elapsed_ms`, `mistakes`, `hints_used`, `status`, `updated_at`, `completed_at` | Üç durumlu hücreler 2 bit/hücre kodlanır; boyut ve aralık yüklemede doğrulanır. |
| `completions` | `id` PK, `puzzle_id` FK, `completed_at`, `elapsed_ms`, `hints_used`, `mistakes`, `attempt_no` | İstatistiğin değişmez kaynağı; tekrarlı çözümler ayrı satırdır. |
| `inventory` | `tool_id` PK, `quantity` | Yalnızca küçük, önceden tanımlı yardım türleri; `quantity >= 0`. |
| `inventory_events` | `id` PK, `puzzle_id` FK, `tool_id`, `delta`, `reason`, `event_key` UNIQUE, `created_at` | Ödül ve kullanım için denetim izi; tekrar kayıtta çift ödül engellenir. |
| `settings` | `key` PK, `value_json` | Görünüm ve erişilebilirlik tercihleri. |

`achievements` ancak gerçek bir oyuncu gereksinimi doğarsa eklenir; şema v1'in zorunlu parçası değildir. Toplam çözüm, en iyi süre ve ortalama süre `completions` üzerinden hesaplanır veya ölçülürse önbelleklenir. Tamamlama, `progress` güncellemesi, `completions` kaydı ve olası envanter ödülü tek transaction içinde; `event_key` ile idempotent. Tamamlanan bulmacayı yeniden oynamak eski completion geçmişini silmez. Paketli bulmaca revizyonu değişirse çözüm maskesi aynı hash'e sahip değilse ilerleme sessizce uygulanmaz; dönüşüm veya açık sıfırlama kararı gerekir.

## 8. Kayıt yaşam döngüsü

Her değişiklik oturum revizyonunu artırır. `SaveManager` ana iş parçacığında değişmez bir snapshot alır, tek yazıcı işçiye iletir; eski bekleyen ara snapshot'lar birleştirilebilir, ancak tamamlama transaction'ı atlanamaz. DB yazımı yalnızca daha yeni `session_revision` için yapılır; eski snapshot yeniyi ezmez. Periyodik kayıt, odak kaybı, ekran değişimi ve uygulama kapanışı tetikleyicidir. Kapanışta `flush` beklenir ve hata görünür kılınır. Başarısız kayıt “kaydedildi” diye gösterilmez. Açılışta `state_version`, bulmaca revizyonu, blob uzunluğu ve değerleri doğrulanır; bozuk kayıt yedeklenip kullanıcıya kurtarma/sıfırlama seçeneği sunulur. Süre yalnızca aktif oynanışta akar; duraklama ve arka plan süresi eklenmez. Undo geçmişi ilk tasarımda oturum içidir; yeniden açılışta hücreler korunur, geçmiş korunmaz.

## 9. Çizim ve arayüz ergonomisi

Tek `BoardWidget`/`QPainter` çizimi kullanılır. Kamera mantıksal hücre koordinatını ekran koordinatına çevirir; DPI ve kesirli ölçekleri hesaba katar. Sol ve üst ipuçları ızgarayla hizalıdır, kaydırmada ilgili eksende sabit kalır. Köşe paneli sabittir. Görünür hücreler, değişen satır/sütun ve ipucu bölgeleri yeniden çizilir. Kalın beşlik çizgiler, satır/sütun vurgusu, tamamlanan ipucunun görünümü, yüksek kontrast, renk dışı durum sembolleri ve klavye odağı ayrı render katmanlarıdır. Çok büyük tahtada ölçüm gösterirse sınırlı LRU `TileCache` eklenir; ipuçları ve hover katmanı karoya gömülmez.

Varsayılan kontroller: sol tık dolu, sağ tık boş, aynı hareketle tekrar işaretleme durum değiştirme, orta tuş/boşluk ile taşıma, tekerlek ile imleç merkezli yakınlaştırma; klavyede oklar, Dolu/Boş/Bilinmeyen eylemleri, geri al/ileri al. Sürükleme bir komut olur ve yanlışlıkla dolu/boş durumları çapraz değiştirmez. Araç seçimi, tüm kontroller ve erişilebilir kısayollar ayarlarda açıklanır. Tamamlama animasyonu kısa ve atlanabilir; bir sonraki bulmacaya doğrudan geçiş sunulur. İpucu açıklamaları odak ve ekran okuyucu için metin olarak da bulunur.

Tema QSS değişkenleriyle tutarlı renk/boşluk/odak değerlerine ayrılır; açık/koyu ve yüksek kontrast varyantları tasarlanır. Tüm görünür metinler çeviri anahtarlarından gelir. Bulmaca başlığı kullanıcı verisi olduğundan kaynak dilde saklanır, paketli içerik için çevrilmiş görünen ad ayrı eşlenebilir.

## 10. Envanter ve istatistik sınırı

İlk yardım türleri `logic_hint` (mantıksal adım) ve `reveal_cell` (tek hücre açma) olarak tasarlanır. Mantıksal ipucu sınırsız ücretsiz kullanılabilir; `reveal_cell` için ödül miktarı ve tüketim kuralı ileride ürün kararı olarak tanımlanır. Envanter yokken çözüm daima mümkündür; araçlar bulmaca kilidi açmaz. Ödüller yalnızca belirlenmiş bulmacaların ilk tamamlanışında, bir kez verilebilir; tekrar çözmek farm döngüsüne dönüşmez. Para, mağaza, craft ve günlük bonus şemada yer almaz. İstatistik ekranı çözülen bulmaca, toplam etkin süre, tekrar çözüm ve yardım kullanımını gösterir; günlük giriş serisi teşvik edilmez.

## 11. Test ve dağıtım yaklaşımı

- `pytest`: ipucu üretimi, boş çizgiler, en uzun run, çelişki, tek/çok/çözümsüz bulmaca, dallanma sınırı ve çözüm doğruluğu için küçük elle doğrulanmış bulmacalar; özellik tabanlı üretim daha sonra değerlendirilebilir.
- SQLite: yeni kurulum, geçiş, yarım kalmış kayıt, bozuk blob, eski snapshot yarışması, tamamlama ve ödülün idempotent transaction'ı, yeniden oynama. Geçici dizin ve gerçek SQLite kullanılır.
- Importer: boyut/ZIP limiti, geçersiz başlık, çelişen ipuçları, hash, EXIF/alfa ve çok çözümlü görsel. Paketli katalogdaki her bulmaca için format ve tekillik kontrolü CI'da yapılır; ağır kontrol ayrı kalite kapısı olabilir.
- Qt: `QT_QPA_PLATFORM=offscreen` ile açılış, fare/klavye koordinatı, zoom/pan, ipucu hizası, ekran geçişi ve kayıt hatası görünürlüğü. Gerçek Linux/Pardus/Debian ve Windows ekranlarında elle DPI, fare ve odak testleri gerekir.
- `ruff check`, `pytest`, Python 3.13 ile CI; AppImage/DEB paketlerinde temiz veri dizini ve ağ kapalı smoke testi. Windows portable, gerekli olduğunda aynı veri yolu/Qt plugin testiyle eklenir. Paketler PySide6, NumPy, Pillow ve kaynak bulmacaları içerir; çalışma anında indirme yapmaz.

## 12. Karar ve açık noktalar

Bu fazın mimari kararı, referanstaki katman ayrımını ve tek widget çizim yaklaşımını örnek almak; Nonogram kuralları, veri biçimi, SQLite şeması ve görsel kimliği için bağımsız uygulama kurmaktır. Referansın kodu, resimleri, metinleri ve `.pcolor` içeriği yeni ürüne taşınmaz. Nonograms Katana yalnızca oynanış ve ergonomi için fikir kaynağıdır; özgün varlıkları alınmaz.

Sonraki fazın kapsamı kullanıcı tarafından ayrıca belirtilecektir. Kodlama başlamadan önce görünür ürün adı, ilk yayın için bulmaca boyut aralığı, paketli bulmaca kaynağı/lisansı ve ödüllü yardım kuralı ürün kararları olarak kesinleştirilebilir. Bu kararlar çekirdek/çözücü tasarımının başlamasına engel değildir.
