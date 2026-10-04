# Bank Marketing: Chronological Response Prediction, Contact Prioritization, and Segment Profiling

This project is an educational and portfolio study designed to **rank campaign contact records within each period** according to their positive response propensity, evaluate limited contact capacity, and explain the profile of prioritized records through tables suitable for Power BI.

> **Current version:** v4  
> **Main analysis:** `notebooks/bank_marketing_chronological_analysis_v4.ipynb`  
> **Executable Python file:** `src/bank_marketing_chronological_analysis_v4.py`

## Business question

If only a limited number of contact records can be processed in each campaign period, which records should be evaluated first, and what is the profile of the prioritized records?

The model's `response_score` output is not an exact purchase probability. It is a relative **response propensity / prioritization score** used to rank records within the same campaign period.

## Project scope

1. Data quality, `unknown` values, and exact duplicate rows were checked.
2. Full campaign-period blocks were created while preserving the chronological order of the file.
3. Periods were split into training, validation, and untouched test sets.
4. `duration` was excluded from the model because of data leakage.
5. Macroeconomic fields were excluded from the main model because they may act as period proxies and create portability risk.
6. Logistic Regression and Random Forest were compared.
7. Model selection was based on **Lift@20** in the validation set; PR-AUC was used as a supporting metric.
8. The selected model was retrained on the combined training and validation data and evaluated only once on the most recent test section.
9. Test records were ranked separately within each campaign period, and 5%–50% capacity scenarios were generated.
10. Job, channel, previous campaign, number of contacts, age, and education profiles were reported on the untouched test set.
11. Record-level, model, capacity, period, and segment tables were created for Power BI.

## Chronological split

| Split | Period blocks | Records | Positive response rate |
|---|---:|---:|---:|
| Training | 1–8 | 27,964 | 5.24% |
| Validation | 9–10 | 8,250 | 11.71% |
| Test | 11–26 | 4,962 | 44.50% |

The baseline response rate changes substantially across periods. Therefore, the results should not be interpreted as a guarantee of performance for future campaigns.

![Response rate by campaign period](outputs/figures/01_period_response_profile.png?v=20261004-en)

## Validation model comparison

| Model | ROC-AUC | PR-AUC | Lift@20 | Capture@20 |
|---|---:|---:|---:|---:|
| Random Forest | 0.634 | **0.199** | **1.42** | **28.36%** |
| Logistic Regression | **0.640** | 0.195 | 1.37 | 27.33% |

Random Forest was selected because Lift@20 was the primary model-selection metric. No claim is made that one model is decisively or substantially superior to the other.

## Untouched test result

| Metric | Result |
|---|---:|
| Selected model | Random Forest |
| ROC-AUC | 0.660 |
| PR-AUC | 0.609 |
| F1 | 0.621 |
| Test baseline response rate | 44.50% |
| Records selected in the within-period Top 20% | 999 |
| Top 20% response rate | 67.87% |
| Capture@20 | 30.71% |
| Lift@20 | 1.53 |
| Difference vs. period-level random selection expectation | approximately +233 positive records |

The “expected difference” is not the result of a controlled experiment, real campaign uplift, or an uplift model. It is a retrospective comparison against the expected outcome of random selection at the same capacity level within each test period.

![Test capacity scenarios](outputs/figures/03_capacity_scenarios.png?v=20261004-en)

## Power BI dashboard

A three-page Power BI dashboard was prepared so that business users can interpret model outputs, campaign capacity, and the profile of prioritized records more easily.

### 1. Campaign Decision and Contact Prioritization

The first page compares the number of prioritized records, response rate, Capture, and Lift across different contact-capacity scenarios.

![Campaign Decision and Contact Prioritization](images/dashboard_01_campaign_decision.png?v=20261004-en)

### 2. Profile of Prioritized Records

The second page summarizes the age, job, education, contact channel, and previous-campaign characteristics of the Top 20% prioritized group.

![Profile of Prioritized Records](images/dashboard_02_target_profile.png?v=20261004-en)

### 3. Model and Limitations

