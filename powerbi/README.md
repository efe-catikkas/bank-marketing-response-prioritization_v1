# Power BI Dosya Alanı

Bu klasör, tamamlanan `.pbix` dosyasının repository içinde tutulacağı alandır.

Önerilen dosya adı:

```text
bank_marketing_response_prioritization_dashboard.pbix
```

Dashboard oluşturulurken ana dinamik kaynak olarak:

```text
../outputs/powerbi/powerbi_scored_test.csv
```

kullanılmalıdır. Yardımcı tabloların açıklamaları `../docs/powerbi_tables.md`, üç sayfalık tasarım ve DAX rehberi `../docs/powerbi_dashboard_guide.md` dosyasındadır.

Bu final pakette `.pbix` bulunmamaktadır; yalnızca Python tarafından üretilen ve dashboard'a hazır CSV altyapısı yer almaktadır.
