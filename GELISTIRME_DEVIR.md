# Geliştirme devir notu — 28 Eylül 2026

## Ürün yönü

PC odaklı, Nonograms Katana'dan ilham alan nonogram oyunu. Minimal simge düğmeleri,
görünür bulmaca isimleri, beyaz tahta ve antrasit/mercan/yeşil karanlık tema.
Atölye ve yerleşim kurma istenmiyor. Bulmaca çözerek yardımcı malzemeler kazanma
ve görevlerden daha güçlü ödüller alma döngüsü korunmalı.

## Mevcut özellikler

- Siyah-beyaz ve renkli bulmacalar; Renkli kategorisi ve iki kolay renkli örnek.
- Kütüphane kategorileri: Tümü, Kolay, Orta, Uzman, Renkli.
- Renkli bulmacalarda renk paleti düğmeleri.
- Açılır işaretçi menüsü, birleşik yatay/dikey ok işaretleri.
- Tahta içinde 5/10/15 sıra numaraları; sayı arkasında kutu yok.
- Tamamen boş satır/sütunların sıkıştırılması ve eski kayıtların uyarlanması.
- İlk tamamlamada her bulmacadan en az bir ödül, ek görev ödülleri.
- Bulmaca editörü, görsel içe aktarma, çözüm analizi, ipuçları, kayıt sistemi.

## Son değişiklik

- Linux dağıtım hazırlığı: `packaging/linux/Dockerfile` Debian 12/Python 3.13
  tabanında sabit Qt 6.8.3 bağımlılıklarıyla PyInstaller paketi üretir.
  `tools/build_linux.py` AppImage, amd64 .deb ve ikisini içeren tar.gz hazırlar.
  `.github/workflows/linux-packages.yml` oyun testleri, donmuş uygulama smoke testi
  ve Debian 12/13 kurulum testlerini çalıştırır. Pardus 23/25 hedeflenir;
  doğrudan Pardus testi henüz yapılmadı. Yerel Windows'ta WSL/Docker yok:
  Linux ikilileri üretilmedi; bu aşamada hazırlanan çıktı GitHub kaynak ZIP'idir.
  `tools/make_github_archive.py` sanal ortam/kayıt/.reference verilerini dışlar.
  Kullanım ve çıktı ayrımı `README_LINUX.md` içinde.

- Tam ekranda bütün satır/sütun ipuçları gösterilir; normal görünümdeki
  bant sınırı ve üç nokta kısaltması uygulanmaz. Bantlar ekrana uyarlanır,
  yakınlaştırırken sayılar sabitlenir. Üst şeritte boya/X/taşı, geri al,
  yakınlaştır/uzaklaştır, sığdır ve okunabilir yakınlaştırma ile renk seçimi var.
  F=sığdır, R=okunabilir yakınlaştır, B=boya, X=boş; Boşluk+sürükle=taşı.
  Çıkışta kullanıcının normal görünümdeki sayıları sabitleme tercihi geri gelir.

- Paketli 1.000 bulmaca artık kare boyutlarını korur: Kolay 5/10,
  Orta 15–20, Zor 25–30, Uzman 30–50. Eski 7×7 kolay çizim 10×10
  boş kenarla tamamlanır. `packaged-grid` etiketi paketli tahtalarda boş
  çizgi kaldırmayı kapatır; kullanıcı bulmacalarının sıkıştırması aynı kalır.
  Önceki sıkıştırılmış kayıtlar, işaretleri ve ipucu çizikleriyle tam boyuta
  yüklenirken geri taşınır. Kimlikler ve 800 siyah-beyaz/200 renkli adet korunur.

- Bütün kategorilerin varsayılan sırası tahta hücre sayısına göre küçükten
  büyüğe değiştirildi. Eşit hücre sayısında genişlik, yükseklik ve ad kullanılır.

- Katalog 1.000 bulmacaya çıktı: siyah-beyaz Kolay/Orta/Zor/Uzman
  275/225/175/125; ayrıca renkli 100/50/25/25. Önceki 84 çizim ve kimlik
  korunur; 916 yeni çizim `catalog_extended.json` içindedir. Üretici:
  `tools/build_extended_catalog.py`. Her yeni tahta hem özgün hem boş çizgileri
  çıkarılmış haliyle tek çözüm doğrulamasından geçer; tekrarlanan çözümler elenir.
  Seviye sekmeleri iki renk türünü de içerir (375/275/200/150); Renkli 200'dür.
  Çizim aileleri ve numaralı başlıklar beş dili destekler. Zorluk sınıfları
  mevcut boyut düzenini izler; yeni çizimler 10/20/25/30 kare boyutundadır.

