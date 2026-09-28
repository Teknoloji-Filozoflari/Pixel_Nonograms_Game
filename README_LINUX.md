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

1. **Actions → Linux packages → Run workflow** seçin. `main`/`master` gönderimi
   veya `v*` etiketi de derlemeyi başlatır.
3. `build` ve `install-test` işleri yeşil olunca **Pixel-Nonograms-Linux-amd64**
   çıktısını indirin.
4. `v0.1.0` gibi bir sürüm etiketi gönderildiğinde, başarılı kurulum testlerinden
   sonra `.AppImage`, `.deb`, `SHA256SUMS.txt` ve birleşik `.tar.gz` otomatik
   olarak GitHub Releases'e eklenir.

Derleme internet ister; oyunun çalışması internet gerektirmez.

## Oyuncu için kurulum

### AppImage

Arşivi çıkarıp çalıştırın:

```sh
chmod +x Pixel_Nonograms-0.1.0-x86_64.AppImage
./Pixel_Nonograms-0.1.0-x86_64.AppImage
```

FUSE yoksa:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Pixel_Nonograms-0.1.0-x86_64.AppImage
```

### Debian / Pardus

```sh
sudo apt install ./pixel-nonograms_0.1.0_amd64.deb
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
