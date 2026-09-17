# Architecture

CSV source → task-specific cleaning → shared feature engineering → scikit-learn preprocessing → task model → FastAPI → React/Vite frontend.

The API imports the single prediction registry in `src/predict.py`, so model loading and feature engineering are not duplicated between backend and inference code.

The two raw datasets remain separate. Models are independently trained from the data containing their targets. Shared customer IDs are useful for analysis, but inference does not require joining the datasets.