- Beş Hücre ipucu menüden ve yeni ödüllerden kaldırıldı. Eski kayıt kimliği
  okunabilir kalır; bu ödülü belirten bulmacalar artık satır/sütun yardımı verir.
  Satır/sütun ipucu fareyle soldaki/üstteki ipucu sayılarına tıklanarak uygulanır.
  Hedef çizgi fareyle vurgulanır. Sağ tık/Esc iptal eder; liste seçimi açılmaz.

- 3×3/5×5/10×10 ipuçları artık tahtada kullanıcı tıklamasıyla hedeflenir.
  Fare hareketinde alan önizlenir; seçilen hücre sol üst başlangıçtır,
  sınırda alan içeri kayar. Sağ tık/Esc hedeflemeyi ücretsiz iptal eder.
  Otomatik alan seçimi kaldırıldı; hizmet katmanı geçerli başlangıç ister.

- Ampul menüsünde otomatik ipuçları tıklandığı anda uygulanır. Satır/sütun
  yardımında hedef numarası seçilince uygulanır; ek Kullan düğmesi yoktur.
  Açıklamalar yalnız fareyle üzerinde beklenince araç ipucunda görünür.

- Yardımcılar çözümü doğrudan tahtaya uygulayan altı seçeneğe dönüştürüldü:
  satır/sütun çözücü, akıllı düzeltme, 3×3, 5×5, beş hücre ve 10×10.
  Satır/sütun ve alan başlangıcı kullanıcı tarafından seçilir.
  Alanlar küçük tahtalarda sınırlanır. Boş hedefler X olur.
  Akıllı düzeltme önce yanlış boyanmış tek hücreyi düzeltir ve yalnız çevresini
  kırmızı çizer; hata yoksa çözümü ilerletecek tek hücreyi boyar. Renkli hücrenin
  sadece rengi yanlışsa doğru renk uygulanır. Beş hücre ayrı hedefler seçer.
  Her kullanım tek geri alma hamlesidir; yararsız kullanım stok tüketmez.
  Tahta ve stok birlikte kaydedilir; kayıt hatasında ikisi de korunur.
  Eski stok kimlikleri korunur: ROW_SCANNER=satır/sütun, ANALYSIS_LENS=akıllı,
  LOGIC_HINT=3×3, ERROR_CHECK=5×5, COLUMN_SCANNER=beş, SECOND_LOOK=10×10.
  Adlar ve açıklamalar beş dilde güncellendi.

- Tahta için ayrı tam ekran modu eklendi: araç çubuğundaki köşe simgesi veya
  oyun açıkken F11. Esc/F11/geri düğmesi ile aynı oturuma dönülür. Uygulamanın
  başlangıcı normal büyütülmüş penceredir. Küçük tahtalar da ekranı dolduracak
  ölçekte büyür; normal moda dönünce olağan yakınlaştırma sınırı geri gelir.
- Katalog 84 bulmaca: Kolay/Orta/Zor/Uzman 21'er; bunların 21'i Renkli
  filtresindedir. 70 yeni çizim `catalog_expansion.json` içinde; üretim ve
  tek çözüm doğrulama aracı `tools/build_catalog_expansion.py`. Eski kimlikler
  ve çizimler değiştirilmedi. Yeni adlar beş dilde çevrildi.

- Oyun araçları tahtanın üstüne taşındı. Silme ve geçici işaretler üçüncü araç
  düğmesinin menüsünde birleşti. Altı yardımcı, ampul düğmesinden açılan menüde
  adları ve stoklarıyla listelenir; seçilen yardımın hedef/kullanım alanı üstte açılır.
  Menüyü açmak veya yardım seçmek eşya tüketmez.

- Aydınlık tema ve tema seçici kaldırıldı. Sağ üstte beş dilli seçici, ayarlar
  ve kayıt akışını kullanan çıkış düğmesi var. Dil değişimi anında uygulanır ve
  kaydedilir. Ana ekranda oluşturma/öğretici ayarlara taşındı.
  Çeviriler `src/pixel_nonograms/translations.json`, altyapı `i18n.py` içindedir.

- Piksel Atölyesi referans alınarak mercan/yeşil/antrasit aile teması uygulandı.
  Görünen ad Piksel Nonogram; kayıt ve ayar kimlikleri aynı kaldı.
  Yalnızca karanlık tema kullanılır.
  Ayrıntı ve doğrulama: `docs/PIKSEL_AILE_TEMASI.md`.

- Tema seçicisi küçültüldü; yalnızca güneş/ay simgeleri kullanılıyor.
- Logo yeşil ve yumuşak altın tonlarına uyarlandı.
- Bulmacayı aç düğmesi ve simgesi büyütüldü; sıkışan yükseklik düzeltildi.
- Renkli satır/sütunda ipuçlarında olmayan renkle hücre boyanınca veya bir rengin
  izin verilen toplamı aşılınca kırmızı çerçeve gösteriliyor. Notlar sayılmaz;
  geri alma uyarıyı günceller. Mevcut hata gösterme tercihi geçerlidir.
