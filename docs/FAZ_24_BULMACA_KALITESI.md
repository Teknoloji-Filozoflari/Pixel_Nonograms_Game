# Faz 24 — Bulmaca kalitesi ve editör

- Editörde **Kalite Analizi** düğmesi; kayıt ve görsel içe aktarımı sonrasında da rapor.
- Tek çözüm kontrolü mevcut sınırlı aramayla yapılır. Mantıksal çözüm ayrı olarak yalnızca ipuçlarından, oyunun açıklamalı ipucu motoruyla yürütülür.
- Rapor tamamlanan hücre sayısını, ortak hücre / tamamlanan blok / olanaksız konum / çapraz çıkarım sayılarını gösterir.
- Yaklaşık zorluk kullanılan çıkarımlara bağlıdır: temel çıkarımlar kolay, olanaksız konum orta, çapraz çıkarım zor. Kullanıcının seçtiği zorluk otomatik değiştirilmez. İnsan zorluğunun kesin ölçümü değildir; satır olasılıklarını tam değerlendiren motor bazı karmaşık çıkarımları ortak hücre olarak sınıflandırabilir.
- İlerleyemeyen veya süresi dolan rapora zorluk atanmaz. İlerleyememek tahmin gerektiğini kanıtlamaz.
- Mantıksal analiz için toplam 2 saniye sınırı vardır; mevcut tek çözüm araması ayrıca en fazla 5 saniyedir. İşlem eşzamanlı olduğundan bu sırada arayüz kısa süre bekleyebilir.
- Doluluk %10 altında / %90 üstünde ve dolu piksellerin en az %25'i aynı renkte dört yönlü komşusuz olduğunda uyarı verilir (tekil piksel kontrolü en az 5 dolu hücrede). Bunlar sanatsal tercihlere de uyabilir; resmi değiştirmez veya kaydı engellemez.
- Çizim veya metadata değişince eski kalite raporu geçersizleşir.
- Öğretici sırası korunur: dolu blok → boşluk → renkli aynı renk boşluğu → farklı renklerin bitişmesi. Dört dersin tahminsiz çözülebilirliği kalite motoruyla test edilir. Raporlar için öğretim sıralama anahtarı da sağlanır; kütüphane sırası değiştirilmez.
- Kayıt biçimi ve mevcut oyuncu verileri değişmez.

Doğrulama: tüm pytest paketi ve Ruff; renkli bitişme, belirsiz çözüm, süre sınırı, gürültü uyarısı, öğretici dersleri ve editör raporunun geçersizleşmesi.
