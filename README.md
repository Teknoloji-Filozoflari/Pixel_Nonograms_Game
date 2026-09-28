<div align="center">
  <img src="docs/oyun_logosu.png" width="112" alt="Piksel Nonogram logosu">
  <h1>Piksel Nonogram</h1>
  <p><strong>Sayıları takip et. Pikselleri tamamla.</strong></p>
  <p>Çevrimdışı çalışan, renkli ve siyah beyaz bulmacalara sahip masaüstü nonogram oyunu.</p>
  <p>
    <a href="https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/releases">⬇️ Linux sürümleri</a> ·
    <a href="#kurulum">Kurulum</a> ·
    <a href="#geliştirme">Geliştirme</a>
  </p>
  <p>
    <img alt="Python 3.13+" src="https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white">
    <img alt="PySide6" src="https://img.shields.io/badge/Aray%C3%BCz-PySide6-41CD52">
    <img alt="Linux paketleri" src="https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/actions/workflows/linux-packages.yml/badge.svg">
  </p>
</div>

![Renkli nonogram oyun tahtası](docs/tahta_normal.png)

## Oyunda neler var?

| | |
| --- | --- |
| 🧩 **1.000 bulmaca** | 800 siyah beyaz ve 200 renkli bulmaca; kolaydan uzmana farklı tahta boyutları. |
| 🎨 **Kendi bulmacanı oluştur** | Dahili editörle çiz, görselden içe aktar, çözümü analiz et ve kaydet. |
| 💡 **Yardımcı araçlar** | Satır ve sütun yardımı, alan ipuçları, işaretçiler ve geri alma. |
| 🌍 **Beş dil** | Türkçe, Azerbaycan Türkçesi, İngilizce, İspanyolca ve Rusça. |
| 💾 **Yerel ilerleme** | Bulmacalar ve kayıtlar çevrimdışı çalışır; ilerleme SQLite ile saklanır. |
| 🖥️ **Büyük tahtalara uygun** | Yakınlaştırma, kaydırma ve tam ekran tahta görünümü. |

<table>
  <tr>
    <td width="50%"><img src="docs/dil_tr.png" alt="Bulmaca kütüphanesi"><br><strong>Bulmaca kütüphanesi</strong></td>
    <td width="50%"><img src="docs/aile_editor.png" alt="Bulmaca editörü"><br><strong>Kendi çizimini oluştur</strong></td>
  </tr>
</table>

<details>
<summary>Daha fazla ekran görüntüsü</summary>

![Tam ekran oyun tahtası](docs/tahta_tam_ekran.png)

![Bulmaca çizimleri](docs/yeni_bulmacalar.png)

</details>

## Kurulum

**Linux x86_64 / amd64:** [Releases sayfasından](https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/releases) sürüme ait AppImage veya `.deb` dosyasını indirin. Yayın henüz yoksa [Actions → Linux packages](https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game/actions/workflows/linux-packages.yml) sayfasındaki başarılı çalışmanın `Pixel-Nonograms-Linux-amd64` çıktısını kullanın.

AppImage için:

```sh
chmod +x Pixel_Nonograms-*-x86_64.AppImage
./Pixel_Nonograms-*-x86_64.AppImage
```

Debian veya Pardus için:

```sh
sudo apt install ./pixel-nonograms_*_amd64.deb
```

Uygulama menüsünden **Piksel Nonogram**'ı açın. Paketler Python kurulumuna ihtiyaç duymaz. AppImage için FUSE bulunmayan sistemlerde `APPIMAGE_EXTRACT_AND_RUN=1 ./Pixel_Nonograms-*-x86_64.AppImage` kullanılabilir. Paketlerin hedefi Debian 12/13 ve Pardus 23/25 masaüstüdür; doğrudan Pardus cihaz testi henüz yapılmadı. Ayrıntılar: [Linux dağıtım rehberi](README_LINUX.md).

**Windows / kaynaktan çalıştırma:** Python 3.13 veya yeni sürüm kurun, ardından proje klasöründe:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pixel_nonograms
```

Linux'ta Python 3.13 ile `sh Oyunu_Baslat_Linux.sh` da kullanılabilir. İlk kurulumda bağımlılıkların indirilmesi gerekir; oyun çevrimdışı çalışır.

## Nasıl oynanır?

Satır ve sütun başındaki sayılar, o çizgide art arda boyanacak hücre gruplarını gösterir. Grupların arasında en az bir boş hücre bırakılır. İpuçlarını birleştirerek gizli resmi ortaya çıkarın. Renkli bulmacalarda önce paletten rengi seçin.

| Kontrol | İşlev |
| --- | --- |
| Sol tık / sürükle | Hücre boyama |
| Sağ tık / `X` | Boş hücre işaretleme |
| `B` | Boya aracına geçme |
| `F` / `R` | Tahtayı sığdırma / okunabilir yakınlaştırma |
| `F11` | Tahta tam ekranı |
| `Boşluk` + sürükle | Tahtayı kaydırma |

## Geliştirme

Kaynak kod `src/pixel_nonograms` altında; testler `tests` içinde. Python 3.13+ ortamında:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m pixel_nonograms
```

Linux paketleri Debian 12 tabanlı Docker ortamında üretilir. `main` dalına gönderimler ve `v*` etiketleri [CI iş akışını](.github/workflows/linux-packages.yml) çalıştırır. Etiket başarılı olduğunda AppImage, DEB, SHA-256 listesi ve birleşik arşiv GitHub Releases'e eklenir. Yerel derleme komutları [README_LINUX.md](README_LINUX.md) içindedir.

Üçüncü taraf bileşenler ve bildirimler için [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) dosyasına bakın.
