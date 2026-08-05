#!/usr/bin/env python
# coding: utf-8

# # Bank Marketing: Kronolojik Yanıt Tahmini, Temas Önceliklendirmesi ve Segment Profili
# 
# Bu çalışma, UCI Bank Marketing temas kayıtlarında olumlu yanıt eğilimi yüksek kayıtları sıralamak ve model sonuçlarını müşteri/kampanya profilleriyle açıklamak için hazırlanmış sade bir eğitim ve portföy projesidir.
# 
# **Temel soru:** Her kampanya döneminde yalnızca belirli sayıda kayıt işleme alınabiliyorsa, hangi kayıtlar önce değerlendirilmelidir ve önceliklendirilen kayıtların profili nasıldır?
# 
# ### Ana metodoloji
# 
# - Dosyanın kronolojik sırası korunur.
# - Tam ay blokları **training → validation → test** olarak ayrılır.
# - Yalnızca **Logistic Regression** ve **Random Forest** karşılaştırılır.
# - Model seçimi validation bölümündeki **Lift@20** sonucuna göre yapılır; PR-AUC destek metriğidir.
# - Seçilen model training ve validation birleştirilerek yeniden eğitilir ve en güncel test bölümünde yalnızca bir kez değerlendirilir.
# - Kapasite hesapları her kampanya dönemi içinde ayrı sıralama yapılarak oluşturulur.
# - Untouched test bölümünde meslek, kanal, önceki kampanya, temas sayısı, yaş ve eğitim profilleri ayrıca raporlanır.
# - Segment bulguları **gözlemseldir**; nedensel kampanya politikası olarak sunulmaz.
# 
# Bu çalışma gerçek banka verisi, canlı CRM sistemi veya production model raporu değildir.

# ## 1. Kütüphaneler, proje yolları ve sabit kararlar
# 
# Model sayısı ve ayarlar bilinçli olarak sınırlı tutulmuştur. Kapsamlı hiperparametre optimizasyonu yapılmamış; açıklanabilir bir baseline ile kontrollü bir ağaç modeli karşılaştırılmıştır.

# In[1]:


from pathlib import Path
import platform

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 160)

candidate_roots = [Path.cwd(), Path.cwd().parent]
PROJECT_ROOT = next(
    (root for root in candidate_roots if (root / "data" / "bank-additional-full.csv").exists()),
    None,
)
if PROJECT_ROOT is None:
    raise FileNotFoundError(
        "data/bank-additional-full.csv bulunamadı. Proje klasör yapısını koruyarak notebook'u çalıştırın."
    )

DATA_PATH = PROJECT_ROOT / "data" / "bank-additional-full.csv"
METRICS_DIR = PROJECT_ROOT / "outputs" / "metrics"
POWERBI_DIR = PROJECT_ROOT / "outputs" / "powerbi"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
METRICS_DIR.mkdir(parents=True, exist_ok=True)
POWERBI_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
CLASSIFICATION_THRESHOLD = 0.50
TOP_K_RATE = 0.20
CAPACITY_RATES = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50)

# Tam dönem blokları: training 1–8, validation 9–10, test 11–26.
TRAIN_PERIOD_END = 8
VALIDATION_PERIOD_END = 10

print(f"Python: {platform.python_version()}")
print(f"Proje kökü: {PROJECT_ROOT.resolve()}")
print(f"Veri: {DATA_PATH.resolve()}")


# ## 2. Veri yükleme, kalite kontrolleri ve kampanya dönemleri
# 
# Veri setinde güvenilir müşteri kimliği bulunmadığı için her satır **kampanya temas kaydı** olarak değerlendirilir. Tam duplicate satırlar, birebir aynı gözlemin farklı veri bölümlerine düşmesini önlemek amacıyla modelleme öncesinde çıkarılır.
# 
# Dosya kronolojik sırada olduğu için, ay değiştiğinde yeni bir `campaign_period_id` oluşturulur. Bu teknik alan yalnızca kronolojik ayrım ve dönem içi kapasite hesabında kullanılır; modele verilmez.

# In[2]:


REQUIRED_COLUMNS = {
    "age", "job", "marital", "education", "default", "housing", "loan",
    "contact", "month", "day_of_week", "duration", "campaign", "pdays",
    "previous", "poutcome", "emp.var.rate", "cons.price.idx",
    "cons.conf.idx", "euribor3m", "nr.employed", "y",
}

raw_df = pd.read_csv(DATA_PATH, sep=";")
missing_columns = REQUIRED_COLUMNS.difference(raw_df.columns)
if missing_columns:
    raise ValueError(f"Eksik sütunlar: {sorted(missing_columns)}")

raw_record_count = len(raw_df)
exact_duplicate_count = int(raw_df.duplicated().sum())

df = raw_df.drop_duplicates().reset_index(drop=True).copy()
df.insert(0, "record_id", np.arange(1, len(df) + 1))
df["y_binary"] = df["y"].map({"no": 0, "yes": 1}).astype(int)
df["previously_contacted"] = np.where(df["pdays"].eq(999), "no", "yes")
df["campaign_period_id"] = df["month"].ne(df["month"].shift()).cumsum().astype(int)

quality_summary = pd.DataFrame({
    "metric": [
        "Ham kayıt sayısı",
        "Tam duplicate satır",
        "Modelleme kayıt sayısı",
        "Olumlu kayıt",
        "Olumsuz kayıt",
        "Olumlu yanıt oranı",
        "Unknown içeren hücre",
        "Kampanya dönem bloğu",
    ],
    "value": [
        raw_record_count,
        exact_duplicate_count,
        len(df),
        int(df["y_binary"].sum()),
        int((1 - df["y_binary"]).sum()),
        df["y_binary"].mean(),
        int(df.astype(str).eq("unknown").sum().sum()),
        int(df["campaign_period_id"].nunique()),
    ],
})

