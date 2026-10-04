# Piksel Nonogram — Linux dağıtımı

1.000 çevrimdışı bulmaca, beş dil ve tam ekran boyama.

## Paketler

Paketler [GitHub Releases](https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/releases)
sayfasında yayımlanır. Bir sürüm henüz yayımlanmadıysa başarılı
[`Linux packages` iş akışının](https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/actions/workflows/linux-packages.yml)
`Pixel-Nonograms-Linux-amd64` çıktısından indirilebilir. Kaynak ZIP dosyası
çalıştırılabilir AppImage veya DEB paketi değildir.

Hedef: **x86_64/amd64**, Debian 12/13 ve Pardus 23/25 masaüstü.
Pardus aynı `.deb` paketini kullanır; doğrudan Pardus cihaz testi henüz yapılmadı.
ARM ve 32-bit sürüm yoktur. Paketler Debian 12 üzerinde üretilir; en az glibc 2.36
gerekir. Varsayılan Qt arayüzü X11/xcb; Wayland oturumunda XWayland gerekir.

## GitHub'da paketleri üretme

1. **Actions → Linux packages → Run workflow** seçin; `v*` etiketi de bu akışı başlatır.
3. `build` ve `install-test` işleri yeşil olunca **Pixel-Nonograms-Linux-amd64**
   çıktısını indirin.
4. `v0.1.1` gibi bir sürüm etiketi gönderildiğinde, başarılı kurulum testlerinden
   sonra `.AppImage`, `.deb`, `SHA256SUMS.txt` ve birleşik `.tar.gz` otomatik
   olarak GitHub Releases'e eklenir.

Derleme internet ister; oyunun çalışması internet gerektirmez.

## Oyuncu için kurulum

### AppImage

Arşivi çıkarıp çalıştırın:

```sh
chmod +x Pixel_Nonograms-0.1.1-x86_64.AppImage
./Pixel_Nonograms-0.1.1-x86_64.AppImage
```

FUSE yoksa:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Pixel_Nonograms-0.1.1-x86_64.AppImage
```

### Debian / Pardus

```sh
sudo apt install ./pixel-nonograms_0.1.1_amd64.deb
```

Uygulama menüsünden **Piksel Nonogram**'ı açın veya `pixel-nonograms` çalıştırın.
Python ve Qt pakette gelir; apt eksik masaüstü kütüphanelerini kurar.
Kaldırma: `sudo apt remove pixel-nonograms`. Kişisel kayıtlar silinmez.
Kayıtlar normalde `~/.local/share/Pixel Nonograms/` altında tutulur.

## Docker ile derleme

Proje kökünde:

```sh
docker build -f packaging/linux/Dockerfile -t pixel-nonograms-build .
mkdir -p dist/linux
docker run --rm -e OUTPUT_DIR=/out -v "$PWD/dist/linux:/out" pixel-nonograms-build
```

Windows PowerShell / Docker Desktop Linux konteynerleri:

```powershell
docker build -f packaging/linux/Dockerfile -t pixel-nonograms-build .
New-Item -ItemType Directory -Force dist/linux
docker run --rm -e OUTPUT_DIR=/out -v "${PWD}/dist/linux:/out" pixel-nonograms-build
```

Çıktı: `dist/linux`. Sabit bağımlılıklar: `packaging/linux/requirements-build.txt`.
AppImage aracı SHA-256 ile doğrulanır. `.deb`, `/opt/pixel-nonograms` altına kurulur.
Python 3.13 / Debian 12 tabanı kullanılır; bit düzeyinde tekrarlanabilirlik iddia edilmez.

## Kaynaktan çalıştırma

Python 3.13 ve venv varsa `sh Oyunu_Baslat_Linux.sh` çalıştırın. İlk açılışta
`.venv-linux` oluşturulur, bağımlılıklar indirilir. Kaynak güncellemesinden sonra
`.venv-linux/bin/python -m pip install --no-deps .` ile kurulu kopyayı güncelleyin.
Oyuncular için Python istemeyen AppImage/.deb tercih edilir.

## Doğrulama

- `--smoke-test`: geçici dizinde Qt arayüzü, 1.000 bulmaca, çeviri, SQLite kayıt
  ve tam ekran kontrolü; kişisel kayıtlar kullanılmaz.
- CI: gerçek AppImage içeriğinin açılışı; temiz Debian 12 ve 13'te .deb kurulumu.
- Bütünlük: `sha256sum -c SHA256SUMS.txt`.
- Sürüm `pyproject.toml` dosyasından alınır.

Kaynaklar: [PyInstaller](https://pyinstaller.org/en/stable/usage.html),
[AppImage](https://github.com/AppImage/appimagetool),
[Pardus sürümleri](https://pardus.org.tr/en/version-management/).

## RPM — Fedora 43

```sh
sudo dnf install ./pixel-nonograms-0.1.1-1.fc43.x86_64.rpm
```

Fedora 43 x86_64 / glibc 2.42+ hedeflenir. Python 3.14, Qt 6.11, NumPy ve
Pillow özel `/usr/lib/pixel-nonograms` bundle'ındadır. Sistem kütüphaneleri
RPM spec içinde tanımlıdır; özel bundle sistem Provides/Requires'a karışmaz.
Diğer RPM dağıtımları ve eski Fedora ayrıca doğrulanmalıdır. Paket kaldırma
oyuncunun XDG kayıtlarını silmez.

Fedora build ortamında, workflow'daki rpmbuild/Qt/XCB bağımlılıkları kurulduktan sonra:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -c packaging/linux/requirements-fedora.txt '.[dev]' PyInstaller
.venv/bin/python tools/build_bundle.py
.venv/bin/python tools/build_rpm.py
```

