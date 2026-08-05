# Power BI Dashboard Rehberi

Dashboard, üç sayfada iş sorusu → kayıt profili → model güvenilirliği akışını takip edecek şekilde tasarlanmalıdır.

## Sayfa 1 — Temas Önceliklendirme Özeti

**Cevaplanacak soru:** Sınırlı kapasitede kaç kayıt değerlendirilmelidir ve model rastgele seçime göre ne kadar iyileşme sağlamaktadır?

### KPI kartları

- Toplam test kaydı
- Test genel yanıt oranı
- Top %20 seçilen kayıt
- Top %20 yanıt oranı
- Capture@20
- Lift@20
- Beklenen ek olumlu kayıt

### Görseller

- Kapasite oranına göre seçilen grup yanıt oranı
- Kapasite oranına göre capture
- Dönem bazında yanıt oranı
- Öncelik bandı dağılımı

### Filtreler

- Kampanya dönemi
- Temas kanalı
- Kapasite senaryosu

## Sayfa 2 — Öncelikli Kayıtların Profili

**Cevaplanacak soru:** Modelin üst sıralara taşıdığı kayıtların profili genel test kitlesinden nasıl farklılaşmaktadır?

### Filtreler

- Öncelik bandı
- Kampanya dönemi
- Kanal
- Daha önce temas durumu

### KPI kartları

- Seçili kayıt sayısı
- Olumlu kayıt sayısı
- Yanıt oranı
- Ortalama öncelik skoru

### Görseller

- Mesleğe göre kayıt hacmi ve yanıt oranı
- Önceki kampanya sonucuna göre yanıt oranı
- Kanala göre yanıt oranı
- Temas sayısı bandına göre yanıt oranı
- Yaş bandına göre kayıt hacmi ve yanıt oranı
- Eğitime göre kayıt hacmi ve yanıt oranı

Yanıt oranı tek başına gösterilmemelidir; küçük hacimli segmentlerin yanıltıcı görünmemesi için kayıt sayısı ve `small_sample_flag` bilgisi tooltip veya tablo içerisinde gösterilmelidir.

## Sayfa 3 — Model ve Veri Güvenilirliği

**Cevaplanacak soru:** Model nasıl seçildi, ne kadar ayrıştırıyor ve hangi sınırlılıklar altında kullanılmalıdır?

### Görseller

- Validation model karşılaştırması
- ROC-AUC ve PR-AUC kartları
- Permutation importance
- Confusion matrix
- Training / validation / test dönem profili

### Açıklama kutuları

- `duration` neden çıkarıldı?
- Makroekonomik alanlar neden ana modelde kullanılmadı?
- Skor neden kesin satın alma olasılığı değildir?
- Segment sonuçları neden nedensel politika değildir?
- Test baz oranı neden training oranından farklıdır?
- Top %20 neden gerçek optimum kapasite değildir?

## Temel DAX örnekleri

Ana tablo adı `ScoredTest` varsayılmıştır.

```DAX
Toplam Kayıt =
COUNTROWS(ScoredTest)
```

```DAX
Olumlu Kayıt =
SUM(ScoredTest[y_binary])
```

```DAX
Yanıt Oranı =
DIVIDE([Olumlu Kayıt], [Toplam Kayıt])
```

```DAX
Top 20 Kayıt =
CALCULATE(
    [Toplam Kayıt],
    ScoredTest[is_top_20] = 1
)
```

```DAX
Top 20 Olumlu Kayıt =
CALCULATE(
    [Olumlu Kayıt],
    ScoredTest[is_top_20] = 1
)
```

```DAX
Top 20 Yanıt Oranı =
DIVIDE([Top 20 Olumlu Kayıt], [Top 20 Kayıt])
```

Sabit nihai Lift@20 ve beklenen ek olumlu kayıt KPI'ları için `powerbi_summary_metrics.csv` kullanılması daha güvenlidir.

## İsimlendirme

`response_score` alanı Power BI'da **Öncelik Skoru**, **Model Sıralama Skoru** veya **Yanıt Eğilimi Skoru** olarak gösterilmelidir. “Satın alma olasılığı” adı kullanılmamalıdır.