period_summary = (
    df.groupby(["campaign_period_id", "month"], as_index=False, observed=True)
      .agg(
          record_count=("record_id", "size"),
          positive_count=("y_binary", "sum"),
          positive_rate=("y_binary", "mean"),
      )
)

display(quality_summary)
display(period_summary)


# ## 3. Kısa keşifsel analiz
# 
# Bu bölüm modelden önce hedef dağılımını, `unknown` değerlerini, temel sayısal alanları ve kampanya dönemleri arasındaki yanıt oranı değişimini görünür hale getirir. Daha ayrıntılı müşteri ve kampanya profili, yalnızca untouched test bölümünde model sonuçları üretildikten sonra incelenir.

# In[3]:


fig, ax = plt.subplots(figsize=(6, 4))
df["y"].value_counts().reindex(["no", "yes"]).plot(kind="bar", ax=ax)
ax.set_title("Hedef sınıf dağılımı")
ax.set_xlabel("Yanıt")
ax.set_ylabel("Kayıt sayısı")
ax.tick_params(axis="x", rotation=0)
plt.tight_layout()
plt.show()

categorical_columns = [
    "job", "marital", "education", "default", "housing", "loan",
    "contact", "month", "day_of_week", "poutcome",
]
unknown_summary = pd.DataFrame({
    "column": categorical_columns,
    "unknown_count": [int(df[column].eq("unknown").sum()) for column in categorical_columns],
})
unknown_summary["unknown_rate"] = unknown_summary["unknown_count"] / len(df)
unknown_summary = unknown_summary.sort_values("unknown_count", ascending=False).reset_index(drop=True)
display(unknown_summary)

numeric_profile = df[["age", "campaign", "previous"]].describe().T
numeric_profile["median"] = df[["age", "campaign", "previous"]].median()
display(numeric_profile)

profile_tables = {}
for column in ["poutcome", "contact", "previously_contacted"]:
    profile_tables[column] = (
        df.groupby(column, observed=True)
          .agg(record_count=("record_id", "size"), response_rate=("y_binary", "mean"))
          .sort_values("response_rate", ascending=False)
    )
    display(Markdown(f"### `{column}` kırılımı"))
    display(profile_tables[column])

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(period_summary["campaign_period_id"], period_summary["positive_rate"], marker="o")
ax.set_title("Kampanya dönemlerine göre olumlu yanıt oranı")
ax.set_xlabel("Kampanya dönem bloğu")
ax.set_ylabel("Olumlu yanıt oranı")
plt.tight_layout()
plt.show()


# ## 4. Tahmin anı, feature politikası ve kronolojik ayrım
# 
# Model, kampanyadan aylar önce müşteri seçen bir sistem olarak değil; planlanmış temas girişiminden hemen önce kayıtları sıralayan retrospektif bir örnek olarak yorumlanır.
# 
# - `duration`: görüşme tamamlandıktan sonra oluştuğu için leakage.
# - `pdays`: `999` sentinel değeri ve eksik zaman bağlamı nedeniyle kullanılmaz.
# - Makroekonomik alanlar: dönem koşullarını güçlü biçimde temsil edebileceği ve farklı döneme taşınabilirliği azaltabileceği için ana modelden çıkarılır.
# - `campaign`, `contact`, `month`, `day_of_week`: planlanan temas anında bilindiği varsayılan koşullu alanlardır.

# In[4]:


NUMERIC_FEATURES = ["age", "campaign", "previous"]
CATEGORICAL_FEATURES = [
    "job", "marital", "education", "default", "housing", "loan",
    "contact", "month", "day_of_week", "poutcome", "previously_contacted",
]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

EXCLUDED_FEATURES = pd.DataFrame([
    {"feature": "duration", "reason": "Görüşme sonrasında oluşur; tahmin anında bilinmez."},
    {"feature": "pdays", "reason": "999 sentinel değeri ve tam zaman bilgisinin belirsizliği."},
    {"feature": "emp.var.rate", "reason": "Makroekonomik dönem vekili ve taşınabilirlik riski."},
    {"feature": "cons.price.idx", "reason": "Makroekonomik dönem vekili ve taşınabilirlik riski."},
    {"feature": "cons.conf.idx", "reason": "Makroekonomik dönem vekili ve taşınabilirlik riski."},
    {"feature": "euribor3m", "reason": "Makroekonomik dönem vekili ve taşınabilirlik riski."},
    {"feature": "nr.employed", "reason": "Makroekonomik dönem vekili ve taşınabilirlik riski."},
])

train_df = df.loc[df["campaign_period_id"].le(TRAIN_PERIOD_END)].copy()
validation_df = df.loc[
    df["campaign_period_id"].gt(TRAIN_PERIOD_END)
    & df["campaign_period_id"].le(VALIDATION_PERIOD_END)
].copy()
test_df = df.loc[df["campaign_period_id"].gt(VALIDATION_PERIOD_END)].copy()

if not (
    train_df["campaign_period_id"].max() < validation_df["campaign_period_id"].min()
    and validation_df["campaign_period_id"].max() < test_df["campaign_period_id"].min()
):
    raise AssertionError("Kronolojik split sırası bozuldu.")

split_summary = pd.DataFrame([
    {
        "split": "Training",
        "period_start": int(train_df["campaign_period_id"].min()),
        "period_end": int(train_df["campaign_period_id"].max()),
        "record_count": len(train_df),
        "positive_count": int(train_df["y_binary"].sum()),
        "positive_rate": train_df["y_binary"].mean(),
    },
    {
        "split": "Validation",
        "period_start": int(validation_df["campaign_period_id"].min()),
        "period_end": int(validation_df["campaign_period_id"].max()),
        "record_count": len(validation_df),
        "positive_count": int(validation_df["y_binary"].sum()),
        "positive_rate": validation_df["y_binary"].mean(),
    },
    {
        "split": "Test",
        "period_start": int(test_df["campaign_period_id"].min()),
        "period_end": int(test_df["campaign_period_id"].max()),
        "record_count": len(test_df),
        "positive_count": int(test_df["y_binary"].sum()),
        "positive_rate": test_df["y_binary"].mean(),
    },
])