## Snap — core24 amd64

GitHub'dan indirilen Store imzası olmayan paketi kurmak için:

```sh
sudo snap install --dangerous ./pixel-nonograms_0.1.1_amd64.snap
pixel-nonograms
```

Strict confinement ve `grade: devel` kullanılır; Snap Store yayını yoktur.
Oyun çevrim dışıdır; network interface'i tanımlanmaz. Görsel içe aktarma için
home interface'i kullanılır; gizli klasörlere genel erişim vermez.
Kayıtlar sistem kurulumundan ayrı `~/snap/pixel-nonograms/common/data/Pixel Nonograms`
altında tutulur. Kayıt taşırken oyun kapalı olmalı ve önce veri klasörü yedeklenmelidir.

Üretim önce Ubuntu 22.04/Python 3.13 üzerinde Qt 6.8.3 bundle'ını
`build/bundle/pixel-nonograms` altında doğrular, ardından Snapcraft bunu core24'e alır.
Yerel üretimde de bundle hazırlandıktan sonra `snapcraft` çalıştırılır.
Base sistemin Python 3.12'sine oyun kurulmaz.

## Nix / NixOS

Flake desteği etkin Nix ile:

```sh
nix run github:Teknoloji-Filozoflari/Pixel_Nonograms_Game/v0.1.1
nix profile install github:Teknoloji-Filozoflari/Pixel_Nonograms_Game/v0.1.1
```

NixOS'ta gerektiğinde `nix.settings.experimental-features = [ "nix-command" "flakes" ];`
etkinleştirilir. Sistem flake'ine
`inputs.nonograms.url = "github:Teknoloji-Filozoflari/Pixel_Nonograms_Game/v0.1.1";`
eklenip `nonograms.packages.x86_64-linux.default` sistem veya Home Manager paketlerine alınabilir.

```sh
nix build
nix flake check --print-build-logs
./result/bin/pixel-nonograms
```

Nixpkgs 25.11 revizyonu `flake.lock` ile sabitlenir. Qt yolları Python
başlatıcısına sarılır. Nix tam PySide6 dağıtımını sağladığından yalnız Nix build
metadata'sında Essentials bağımlılık adı PySide6 olarak eşleştirilir.
Nix store salt okunurdur; oyuncu kayıtları normal XDG klasörüne yazılır.

Oyun kodu GNU GPL 3.0 veya sonraki sürümleri (`GPL-3.0-or-later`) altında sunulur.
Nix metadata'sı `lib.licenses.gpl3Plus` kullanır.
Üçüncü taraf lisans bildirimleri korunur. Resmî Nixpkgs yayını yapılmadı.
x86_64 CI build ve kurulu paket açılışı doğrulanır; gerçek NixOS masaüstü veya
ARM64 kontrolü değildir. aarch64 flake çıktısı tanımlıdır ama doğrulanmamıştır.

## Doğrulanmış paketlerle yayın

`Publish verified Linux packages` workflow'u Linux build/DEB kurulum,
AppImage temiz Ubuntu kontrolü, RPM, Snap ve Nix koşularının tamamının başarılı
olmasını zorunlu tutar. AppImage, DEB, RPM, Snap, Python wheel/sdist ve temiz
GitHub kaynak ZIP'i ortak `SHA256SUMS.txt` ile aynı sürüme yüklenir.
AUR işlemi yapılmaz; mevcut v0.1.0 sürümü korunur.

AppImage temiz Ubuntu 24.04 üzerinde, DEB Debian 12/13 üzerinde,
RPM Fedora 43 ve strict Snap Ubuntu 24.04/snapd ortamında kontrol edilir.
X11 testleri Xvfb kullanır; fiziksel ekran sürücüsü testi değildir.
Her açılış kontrolü Qt arayüzü, 1.000 bulmaca, beş dil, SQLite save/load ve
tam ekran davranışını geçici kayıtlarla sınar.
