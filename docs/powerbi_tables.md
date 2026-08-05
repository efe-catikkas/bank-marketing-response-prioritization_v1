# Power BI Çıktı Tabloları

Power BI için kullanılacak dosyalar `outputs/powerbi/` klasöründedir.

## Ana tablo: `powerbi_scored_test.csv`

Untouched test dönemindeki kayıt düzeyinde skorlanmış temas kayıtlarıdır. Dinamik filtreleme ve segment görselleri için ana kaynaktır.

### Kimlik ve dönem

- `record_id`: Teknik kayıt numarası
- `campaign_period_id`: Kronolojik kampanya dönem bloğu
- `month`, `day_of_week`: Kaynak dönem/temas bağlamı

### Model ve öncelik

- `model_name`: Seçilen model
- `response_score`: Göreli model sıralama skoru; kesin satın alma olasılığı değildir
- `predicted_response_at_050`: 0,50 eşik tahmini
- `rank_within_period`: Aynı dönem içindeki sıra
- `percentile_within_period`: Aynı dönem içindeki yüzdelik sıra
- `priority_band`: İlk %10 / İkinci %10 / Diğer %80
- `priority_band_sort`: Görsel sıralama alanı
- `is_top_10`, `is_top_20`: Öncelik göstergeleri

### Gerçek sonuç

- `y`, `y_binary`: Retrospektif gerçek yanıt
- `response_label`: Olumlu / Olumsuz

### Profil alanları

- `age`, `age_band`, `age_band_sort`
- `job`, `job_tr`
- `education`, `education_tr`
- `contact`, `contact_tr`
- `campaign`, `campaign_bucket`, `campaign_bucket_sort`
- `poutcome`, `poutcome_tr`
- `previously_contacted`, `previously_contacted_tr`

Power BI'da `age_band`, `campaign_bucket` ve `priority_band` alanları ilgili `_sort` sütunlarıyla sıralanmalıdır.

## `powerbi_summary_metrics.csv`

Seçilen modelin untouched test özetidir. Sabit yönetici KPI kartlarında kullanılabilir.

## `powerbi_model_comparison.csv`

Logistic Regression ve Random Forest modellerinin validation sonuçlarını içerir. Model seçimi test verisinden önce bu tabloya göre yapılmıştır.

## `powerbi_capacity_scenarios.csv`

Her test kampanya döneminde ayrı sıralama yapılarak %5–%50 kapasite senaryolarını içerir.

- `response_rate`: Seçilen grubun yanıt oranı
- `capture`: Bütün olumlu kayıtların seçilen gruptaki payı
- `lift`: Seçilen grup yanıt oranı / genel test yanıt oranı
- `expected_extra_positive`: Dönem bazlı rastgele seçim beklentisine göre retrospektif fark

## `powerbi_feature_importance.csv`

Seçilen modelin validation bölümündeki permutation importance sonuçlarıdır. Nedensellik veya operasyon politikası önerisi değildir.

## `powerbi_period_profile.csv`

Kampanya dönemlerinin kayıt sayısı, olumlu yanıt oranı ve training/validation/test bölümünü gösterir.

## `powerbi_split_summary.csv`

Training, validation ve test büyüklüklerini ve hedef oranlarını içerir.

## `powerbi_confusion_matrix.csv`

0,50 sınıf eşiğindeki untouched test confusion matrix değerlerini uzun tablo formatında içerir. Kapasite kararı bu eşikle değil, skor sıralamasıyla verilmektedir.

## `powerbi_segment_profile.csv`

Untouched test bölümünde her segment için:

- kayıt ve olumlu/olumsuz kayıt sayısı,
- yanıt oranı,
- kayıt ve olumlu yanıt payı,
- genel test ortalamasına göre lift,
- düşük örneklem uyarısı

alanlarını içerir.

## `powerbi_segment_profile_by_priority.csv`

Aynı segment metriklerini İlk %10, İkinci %10 ve Diğer %80 öncelik bantlarında ayrı üretir. Önceliklendirilen kayıt profilini genel kitleyle karşılaştırmak için kullanılabilir.

## `powerbi_age_education_profile.csv`

Yaş bandı × eğitim kırılımında kayıt hacmi ve yanıt oranını içerir. Matris veya heatmap benzeri görseller için hazırlanmıştır.