display(pd.DataFrame({"model_feature": MODEL_FEATURES}))
display(EXCLUDED_FEATURES)
display(split_summary)


# ## 5. Pipeline, iki model ve dönem içi kapasite fonksiyonları
# 
# - **Logistic Regression:** açıklanabilir baseline.
# - **Random Forest:** doğrusal olmayan ilişkileri yakalayabilen challenger.
# 
# Ayarlar kapsamlı tuning sonucu değildir. Aşırı karmaşıklığı sınırlayan tek bir manuel yapılandırma kullanılır ve optimum olduğu iddia edilmez.

# In[5]:


def make_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_pipeline = Pipeline(numeric_steps)
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer([
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
    ])

MODEL_TEMPLATES = {
    "Logistic Regression": Pipeline([
        ("preprocessor", make_preprocessor(scale_numeric=True)),
        ("model", LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=RANDOM_STATE,
        )),
    ]),
    "Random Forest": Pipeline([
        ("preprocessor", make_preprocessor(scale_numeric=False)),
        ("model", RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=10,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ]),
}


def build_period_capacity_table(evaluation_df: pd.DataFrame, scores, capacity_rates) -> pd.DataFrame:
    """Her kampanya döneminde kayıtları ayrı sıralar ve toplam kapasite metriklerini üretir."""
    scored = evaluation_df[["record_id", "campaign_period_id", "y_binary"]].copy()
    scored["response_score"] = np.asarray(scores)

    rows = []
    for rate in capacity_rates:
        selected_indices = []
        expected_random_positive = 0.0

        for _, period_group in scored.groupby("campaign_period_id", sort=True):
            selected_n = max(1, int(np.ceil(rate * len(period_group))))
            selected_period = (
                period_group.sort_values(
                    ["response_score", "record_id"],
                    ascending=[False, True],
                    kind="mergesort",
                )
                .head(selected_n)
            )
            selected_indices.extend(selected_period.index.tolist())
            expected_random_positive += selected_n * period_group["y_binary"].mean()

        selected = scored.loc[selected_indices]
        base_rate = scored["y_binary"].mean()
        response_rate = selected["y_binary"].mean()
        selected_positive = int(selected["y_binary"].sum())

        rows.append({
            "capacity_rate": rate,
            "selected_count": int(len(selected)),
            "selected_positive": selected_positive,
            "base_rate": base_rate,
            "response_rate": response_rate,
            "capture": selected_positive / scored["y_binary"].sum(),
            "lift": response_rate / base_rate,
            "expected_random_positive": expected_random_positive,
            "expected_extra_positive": selected_positive - expected_random_positive,
        })

    return pd.DataFrame(rows)


def evaluate_pipeline(model_name: str, pipeline: Pipeline, fit_df: pd.DataFrame, evaluation_df: pd.DataFrame):
    fitted = clone(pipeline)
    fitted.fit(fit_df[MODEL_FEATURES], fit_df["y_binary"])

    scores = fitted.predict_proba(evaluation_df[MODEL_FEATURES])[:, 1]
    predictions = (scores >= CLASSIFICATION_THRESHOLD).astype(int)
    capacity_20 = build_period_capacity_table(evaluation_df, scores, [TOP_K_RATE]).iloc[0]

    metrics = {
        "model": model_name,
        "accuracy": accuracy_score(evaluation_df["y_binary"], predictions),
        "precision": precision_score(evaluation_df["y_binary"], predictions, zero_division=0),
        "recall": recall_score(evaluation_df["y_binary"], predictions, zero_division=0),
        "f1": f1_score(evaluation_df["y_binary"], predictions, zero_division=0),
        "roc_auc": roc_auc_score(evaluation_df["y_binary"], scores),
        "pr_auc": average_precision_score(evaluation_df["y_binary"], scores),
        "selected_count_at_20": int(capacity_20["selected_count"]),
        "response_rate_at_20": capacity_20["response_rate"],
        "capture_at_20": capacity_20["capture"],
        "lift_at_20": capacity_20["lift"],
        "expected_extra_positive_at_20": capacity_20["expected_extra_positive"],
    }
    return fitted, scores, predictions, metrics


# ## 6. Validation bölümünde model karşılaştırması ve seçim
# 
# Birincil seçim ölçütü **Lift@20**'dir. Lift sonuçları yakınsa PR-AUC destek metriği olarak kullanılır. Test bölümü model seçimine dahil edilmez.

# In[6]:


validation_models = {}
validation_scores = {}
comparison_rows = []

for model_name, template in MODEL_TEMPLATES.items():
    fitted, scores, predictions, metrics = evaluate_pipeline(
        model_name=model_name,
        pipeline=template,
        fit_df=train_df,
        evaluation_df=validation_df,
    )
    validation_models[model_name] = fitted
    validation_scores[model_name] = scores
    comparison_rows.append(metrics)

model_comparison = (
    pd.DataFrame(comparison_rows)
      .sort_values(["lift_at_20", "pr_auc"], ascending=False)
      .reset_index(drop=True)
)
model_comparison.insert(0, "evaluation_set", "Validation")

display(model_comparison.round(4))

SELECTED_MODEL_NAME = model_comparison.loc[0, "model"]
SELECTED_VALIDATION_MODEL = validation_models[SELECTED_MODEL_NAME]
SELECTED_VALIDATION_SCORES = validation_scores[SELECTED_MODEL_NAME]

lift_gap = model_comparison.loc[0, "lift_at_20"] - model_comparison.loc[1, "lift_at_20"]
print(f"Seçilen model: {SELECTED_MODEL_NAME}")
print(f"İlk iki model arasındaki validation Lift@20 farkı: {lift_gap:.4f}")