The third page presents the selected model's key performance indicators and the methodological limitations that should be considered when interpreting the results.

![Model and Limitations](images/dashboard_03_model_limitations.png?v=20261004-en)

> Dashboard results are based on retrospective test data. The visuals should not be interpreted as real campaign uplift, financial ROI, or live decision-engine performance.

## Segment profiling

In version V4, untouched test records are additionally analyzed across the following dimensions:

- Job
- Contact channel
- Previous campaign outcome
- Number of contacts in the campaign
- Age band
- Education

For each segment, record volume, number of positive records, response rate, lift versus the overall average, and a low-sample-size warning are generated. The findings are observational and should not be interpreted as causal relationships or as automatic targeting/exclusion policies.

![Test response profile by previous campaign outcome](outputs/figures/04_poutcome_response_profile.png?v=20261004-en)

## Features used

### Customer profile

`age`, `job`, `marital`, `education`, `default`, `housing`, `loan`

### Previous campaign information

`previous`, `poutcome`, `previously_contacted`

### Assumed planned-contact context

`campaign`, `contact`, `month`, `day_of_week`

Detailed feature policy: [`docs/model_feature_policy.csv`](docs/model_feature_policy.csv)

## Power BI usage

Main dynamic table:

```text
outputs/powerbi/powerbi_scored_test.csv
```

This table contains the record-level score, actual response, within-period rank, priority band, and translated profile fields. The other CSV files serve as supporting tables for KPIs, capacity scenarios, model comparison, feature importance, and segment summaries.

- Table dictionary: [`docs/powerbi_tables.md`](docs/powerbi_tables.md)
- Three-page dashboard guide: [`docs/powerbi_dashboard_guide.md`](docs/powerbi_dashboard_guide.md)
- PBIX scope and usage notes: [`powerbi/README.md`](powerbi/README.md)

## Project structure

```text
bank-marketing-response-prioritization/
├── README.md
├── CHANGELOG.md
├── requirements.txt
├── src/
│   └── bank_marketing_chronological_analysis_v4.py
├── notebooks/
│   └── bank_marketing_chronological_analysis_v4.ipynb
├── data/
│   └── bank-additional-full.csv
├── docs/
│   ├── methodology.md
│   ├── model_feature_policy.csv
│   ├── powerbi_dashboard_guide.md
│   └── powerbi_tables.md
├── outputs/
│   ├── figures/
│   ├── metrics/
│   └── powerbi/
├── powerbi/
│   └── README.md
└── archive/
    └── v3/
        ├── README.md
        └── bank_marketing_chronological_analysis_v3.ipynb
```

## Installation and execution

The project was tested with Python **3.13.5**.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
jupyter notebook notebooks/bank_marketing_chronological_analysis_v4.ipynb
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/bank_marketing_chronological_analysis_v4.ipynb
```

To run the Python file directly from the project root:

```bash
python src/bank_marketing_chronological_analysis_v4.py
```

When the notebook or Python file is run from start to finish, the `outputs/metrics/`, `outputs/powerbi/`, and `outputs/figures/` folders are regenerated.

## Main limitations

- No unique customer identifier or complete date/year information is available.
- Validation contains only two complete campaign-period blocks.
- Training, validation, and test baseline response rates differ substantially.
- The `campaign`, `contact`, `month`, and `day_of_week` fields are assumed to be known at scoring time.
- The model score is not a calibrated exact purchase probability.
- The Top 20% is not a real call-center capacity limit or a cost/return optimum.
- ROI or true uplift was not calculated because cost, product return, and control-group data are not available.
- Permutation importance and segment differences do not imply causality.
- Segments with fewer than 30 records are flagged as low-sample-size segments.
- Age and similar profile fields should not be used as automatic exclusion or access-restriction rules.

## Data source

UCI Machine Learning Repository — **Bank Marketing**, Dataset ID 222  
DOI: `10.24432/C5K306`

This repository is a retrospective portfolio analysis based on publicly available educational data. A code license has intentionally not been added; the repository owner should select a license separately according to the intended sharing terms.