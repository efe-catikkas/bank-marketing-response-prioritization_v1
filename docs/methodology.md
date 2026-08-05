# Metodoloji ve Teknik Kararlar

## 1. Tahmin ve kullanım anı

Çalışma, kampanyadan aylar önce müşteri seçen production sistem olarak değil; planlanmış temas girişiminden hemen önce kayıtları dönem içinde sıralayan retrospektif bir portföy örneği olarak yorumlanır.

## 2. Neden random split kullanılmadı?

Kaynak dosya kronolojik sıradadır ve kampanya koşulları zaman içinde değişmektedir. Modeller tam dönem bloklarından oluşan training ve validation bölümlerinde karşılaştırılmış; en güncel dönemler untouched test için saklanmıştır.

- Training: dönem 1–8
- Validation: dönem 9–10
- Test: dönem 11–26

Test bölümü model, feature veya eşik kararını değiştirmek için kullanılmamıştır.

## 3. Feature politikası

- `duration`: Görüşme tamamlandıktan sonra oluştuğu için leakage kabul edilmiştir.
- `pdays`: `999` sentinel değeri ve tam zaman bağlamının belirsizliği nedeniyle kullanılmamıştır.
- Makroekonomik alanlar: Dönemi güçlü biçimde temsil edebileceği ve farklı döneme taşınabilirliği azaltabileceği için ana modelden çıkarılmıştır.
- `campaign`, `contact`, `month`, `day_of_week`: Planlanan temas anında bilindiği varsayılan koşullu alanlardır.

Ayrıntılar `model_feature_policy.csv` dosyasındadır.

## 4. Neden yalnızca iki model var?

Amaç model sayısını artırmak değil, açıklanabilir bir baseline ile daha esnek bir ağaç modelini karşılaştırmaktır:

- Logistic Regression
- Random Forest

Kapsamlı hiperparametre optimizasyonu yapılmamış; aşırı karmaşıklığı sınırlayan tek bir manuel yapılandırma kullanılmıştır.

## 5. Neden model seçimi Lift@20 ile yapıldı?

Projenin iş sorusu, sınırlı kapasitede listenin üst bölümündeki olumlu yanıt yoğunluğudur. Bu nedenle birincil validation ölçütü Lift@20, destek metriği PR-AUC olarak belirlenmiştir.

Random Forest validation Lift@20 sonucunda önde olduğu için seçilmiş; iki model arasında kesin veya büyük üstünlük iddia edilmemiştir.

## 6. Neden kapasite dönem içinde hesaplanıyor?

Her kampanya döneminin hacmi ve baz yanıt oranı farklı olabilir. Bu nedenle kayıtlar bütün test verisinde global olarak değil, kendi dönemleri içinde sıralanmıştır. Her kapasite oranında dönem başına en az bir kayıt seçilir.

## 7. Neden permutation importance kullanıldı?

Random Forest’ın yerleşik Gini önemleri kategori sayısından etkilenebilir. Seçilen validation modeli üzerinde PR-AUC skorlu standart permutation importance kullanılmıştır. Sonuç nedensellik değildir.

## 8. Segment analizi neden untouched test üzerinde yapıldı?

Segment profili, final değerlendirme dönemindeki gerçek sonuçları ve modelin öncelik bantlarını açıklamak amacıyla hazırlanmıştır. Meslek, kanal, önceki kampanya, temas sayısı, yaş ve eğitim boyutlarında hacim ile yanıt oranı birlikte gösterilir.

- Segment bulguları gözlemseldir.
- 30’dan az kayıt içeren segmentler düşük örneklem olarak işaretlenir.
- Hassas olabilecek profil alanları otomatik dışlama veya erişim kısıtlama kuralı değildir.

## 9. Skorun yorumu

`response_score`, kalibre edilmiş kesin satın alma olasılığı değildir. Dönem içindeki göreli öncelik sırasını üretmek için kullanılır.

## 10. Sonuçların sınırı

Top %20 kapasite, gerçek çağrı merkezi optimumu değildir. Maliyet, getiri, kontrol grubu ve deney tasarımı bulunmadığı için ROI veya gerçek uplift sonucu üretilmemiştir. “Beklenen ek olumlu kayıt”, aynı dönemlerde eşit kapasitedeki rastgele seçimin retrospektif beklentisiyle karşılaştırmadır.