fig, ax = plt.subplots(figsize=(8, 4))
model_comparison.set_index("model")[["lift_at_20", "capture_at_20", "pr_auc"]].plot(kind="bar", ax=ax)
ax.set_title("Validation model karşılaştırması")
ax.set_xlabel("")
ax.set_ylabel("Metrik")
ax.tick_params(axis="x", rotation=0)
plt.tight_layout()
plt.show()


# ## 7. Validation üzerinde standart permutation importance
# 
# Özellik önemleri final test kullanılmadan, seçilen modelin validation performansı üzerinden hesaplanır. Permutation importance bir alanın değerleri karıştırıldığında PR-AUC'nin ortalama ne kadar değiştiğini gösterir; nedensellik değildir.

# In[7]:


permutation_result = permutation_importance(
    SELECTED_VALIDATION_MODEL,
    validation_df[MODEL_FEATURES],
    validation_df["y_binary"],
    scoring="average_precision",
    n_repeats=5,
    random_state=RANDOM_STATE,
    n_jobs=-1,
)

feature_importance = pd.DataFrame({
    "feature": MODEL_FEATURES,
    "importance_mean": permutation_result.importances_mean,
    "importance_std": permutation_result.importances_std,
    "scoring": "average_precision",
    "evaluation_set": "Validation",
}).sort_values("importance_mean", ascending=False).reset_index(drop=True)

display(feature_importance.round(4))

fig, ax = plt.subplots(figsize=(8, 5))
feature_importance.head(12).sort_values("importance_mean").plot(
    kind="barh", x="feature", y="importance_mean", legend=False, ax=ax
)
ax.set_title(f"Validation permutation importance — {SELECTED_MODEL_NAME}")
ax.set_xlabel("PR-AUC ortalama değişimi")
ax.set_ylabel("")
plt.tight_layout()
plt.show()


# ## 8. Seçilen modelin untouched test değerlendirmesi
# 
# Seçilen model, training ve validation verileri birleştirilerek yeniden eğitilir. En güncel test dönemi bu aşamaya kadar model seçimi veya feature kararı için kullanılmamıştır.

# In[8]:


train_validation_df = pd.concat([train_df, validation_df], axis=0).sort_index()
final_pipeline = clone(MODEL_TEMPLATES[SELECTED_MODEL_NAME])
final_pipeline.fit(train_validation_df[MODEL_FEATURES], train_validation_df["y_binary"])

test_scores = final_pipeline.predict_proba(test_df[MODEL_FEATURES])[:, 1]
test_predictions = (test_scores >= CLASSIFICATION_THRESHOLD).astype(int)
capacity_scenarios = build_period_capacity_table(test_df, test_scores, CAPACITY_RATES)
top20_row = capacity_scenarios.loc[np.isclose(capacity_scenarios["capacity_rate"], TOP_K_RATE)].iloc[0]

test_base_rate = test_df["y_binary"].mean()
majority_baseline_accuracy = max(test_base_rate, 1 - test_base_rate)

final_test_metrics = {
    "selected_model": SELECTED_MODEL_NAME,
    "evaluation_set": "Untouched chronological test",
    "test_record_count": int(len(test_df)),
    "test_positive_rate": test_base_rate,
    "accuracy": accuracy_score(test_df["y_binary"], test_predictions),
    "majority_baseline_accuracy": majority_baseline_accuracy,
    "precision": precision_score(test_df["y_binary"], test_predictions, zero_division=0),
    "recall": recall_score(test_df["y_binary"], test_predictions, zero_division=0),
    "f1": f1_score(test_df["y_binary"], test_predictions, zero_division=0),
    "roc_auc": roc_auc_score(test_df["y_binary"], test_scores),
    "pr_auc": average_precision_score(test_df["y_binary"], test_scores),
    "selected_count_at_20": int(top20_row["selected_count"]),
    "response_rate_at_20": top20_row["response_rate"],
    "capture_at_20": top20_row["capture"],
    "lift_at_20": top20_row["lift"],
    "expected_extra_positive_at_20": top20_row["expected_extra_positive"],
}
final_test_table = pd.DataFrame([final_test_metrics])

display(final_test_table.T.rename(columns={0: "value"}).round(4))
display(capacity_scenarios.round(4))

confusion = confusion_matrix(test_df["y_binary"], test_predictions)
confusion_table = pd.DataFrame(
    confusion,
    index=["Gerçek Olumsuz", "Gerçek Olumlu"],
    columns=["Tahmin Olumsuz", "Tahmin Olumlu"],
)
display(confusion_table)

fig, ax = plt.subplots(figsize=(5, 4))
ConfusionMatrixDisplay(confusion_matrix=confusion, display_labels=["Olumsuz", "Olumlu"]).plot(
    ax=ax, values_format="d"
)
ax.set_title(f"Test confusion matrix — {SELECTED_MODEL_NAME}")
plt.tight_layout()
plt.show()

fpr, tpr, _ = roc_curve(test_df["y_binary"], test_scores)
precision_curve, recall_curve, _ = precision_recall_curve(test_df["y_binary"], test_scores)

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(fpr, tpr, label=f"ROC-AUC = {final_test_metrics['roc_auc']:.3f}")
ax.plot([0, 1], [0, 1], linestyle="--")
ax.set_title("Test ROC eğrisi")
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.legend()
plt.tight_layout()
plt.show()

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(recall_curve, precision_curve, label=f"PR-AUC = {final_test_metrics['pr_auc']:.3f}")
ax.axhline(test_base_rate, linestyle="--", label=f"Test baz oran = {test_base_rate:.3f}")
ax.set_title("Test Precision–Recall eğrisi")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.legend()
plt.tight_layout()
plt.show()


