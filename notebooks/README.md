# Jupyter Notebooks

These notebooks are included for EDA, model evaluation, learning, and project presentation. They use the same datasets, configuration, feature engineering, and serialized models as the production application.

## Notebooks

1. `01_Loan_Data_EDA.ipynb` — dataset quality, distributions, duplicates, and basic validation.
2. `02_Loan_Amount_Prediction.ipynb` — approved-loan amount model evaluation.
3. `03_Loan_Approval_Prediction.ipynb` — approval probability, threshold, and classification metrics.
4. `04_Credit_Score_Prediction.ipynb` — credit-score regression evaluation.
5. `05_Credit_Risk_Analysis.ipynb` — leakage-safe risk evaluation and credit-score independence smoke test.
6. `06_Model_Evaluation.ipynb` — training metrics and artifact verification.

## Run

From the project root:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-notebooks.txt
python -m jupyter lab
```

Open the notebook files under `notebooks/`. The notebooks are analysis-oriented and do not overwrite production `.joblib` files.