- İlgili 51 test geçti; son düğme boyutu düzeltmesinden sonra 8 kütüphane testi
  tekrar geçti. Tam test paketi bu son değişiklikte yeniden çalıştırılmadı.

## Kod yönlendirmesi

- `ui/theme.py`: renkler, tema seçici ve stiller.
- `ui/branding.py`: logo ve açılış ekranı.
- `ui/collection_screen.py`: kütüphane kartları ve kategoriler.
- `ui/game_screen.py`: oyun araçları, renk paleti ve işaretçiler.
- `rendering/board.py`: tahta çizimi ve satır/sütun uyarıları.
- `docs`: önceki fazlar; eski planlar güncel kullanıcı tercihleriyle çelişirse
  yukarıdaki ürün yönü esas alınmalı.

Arşiv hazırlanırken kullanılan ortam: Python 3.13.15, PySide6-Essentials 6.11.2,
shiboken6 6.11.2, NumPy 2.5.3, Pillow 12.3.0, pytest 9.1.1, Ruff 0.16.9.
Kurulum bağımlılık aralıkları `pyproject.toml` içindedir.


## Linux paketlerini doğrulama ve yayın — 4 Ekim 2026

### Yapılanlar

Mevcut v0.1.0 korunarak 0.1.1 hazırlandı. AppImage/DEB'e ek olarak Fedora 43
RPM, core24 strict Snap ve Nix/NixOS flake eklendi. Kaynaktan ve Nix paketinden
çalıştırmada --smoke-test desteği mevcut dağıtım kontrolüne yönlendirilir.
Oyun davranışı, bulmaca kimlikleri ve oyuncu ilerlemesi değiştirilmedi.

### Değiştirilen önemli dosyalar

- tools/build_bundle.py ve build_rpm.py, RPM spec/başlatıcı.
- snap/, packaging/nix/, flake.nix/lock/default.nix, MANIFEST.in.
- Linux, RPM, Snap, Nix, temiz AppImage kontrolü ve doğrulanmış yayın workflow'ları.
- app.py CLI kontrolü, dört eksik kaynak paketleme testi.
- README/README_LINUX, kaynak ZIP betiği ve v0.1.1 release notları.

### Test sonucu

Yerelde Ruff ve 377 pytest başarılı. Kaynak CLI açılış kontrolü başarılı:
Qt arayüzü, 1.000 bulmaca, beş dil, SQLite save/load ve tam ekran.
Workflow YAML/shell syntax, temiz kaynak ZIP, Nix/Snap/RPM kaynaklarının
ZIP'e dahil olması ve RPM başlatıcı çalıştırma izni doğrulandı.

Başarılı GitHub doğrulamaları:
- AppImage/DEB build ve Debian 12/13 kurulum: 37217549655.
- Temiz Ubuntu 24.04 AppImage offscreen/X11: 37218086696.
- Fedora 43 RPM offscreen/X11 kurulum: 37217551508.
- Nix x86_64 build, 377 test ve kurulu wrapper offscreen: 37217660664.
- Snap build ve strict offscreen/X11 kurulum: 37217553499.

### Manuel kontrol

Paket açılış kontrolleri gerçek Qt arayüzünü geçici kayıtlarla sınar;
X11 için sanal Xvfb kullanılır. Yayın workflow'u bütün başarılı koşuları
zorunlu tutar; AppImage/DEB/RPM/Snap, wheel/sdist, temiz kaynak ZIP ve ortak
SHA256SUMS.txt sürüm sayfasına yüklenir. Eski build arşivinin yerine güncel
kurulum belgeleri ve ayrı doğrulanmış paketler yayımlanır.

### Bilinen sorunlar

AUR, Snap Store ve resmî Nixpkgs yayını yoktur. Snap devel/strict ve yerel
--dangerous kurulumu kullanır; kayıtları SNAP_USER_COMMON altında ayrıdır.
AppImage/DEB glibc 2.36+, Fedora 43 RPM glibc 2.42+ hedefler.
Gerçek Pardus, NixOS masaüstü ve ARM64 testi yapılmadı.
Proje kod lisansı depoda belirtilmemiştir; yeni lisans seçilmedi. RPM bunu
LicenseRef-Unknown, Nix unfree olarak korur; flake yalnız bu pakete izin verir.
Üçüncü taraf lisansları paketlerde saklanır.

### Sonraki faz

Kullanıcının sonraki isteği.