# ## 9. Dönem içi sıralama ve zenginleştirilmiş Power BI kayıt tablosu
# 
# Öncelik bantları her kampanya döneminde ayrı hesaplanır:
# 
# - İlk %10
# - İkinci %10
# - Diğer %80
# 
# `response_score`, kalibre edilmiş kesin satın alma olasılığı değil; dönem içi sıralama skorudur.
# 
# Power BI tarafında tutarlı kullanım için yaş ve temas bantları, Türkçe kategori adları ve öncelik göstergeleri Python tarafında standartlaştırılır.

# In[9]:


scored_test = test_df[[
    "record_id", "campaign_period_id", "age", "job", "marital", "education",
    "default", "housing", "loan", "contact", "month", "day_of_week",
    "campaign", "previous", "poutcome", "previously_contacted", "y", "y_binary",
]].copy()
scored_test["model_name"] = SELECTED_MODEL_NAME
scored_test["response_score"] = test_scores
scored_test["predicted_response_at_050"] = test_predictions

ranked_groups = []
for _, period_group in scored_test.groupby("campaign_period_id", sort=True):
    ranked = period_group.sort_values(
        ["response_score", "record_id"],
        ascending=[False, True],
        kind="mergesort",
    ).copy()
    ranked["rank_within_period"] = np.arange(1, len(ranked) + 1)
    ranked["percentile_within_period"] = ranked["rank_within_period"] / len(ranked)

    top10_n = max(1, int(np.ceil(0.10 * len(ranked))))
    top20_n = max(1, int(np.ceil(0.20 * len(ranked))))
    ranked["priority_band"] = np.select(
        [
            ranked["rank_within_period"].le(top10_n),
            ranked["rank_within_period"].le(top20_n),
        ],
        ["İlk %10", "İkinci %10"],
        default="Diğer %80",
    )
    ranked_groups.append(ranked)

scored_test = pd.concat(ranked_groups, ignore_index=True)

