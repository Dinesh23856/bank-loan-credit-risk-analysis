"""Controlled retraining entry point.

Run manually after reviewing data provenance:
    python -m src.train
This wrapper exists so future scheduled jobs have a stable entry point.
It intentionally does not overwrite production models automatically.
"""
from src.train import main
if __name__=="__main__":
    main()
