from __future__ import annotations
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, mean_absolute_error, mean_squared_error, r2_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from .pipeline_utils import ROOT, CONFIG, clean_common, feature_frame, make_preprocessor, save_json

R = ROOT / "reports"; M = ROOT / "models"; F = R / "figures"
F.mkdir(parents=True, exist_ok=True); M.mkdir(parents=True, exist_ok=True)


def regression_metrics(y, p):
    return {"mae": float(mean_absolute_error(y,p)), "rmse": float(np.sqrt(mean_squared_error(y,p))), "r2": float(r2_score(y,p))}

def classifier_metrics(y, p, prob):
    return {"accuracy": float(accuracy_score(y,p)), "f1": float(f1_score(y,p)), "roc_auc": float(roc_auc_score(y,prob)), "confusion_matrix": confusion_matrix(y,p).tolist()}

def multiclass_metrics(y,p):
    return {"accuracy": float(accuracy_score(y,p)), "f1_macro": float(f1_score(y,p,average="macro")), "confusion_matrix": confusion_matrix(y,p).tolist()}

def split_xy(X, y, stratify=None):
    return train_test_split(X, y, test_size=0.20, random_state=42, stratify=stratify)

def main():
    loan = clean_common(pd.read_csv(ROOT/"data/raw/loan_data.csv"))
    risk = clean_common(pd.read_csv(ROOT/"data/raw/credit_risk_data.csv"))
    metrics = {"dataset": {"loan_rows": len(loan), "risk_rows": len(risk)}, "modules": {}, "version": "2.0.0"}
    # M1: approved amount, only on approved applications; enforce business cap.
    approved = loan[loan.loan_status.eq("Approved")].copy()
    approved["approved_loan_amount"] = np.minimum(approved["approved_loan_amount"], approved["requested_loan_amount"])
    X = feature_frame(approved, CONFIG["features"]["loan_amount"]); y = approved["approved_loan_amount"]
    Xtr, Xte, ytr, yte = train_test_split(X,y,test_size=.2,random_state=42)
    model = Pipeline([("prep",make_preprocessor(Xtr)),("model",RandomForestRegressor(n_estimators=300,max_depth=18,min_samples_leaf=2,n_jobs=-1,random_state=42))])
    model.fit(Xtr,ytr); p=model.predict(Xte); metrics["modules"]["loan_amount"]={"rows":len(approved),"test":regression_metrics(yte,np.minimum(p, approved.loc[Xte.index,"requested_loan_amount"]))}
    joblib.dump(model,M/"loan_amount.joblib")
    # M2 approval
    X = feature_frame(loan, CONFIG["features"]["loan_approval"]); y = loan.loan_status.eq("Approved").astype(int)
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
    model = Pipeline([("prep",make_preprocessor(Xtr)),("model",RandomForestClassifier(n_estimators=350,max_depth=18,min_samples_leaf=2,class_weight="balanced",n_jobs=-1,random_state=42))])
    model.fit(Xtr,ytr); prob=model.predict_proba(Xte)[:,1]; pred=(prob>=.5).astype(int); metrics["modules"]["loan_approval"]={"rows":len(loan),"test":classifier_metrics(yte,pred,prob)}
    joblib.dump(model,M/"loan_approval.joblib")
    # M3 credit score (no credit_score input feature)
    X = feature_frame(risk, CONFIG["features"]["credit_score"]); y = risk.credit_score
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42)
    model=Pipeline([("prep",make_preprocessor(Xtr)),("model",GradientBoostingRegressor(n_estimators=250,learning_rate=.04,max_depth=3,loss="huber",random_state=42))])
    model.fit(Xtr,ytr); p=model.predict(Xte); metrics["modules"]["credit_score"]={"rows":len(risk),"test":regression_metrics(yte,np.clip(p,300,850))}
    joblib.dump(model,M/"credit_score.joblib")
    # M4 risk — leakage-safe: do not use observed credit_score or credit_strength
    X = feature_frame(risk, CONFIG["features"]["credit_risk"]).drop(columns=["credit_score", "credit_strength"], errors="ignore")
    le=LabelEncoder(); y=le.fit_transform(risk.risk_level)
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
    model=Pipeline([("prep",make_preprocessor(Xtr)),("model",RandomForestClassifier(n_estimators=400,max_depth=20,min_samples_leaf=2,class_weight="balanced",n_jobs=-1,random_state=42))])
    model.fit(Xtr,ytr); pred=model.predict(Xte); metrics["modules"]["credit_risk"]={"rows":len(risk),"classes":le.classes_.tolist(),"test":multiclass_metrics(yte,pred)}
    joblib.dump({"pipeline":model,"label_encoder":le},M/"credit_risk.joblib")
    save_json(metrics,R/"training_metrics.json")
    pd.DataFrame([{**{"module":k},**v["test"]} for k,v in metrics["modules"].items()]).drop(columns=["confusion_matrix"],errors="ignore").to_csv(R/"model_comparison.csv",index=False)
    print(json.dumps(metrics,indent=2))
if __name__ == "__main__": main()