# Power BI ve README için ortak profil alanları.
AGE_BINS = [0, 24, 34, 44, 54, 64, np.inf]
AGE_LABELS = ["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]
CAMPAIGN_BINS = [0, 1, 2, 3, 4, 5, np.inf]
CAMPAIGN_LABELS = ["1", "2", "3", "4", "5", "6+"]

scored_test["age_band"] = pd.cut(
    scored_test["age"],
    bins=AGE_BINS,
    labels=AGE_LABELS,
    include_lowest=True,
    ordered=True,
)
scored_test["campaign_bucket"] = pd.cut(
    scored_test["campaign"],
    bins=CAMPAIGN_BINS,
    labels=CAMPAIGN_LABELS,
    include_lowest=True,
    ordered=True,
)

scored_test["age_band_sort"] = scored_test["age_band"].map(
    {label: index + 1 for index, label in enumerate(AGE_LABELS)}
).astype("Int64")
scored_test["campaign_bucket_sort"] = scored_test["campaign_bucket"].map(
    {label: index + 1 for index, label in enumerate(CAMPAIGN_LABELS)}
).astype("Int64")
scored_test["priority_band_sort"] = scored_test["priority_band"].map(
    {"İlk %10": 1, "İkinci %10": 2, "Diğer %80": 3}
).astype("Int64")

scored_test["response_label"] = np.where(scored_test["y_binary"].eq(1), "Olumlu", "Olumsuz")
scored_test["is_top_10"] = scored_test["priority_band"].eq("İlk %10").astype(int)
scored_test["is_top_20"] = scored_test["percentile_within_period"].le(TOP_K_RATE).astype(int)

JOB_LABELS = {
    "admin.": "İdari çalışan",
    "blue-collar": "Mavi yaka",
    "entrepreneur": "Girişimci",
    "housemaid": "Ev hizmetleri",
    "management": "Yönetim",
    "retired": "Emekli",
    "self-employed": "Serbest çalışan",
    "services": "Hizmet çalışanı",
    "student": "Öğrenci",
    "technician": "Teknik personel",
    "unemployed": "İşsiz",
    "unknown": "Bilinmiyor",
}
EDUCATION_LABELS = {
    "basic.4y": "Temel eğitim - 4 yıl",
    "basic.6y": "Temel eğitim - 6 yıl",
    "basic.9y": "Temel eğitim - 9 yıl",
    "high.school": "Lise",
    "illiterate": "Okuryazar değil",
    "professional.course": "Mesleki eğitim",
    "university.degree": "Üniversite",
    "unknown": "Bilinmiyor",
}
CONTACT_LABELS = {"cellular": "Cep telefonu", "telephone": "Sabit telefon"}
POUTCOME_LABELS = {
    "success": "Başarılı",
    "failure": "Başarısız",
    "nonexistent": "Önceki kampanya yok",
}
PREVIOUS_CONTACT_LABELS = {"yes": "Daha önce temas edilmiş", "no": "İlk temas"}

scored_test["job_tr"] = scored_test["job"].map(JOB_LABELS).fillna(scored_test["job"])
scored_test["education_tr"] = scored_test["education"].map(EDUCATION_LABELS).fillna(scored_test["education"])
scored_test["contact_tr"] = scored_test["contact"].map(CONTACT_LABELS).fillna(scored_test["contact"])
scored_test["poutcome_tr"] = scored_test["poutcome"].map(POUTCOME_LABELS).fillna(scored_test["poutcome"])
scored_test["previously_contacted_tr"] = (
    scored_test["previously_contacted"].map(PREVIOUS_CONTACT_LABELS).fillna(scored_test["previously_contacted"])
)

period_profile = (
    df.groupby(["campaign_period_id", "month"], as_index=False, observed=True)
      .agg(
          record_count=("record_id", "size"),
          positive_count=("y_binary", "sum"),
          positive_rate=("y_binary", "mean"),
      )
)
period_profile["split"] = np.select(
    [
        period_profile["campaign_period_id"].le(TRAIN_PERIOD_END),
        period_profile["campaign_period_id"].le(VALIDATION_PERIOD_END),
    ],
    ["Training", "Validation"],
    default="Test",
)

confusion_long = pd.DataFrame([
    {"actual_class": "Olumsuz", "predicted_class": "Olumsuz", "record_count": int(confusion[0, 0])},
    {"actual_class": "Olumsuz", "predicted_class": "Olumlu", "record_count": int(confusion[0, 1])},
    {"actual_class": "Olumlu", "predicted_class": "Olumsuz", "record_count": int(confusion[1, 0])},
    {"actual_class": "Olumlu", "predicted_class": "Olumlu", "record_count": int(confusion[1, 1])},
])

display(scored_test.head())


# ## 10. Untouched test müşteri ve kampanya profili
# 
# Bu bölüm yalnızca final test dönemindeki gerçek sonuçları betimler. Meslek, kanal, önceki kampanya sonucu, temas sayısı, yaş ve eğitim grupları için kayıt hacmi ile yanıt oranı birlikte gösterilir.
# 
# - Bulgular **gözlemseldir** ve neden–sonuç ilişkisi kanıtlamaz.
# - Kayıt sayısı 30'un altında olan segmentler `small_sample_flag=True` ile işaretlenir.
# - Yaş ve diğer hassas olabilecek alanlar otomatik dışlama veya erişim kısıtlama kuralı olarak yorumlanmaz.
# - Power BI'da dinamik filtreleme için ana kaynak `powerbi_scored_test.csv` dosyasıdır; özet tablolar kontrol ve hazır görünüm amacıyla eklenmiştir.

# In[10]:


SEGMENT_DIMENSIONS = {
    "Meslek": "job_tr",
    "Kanal": "contact_tr",
    "Önceki Kampanya Sonucu": "poutcome_tr",
    "Temas Sayısı": "campaign_bucket",
    "Yaş Bandı": "age_band",
    "Eğitim": "education_tr",
}
DIMENSION_SORT = {dimension: index + 1 for index, dimension in enumerate(SEGMENT_DIMENSIONS)}
SEGMENT_ORDERS = {
    "Kanal": ["Cep telefonu", "Sabit telefon"],
    "Önceki Kampanya Sonucu": ["Başarılı", "Başarısız", "Önceki kampanya yok"],
    "Temas Sayısı": CAMPAIGN_LABELS,
    "Yaş Bandı": AGE_LABELS,
    "Eğitim": [
        "Okuryazar değil", "Temel eğitim - 4 yıl", "Temel eğitim - 6 yıl",
        "Temel eğitim - 9 yıl", "Lise", "Mesleki eğitim", "Üniversite", "Bilinmiyor",
    ],
    "Meslek": list(JOB_LABELS.values()),
}


def create_segment_summary(
    data: pd.DataFrame,
    dimension_name: str,
    column_name: str,
    priority_band: str | None = None,
) -> pd.DataFrame:
    analysis_data = data if priority_band is None else data.loc[data["priority_band"].eq(priority_band)]
    overall_response_rate = analysis_data["y_binary"].mean()
    total_positive = analysis_data["y_binary"].sum()

    summary = (
        analysis_data.groupby(column_name, observed=True, dropna=False)
        .agg(
            record_count=("record_id", "size"),
            positive_count=("y_binary", "sum"),
            response_rate=("y_binary", "mean"),
        )
        .reset_index()
        .rename(columns={column_name: "segment"})
    )
    summary["segment"] = summary["segment"].astype(str)
    summary["negative_count"] = summary["record_count"] - summary["positive_count"]
    summary["record_share"] = summary["record_count"] / len(analysis_data)
    summary["positive_share"] = np.where(
        total_positive > 0,
        summary["positive_count"] / total_positive,
        np.nan,
    )
    summary["overall_response_rate"] = overall_response_rate
    summary["lift_vs_overall"] = summary["response_rate"] / overall_response_rate
    summary["small_sample_flag"] = summary["record_count"].lt(30)
    summary["priority_band"] = "Tüm Test" if priority_band is None else priority_band
    summary.insert(0, "dimension", dimension_name)
    summary.insert(1, "dimension_sort", DIMENSION_SORT[dimension_name])

    order_map = {label: index + 1 for index, label in enumerate(SEGMENT_ORDERS[dimension_name])}
    summary["segment_sort"] = summary["segment"].map(order_map)
    fallback_start = len(order_map) + 1
    missing_sort = summary["segment_sort"].isna()
    if missing_sort.any():
        fallback = {
            label: fallback_start + index
            for index, label in enumerate(sorted(summary.loc[missing_sort, "segment"].unique()))
        }
        summary.loc[missing_sort, "segment_sort"] = summary.loc[missing_sort, "segment"].map(fallback)
    summary["segment_sort"] = summary["segment_sort"].astype(int)
    return summary


segment_profile = pd.concat(
    [
        create_segment_summary(scored_test, dimension_name, column_name)
        for dimension_name, column_name in SEGMENT_DIMENSIONS.items()
    ],
    ignore_index=True,
)

segment_profile_by_priority = pd.concat(
    [
        create_segment_summary(scored_test, dimension_name, column_name, priority_band)
        for priority_band in ["İlk %10", "İkinci %10", "Diğer %80"]
        for dimension_name, column_name in SEGMENT_DIMENSIONS.items()
    ],
    ignore_index=True,
)

age_education_profile = (
    scored_test.groupby(["age_band", "age_band_sort", "education_tr"], observed=True, dropna=False)
    .agg(
        record_count=("record_id", "size"),
        positive_count=("y_binary", "sum"),
        response_rate=("y_binary", "mean"),
    )
    .reset_index()
)
age_education_profile["negative_count"] = (
    age_education_profile["record_count"] - age_education_profile["positive_count"]
)
age_education_profile["small_sample_flag"] = age_education_profile["record_count"].lt(30)
age_education_profile["education_sort"] = age_education_profile["education_tr"].map(
    {label: index + 1 for index, label in enumerate(SEGMENT_ORDERS["Eğitim"])}
).astype("Int64")

for dimension in SEGMENT_DIMENSIONS:
    display(Markdown(f"### {dimension}"))
    display(
        segment_profile.loc[segment_profile["dimension"].eq(dimension)]
        .sort_values(["response_rate", "record_count"], ascending=[False, False])
        [["segment", "record_count", "positive_count", "response_rate", "lift_vs_overall", "small_sample_flag"]]
        .reset_index(drop=True)
        .round(4)
    )


def plot_segment_response(dimension: str, filename: str, horizontal: bool = True) -> None:
    plot_data = (
        segment_profile.loc[segment_profile["dimension"].eq(dimension)]
        .sort_values("response_rate", ascending=True if horizontal else False)
        .copy()
    )
    plot_data["label_with_n"] = plot_data.apply(
        lambda row: f"{row['segment']} (n={int(row['record_count']):,})", axis=1
    )
    overall_rate = float(plot_data["overall_response_rate"].iloc[0])

    if horizontal:
        fig, ax = plt.subplots(figsize=(8, max(3.5, 0.42 * len(plot_data) + 1.2)))
        ax.barh(plot_data["label_with_n"], plot_data["response_rate"])
        ax.axvline(overall_rate, linestyle="--", label=f"Test baz oranı: %{overall_rate * 100:.1f}")
        ax.set_xlabel("Olumlu yanıt oranı")
        ax.set_ylabel("")
        ax.set_xlim(left=0)
        for index, value in enumerate(plot_data["response_rate"]):
            ax.text(value, index, f" %{value * 100:.1f}", va="center")
    else:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(plot_data["label_with_n"], plot_data["response_rate"])
        ax.axhline(overall_rate, linestyle="--", label=f"Test baz oranı: %{overall_rate * 100:.1f}")
        ax.set_ylabel("Olumlu yanıt oranı")
        ax.set_xlabel("")
        ax.set_ylim(bottom=0)
        ax.tick_params(axis="x", rotation=0)
        for index, value in enumerate(plot_data["response_rate"]):
            ax.text(index, value, f"%{value * 100:.1f}", ha="center", va="bottom")

    ax.set_title(f"Untouched test — {dimension} bazında yanıt oranı")
    ax.legend()
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / filename, dpi=180, bbox_inches="tight")
    plt.show()


