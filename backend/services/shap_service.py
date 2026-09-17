from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import shap

from src.predict import MODELS, CONFIG, feature_frame
from .adverse_action_mapper import map_adverse_reason, map_positive_factor

logger = logging.getLogger(__name__)

_tree_explainer: Optional[shap.TreeExplainer] = None
_base_prob: float = 0.5
_feature_root_map: Optional[List[str]] = None

def init_shap_explainer() -> None:
    """Initialize TreeExplainer once during lifespan startup and cache static metadata."""
    global _tree_explainer, _base_prob, _feature_root_map
    if _tree_explainer is not None:
        return
    try:
        pipeline = MODELS.get("loan_approval")
        if pipeline is not None and hasattr(pipeline, "named_steps"):
            model = pipeline.named_steps.get("model")
            prep = pipeline.named_steps.get("prep")
            if model is not None:
                _tree_explainer = shap.TreeExplainer(model)
                logger.info("SHAP TreeExplainer initialized successfully for loan_approval model.")
                
                # Cache expected base probability
                expected_val = _tree_explainer.expected_value
                if isinstance(expected_val, (list, np.ndarray)) and len(expected_val) > 1:
                    _base_prob = float(expected_val[1])
                else:
                    _base_prob = float(expected_val) if expected_val is not None else 0.5

            if prep is not None and hasattr(prep, "get_feature_names_out"):
                raw_names = list(prep.get_feature_names_out())
                root_map = []
                for feat_name in raw_names:
                    root = feat_name
                    if "__" in root:
                        root = root.split("__", 1)[1]
                    for orig in CONFIG["features"]["loan_approval"]:
                        if root == orig or root.startswith(f"{orig}_"):
                            root = orig
                            break
                    root_map.append(root)
                _feature_root_map = root_map
    except Exception as exc:
        logger.warning(f"Failed to initialize SHAP TreeExplainer: {exc}")

def get_shap_explainer() -> Optional[shap.TreeExplainer]:
    """Get the cached TreeExplainer singleton."""
    global _tree_explainer
    if _tree_explainer is None:
        init_shap_explainer()
    return _tree_explainer

def explain_loan_approval(applicant_data: dict, loan_status: str, approval_probability: float) -> dict:
    """
    Generate localized TreeSHAP feature attributions for loan approval prediction.
    Aggregates one-hot features to domain features, ranks by absolute contribution,
    and returns adverse action reasons and positive factors.
    """
    explainer = get_shap_explainer()
    if explainer is None:
        return {
            "adverse_action_reasons": [],
            "positive_factors": [],
            "all_feature_contributions": [],
            "explanation_metadata": {"method": "SHAP_UNAVAILABLE", "status": "explainer_not_initialized"}
        }

    try:
        pipeline = MODELS["loan_approval"]
        prep = pipeline.named_steps["prep"]
        row = pd.DataFrame([applicant_data])
        approval_X = feature_frame(row, CONFIG["features"]["loan_approval"])
        X_trans = prep.transform(approval_X)

        sv = explainer.shap_values(X_trans, check_additivity=False)
        if isinstance(sv, list) and len(sv) == 2:
            class1_vals = sv[1][0]
        elif hasattr(sv, "shape") and len(sv.shape) == 3:
            class1_vals = sv[0, :, 1]
        elif hasattr(sv, "shape") and len(sv.shape) == 2:
            class1_vals = sv[0]
        else:
            class1_vals = np.array(sv).flatten()

        base_prob = _base_prob

        feature_map = _feature_root_map
        if feature_map is None:
            feature_names = list(prep.get_feature_names_out())
            feature_map = []
            for feat_name in feature_names:
                root = feat_name
                if "__" in root:
                    root = root.split("__", 1)[1]
                for orig in CONFIG["features"]["loan_approval"]:
                    if root == orig or root.startswith(f"{orig}_"):
                        root = orig
                        break
                feature_map.append(root)

        grouped_impacts: Dict[str, float] = {}
        for root, val in zip(feature_map, class1_vals):
            grouped_impacts[root] = grouped_impacts.get(root, 0.0) + float(val)

        sorted_factors = sorted(grouped_impacts.items(), key=lambda x: abs(x[1]), reverse=True)

        neg_factors = [
            {
                "feature": feat,
                "contribution": round(contrib, 4),
                "description": map_adverse_reason(feat)
            }
            for feat, contrib in sorted_factors if contrib < 0
        ]
        adverse_action_reasons = neg_factors[:4]

        pos_factors = [
            {
                "feature": feat,
                "contribution": round(contrib, 4),
                "description": map_positive_factor(feat)
            }
            for feat, contrib in sorted_factors if contrib > 0
        ]
        positive_factors = pos_factors[:4]

        return {
            "adverse_action_reasons": adverse_action_reasons,
            "positive_factors": positive_factors,
            "all_feature_contributions": [
                {"feature": feat, "contribution": round(contrib, 4)}
                for feat, contrib in sorted_factors
            ],
            "explanation_metadata": {
                "method": "TreeSHAP",
                "model_name": "loan_approval",
                "base_value": round(base_prob, 4),
                "decision": loan_status,
                "approval_probability": round(approval_probability, 4),
                "features_evaluated": len(grouped_impacts)
            }
        }
    except Exception as exc:
        logger.exception(f"Error computing SHAP explanations: {exc}")
        return {
            "adverse_action_reasons": [],
            "positive_factors": [],
            "all_feature_contributions": [],
            "explanation_metadata": {"method": "TreeSHAP", "status": "error", "error": str(exc)}
        }
