# Model cards

## Approval
Random Forest classifier. Primary metrics: ROC-AUC, F1, accuracy. Imbalanced classes are handled with class weights.

## Approved amount
Random Forest regression trained on approved applications only. Predictions are capped to the requested amount.

## Credit score
Huber-loss Gradient Boosting regression. The observed credit score is excluded from features to prevent direct target leakage.

## Credit risk
Random Forest multiclass classifier with class weights. Labels are Low / Medium / High from the supplied risk dataset.

The risk model was retrained as a leakage-safe model without the observed `credit_score` and the derived `credit_strength` feature. The repository does not contain the original target-generation provenance, so direct target derivation cannot be proven; excluding score-derived predictors is the conservative deployment choice. The retrained holdout metrics are accuracy 0.8179 and macro-F1 0.5780. This is lower than the prior model, which is expected when removing a potentially leaked predictor.