# README ve proje sunumu için temel görseller.
fig, ax = plt.subplots(figsize=(10, 4.5))
for split_name, split_group in period_profile.groupby("split", sort=False):
    ax.plot(
        split_group["campaign_period_id"],
        split_group["positive_rate"],
        marker="o",
        label=split_name,
    )
ax.set_title("Kampanya dönemlerine göre olumlu yanıt oranı")
ax.set_xlabel("Kampanya dönem bloğu")
ax.set_ylabel("Olumlu yanıt oranı")
ax.set_ylim(bottom=0)
ax.legend()
plt.tight_layout()
fig.savefig(FIGURES_DIR / "01_period_response_profile.png", dpi=180, bbox_inches="tight")
plt.show()

comparison_plot = model_comparison.set_index("model")[["lift_at_20", "capture_at_20", "pr_auc"]]
fig, ax = plt.subplots(figsize=(8, 4.5))
comparison_plot.plot(kind="bar", ax=ax)
ax.set_title("Validation model karşılaştırması")
ax.set_xlabel("")
ax.set_ylabel("Metrik değeri")
ax.tick_params(axis="x", rotation=0)
ax.set_ylim(bottom=0)
plt.tight_layout()
fig.savefig(FIGURES_DIR / "02_validation_model_comparison.png", dpi=180, bbox_inches="tight")
plt.show()

fig, ax = plt.subplots(figsize=(8, 4.5))
capacity_axis = capacity_scenarios["capacity_rate"] * 100
ax.plot(capacity_axis, capacity_scenarios["response_rate"], marker="o", label="Seçilen grup yanıt oranı")
ax.plot(capacity_axis, capacity_scenarios["capture"], marker="o", label="Capture")
ax.axhline(test_base_rate, linestyle="--", label=f"Test baz oranı: %{test_base_rate * 100:.1f}")
ax.set_title("Test kapasite senaryoları")
ax.set_xlabel("Kapasite (%)")
ax.set_ylabel("Oran")
ax.set_ylim(bottom=0)
ax.legend()
plt.tight_layout()
fig.savefig(FIGURES_DIR / "03_capacity_scenarios.png", dpi=180, bbox_inches="tight")
plt.show()

plot_segment_response("Önceki Kampanya Sonucu", "04_poutcome_response_profile.png")
plot_segment_response("Kanal", "05_contact_response_profile.png")
plot_segment_response("Temas Sayısı", "06_campaign_response_profile.png", horizontal=False)
plot_segment_response("Meslek", "07_job_response_profile.png")
plot_segment_response("Yaş Bandı", "08_age_response_profile.png", horizontal=False)
plot_segment_response("Eğitim", "09_education_response_profile.png")

# Metrik çıktıları
quality_summary.to_csv(METRICS_DIR / "data_quality_summary.csv", index=False)
period_summary.to_csv(METRICS_DIR / "period_summary.csv", index=False)
split_summary.to_csv(METRICS_DIR / "chronological_split_summary.csv", index=False)
model_comparison.to_csv(METRICS_DIR / "validation_model_comparison.csv", index=False)
final_test_table.to_csv(METRICS_DIR / "final_test_metrics.csv", index=False)
capacity_scenarios.to_csv(METRICS_DIR / "test_capacity_scenarios.csv", index=False)
feature_importance.to_csv(METRICS_DIR / "validation_permutation_importance.csv", index=False)
EXCLUDED_FEATURES.to_csv(METRICS_DIR / "excluded_features.csv", index=False)
confusion_long.to_csv(METRICS_DIR / "test_confusion_matrix.csv", index=False)
segment_profile.to_csv(METRICS_DIR / "test_segment_profile.csv", index=False)
segment_profile_by_priority.to_csv(METRICS_DIR / "test_segment_profile_by_priority.csv", index=False)
age_education_profile.to_csv(METRICS_DIR / "test_age_education_profile.csv", index=False)

# Power BI tabloları
scored_test.to_csv(POWERBI_DIR / "powerbi_scored_test.csv", index=False)
final_test_table.to_csv(POWERBI_DIR / "powerbi_summary_metrics.csv", index=False)
model_comparison.to_csv(POWERBI_DIR / "powerbi_model_comparison.csv", index=False)
capacity_scenarios.to_csv(POWERBI_DIR / "powerbi_capacity_scenarios.csv", index=False)
feature_importance.to_csv(POWERBI_DIR / "powerbi_feature_importance.csv", index=False)
period_profile.to_csv(POWERBI_DIR / "powerbi_period_profile.csv", index=False)
split_summary.to_csv(POWERBI_DIR / "powerbi_split_summary.csv", index=False)
confusion_long.to_csv(POWERBI_DIR / "powerbi_confusion_matrix.csv", index=False)
segment_profile.to_csv(POWERBI_DIR / "powerbi_segment_profile.csv", index=False)
segment_profile_by_priority.to_csv(POWERBI_DIR / "powerbi_segment_profile_by_priority.csv", index=False)
age_education_profile.to_csv(POWERBI_DIR / "powerbi_age_education_profile.csv", index=False)

created_files = sorted(
    str(path.relative_to(PROJECT_ROOT))
    for path in [
        *METRICS_DIR.glob("*.csv"),
        *POWERBI_DIR.glob("*.csv"),
        *FIGURES_DIR.glob("*.png"),
    ]
)
print("Oluşturulan çıktılar:")
for path in created_files:
    print(f"- {path}")


# ## 11. Nihai yorum ve kullanım sınırları

# In[11]:


def get_segment_rate(dimension: str, segment: str) -> float:
    row = segment_profile.loc[
        segment_profile["dimension"].eq(dimension)
        & segment_profile["segment"].eq(segment),
        "response_rate",
    ]
    if row.empty:
        return float("nan")
    return float(row.iloc[0])

success_rate = get_segment_rate("Önceki Kampanya Sonucu", "Başarılı")
cellular_rate = get_segment_rate("Kanal", "Cep telefonu")
telephone_rate = get_segment_rate("Kanal", "Sabit telefon")
student_rate = get_segment_rate("Meslek", "Öğrenci")
retired_rate = get_segment_rate("Meslek", "Emekli")
age_65_rate = get_segment_rate("Yaş Bandı", "65+")


display(Markdown(
    f"""
### Nihai sonuç

- Validation seçim kuralına göre seçilen model: **{SELECTED_MODEL_NAME}**
- Validation Lift@20: **{model_comparison.loc[0, 'lift_at_20']:.2f}**
- Untouched test ROC-AUC: **{final_test_metrics['roc_auc']:.3f}**
- Untouched test PR-AUC: **{final_test_metrics['pr_auc']:.3f}**
- Test genel yanıt oranı: **%{100 * final_test_metrics['test_positive_rate']:.1f}**
- Dönem içi Top %20 yanıt oranı: **%{100 * final_test_metrics['response_rate_at_20']:.1f}**
- Capture@20: **%{100 * final_test_metrics['capture_at_20']:.1f}**
- Lift@20: **{final_test_metrics['lift_at_20']:.2f}**
- Dönem bazlı rastgele seçim beklentisine göre fark: **yaklaşık {final_test_metrics['expected_extra_positive_at_20']:.0f} olumlu kayıt**

### Test dönemi segment görünümü

- Önceki kampanyası başarılı olan kayıtlarda gözlenen yanıt oranı: **%{100 * success_rate:.1f}**
- Cep telefonu kanalında gözlenen oran: **%{100 * cellular_rate:.1f}**; sabit telefonda: **%{100 * telephone_rate:.1f}**
- Öğrenci kayıtlarında gözlenen oran: **%{100 * student_rate:.1f}**; emekli kayıtlarında: **%{100 * retired_rate:.1f}**
- 65+ yaş bandında gözlenen oran: **%{100 * age_65_rate:.1f}**

Bu segment farkları modelin işleyişini ve test döneminin profilini anlamaya yardımcı olur; nedensel operasyon politikası değildir.

### Kullanım sınırları

- Tam tarih/yıl ve benzersiz müşteri kimliği bulunmadığı için kusursuz production out-of-time validation yapılamaz.
- Validation yalnızca iki tam kampanya dönem bloğu içerir.
- Training, validation ve test baz oranları belirgin biçimde farklıdır; sonuçlar gelecek performans garantisi değildir.
- `duration` görüşme sonrasında oluştuğu için modelde kullanılmamıştır.
- `campaign`, `contact`, `month` ve `day_of_week` alanlarının planlanan temas anında bilindiği varsayılmıştır.
- Model skoru kalibre edilmiş kesin satın alma olasılığı değildir.
- Top %20 gerçek çağrı merkezi kapasitesi veya maliyet/getiri optimumu değildir.
- Beklenen ek olumlu kayıt kontrollü deney veya gerçek uplift sonucu değildir.
- Permutation importance nedensellik göstermez.
- Meslek, kanal, önceki kampanya, temas sayısı, yaş ve eğitim kırılımları gözlemseldir; nedensel politika önerisi değildir.
- Kayıt sayısı 30'un altında olan segmentler düşük örneklem olarak işaretlenmiştir.
- Yaş ve benzeri profil alanları otomatik dışlama veya erişim kısıtlama kuralı olarak kullanılmamalıdır.

Bu çalışma kamuya açık eğitim verisi üzerinde hazırlanmış retrospektif portföy analizidir.
"""
))

