# Negotiation Boundaries - Complete Integration Guide

This document is a complete reference for negotiation boundaries in this repository, focused on:

- `agents/negotiation_bounds.py`
- the ML model pipeline in `ai-negotiation/ml`
- how frontend should consume boundary values

## 1) What Negotiation Boundaries Are

Negotiation boundaries provide a machine-learned settlement anchor and range:

- `predicted_settlement`: model-estimated fair settlement
- `boundary_low`: lower negotiation bound
- `boundary_high`: upper negotiation bound

These are used to initialize negotiation positions in round 1 and can also be shown as guidance in frontend UX.

## 2) Source of Truth Files

Primary production logic:
- `agents/negotiation_bounds.py`

Primary API usage:
- `main.py`
  - `POST /negotiation-boundaries`
  - `POST /negotiate` (auto-uses boundaries when positions are missing)

ML training/inference support:
- `ai-negotiation/ml/generate_data.py`
- `ai-negotiation/ml/train.py`
- `ai-negotiation/ml/model.pkl`

Secondary standalone ML service (optional, not required by main app):
- `ai-negotiation/backend/services/ml_model.py`
- `ai-negotiation/backend/utils/preprocess.py`
- `ai-negotiation/backend/routes/predict.py`

## 3) Core Function in `agents/negotiation_bounds.py`

Public function:
- `predict_boundary_values(intake: Dict[str, Any], spread_ratio: float = 0.15) -> Dict[str, int>`

Returns:
```json
{
  "predicted_settlement": 65972,
  "boundary_low": 56076,
  "boundary_high": 75867
}
```

### 3.1 Input fields expected from `intake`

`predict_boundary_values()` reads:
- `amount` (claim amount)
- `dispute_type`
- `strength_assessment`
- `key_facts` (list)
- `disputed_clauses` (list)

If fields are missing, defaults are applied.

### 3.2 Internal feature mapping logic

From `_map_input_to_features()`:

- `claim = int(amount or 0)`
- `type` mapped from `dispute_type`:
  - `Consumer Product Defect -> refund`
  - `Service Failure -> service`
  - `Payment Default -> delivery`
  - `Contract Breach -> service`
  - `Property Dispute -> fraud`
  - `MSME Supply Dispute -> delivery`
  - fallback: `service`
- `evidence` mapped from `strength_assessment`:
  - `Strong -> 5`
  - `Moderate -> 3`
  - `Weak -> 1`
  - fallback: `3`
- `severity = min(5, len(key_facts) + len(disputed_clauses))`
- fixed values:
  - `aggressiveness = 3`
  - `flexibility = 3`

Final model feature vector:
- `claim`, `type`, `severity`, `evidence`, `aggressiveness`, `flexibility`

### 3.3 Model load behavior

Model path resolved as:
- `repo_root/ai-negotiation/ml/model.pkl`

If file is missing:
- raises `FileNotFoundError` with clear message.

### 3.4 Prediction and boundary formulas

1. Run model prediction:
- `predicted_settlement = int(model.predict(df)[0])`

2. Clamp prediction to claim when claim is positive:
- `predicted_settlement = max(0, min(predicted_settlement, claim_amount))`

3. Compute bounds:
- `lower = int(predicted_settlement * (1 - spread_ratio))`
- `upper = int(predicted_settlement * (1 + spread_ratio))`

4. Clamp upper to claim if claim positive:
- `upper = min(upper, claim_amount)`

5. Return non-negative integers:
- `boundary_low = max(0, lower)`
- `boundary_high = max(0, upper)`

Default `spread_ratio`:
- `0.15` (15%)

## 4) API Contracts for Frontend

## 4.1 `POST /negotiation-boundaries`

Purpose:
- direct boundary computation endpoint.

Request:
```json
{
  "intake": {
    "amount": 280000,
    "dispute_type": "Service Failure",
    "strength_assessment": "Moderate",
    "key_facts": ["Delayed delivery", "Defective units"],
    "disputed_clauses": ["delivery schedule", "quality warranty"]
  }
}
```

Success response:
```json
{
  "success": true,
  "data": {
    "predicted_settlement": 65972,
    "boundary_low": 56076,
    "boundary_high": 75867
  }
}
```

Error behavior:
- `500` if model is missing or unexpected runtime error.
- `422` for schema validation errors.

## 4.2 `POST /negotiate` (how boundaries are applied)

In `main.py`, `/negotiate` does:

1. Tries boundary prediction:
- `ml_boundaries = predict_boundary_values(req.intake)`
- on failure, sets `ml_boundaries = None` (no hard failure here)

2. Round position initialization:
- If `party1_position` provided by frontend -> use it
- Else if `ml_boundaries` exists -> use `boundary_high`
- Else -> fallback to `intake.amount` (or `280000` default)

- If `party2_position` provided by frontend -> use it
- Else if `ml_boundaries` exists -> use `boundary_low`
- Else -> fallback to `0`

3. Response always includes:
- `data.ml_boundaries` (object or `null`)

Important frontend implication:
- For round 1, omitting `party1_position` and `party2_position` allows backend to start from ML boundaries.
- For round 2/3, frontend should pass prior round positions explicitly.

## 5) ML Model Pipeline Details

## 5.1 Dataset generation (`ai-negotiation/ml/generate_data.py`)

Generates synthetic training rows with columns:
- `type`, `claim`, `severity`, `evidence`, `aggressiveness`, `flexibility`, `settlement`

Settlement label logic:
- Starts with claim * type-specific ratio:
  - refund: 0.6-0.85
  - service: 0.4-0.7
  - delivery: 0.3-0.6
  - fraud: 0.2-0.4
- Adds/subtracts rule-based effects for severity/evidence/aggressiveness/flexibility
- Clamps to `[0, claim]`

Output:
- `data.csv`

## 5.2 Training (`ai-negotiation/ml/train.py`)

Training steps:
- load `data.csv`
- one-hot encode `type`
- split train/test (`test_size=0.2`, `random_state=42`)
- train `RandomForestRegressor()`
- print MAE
- save artifact as `model.pkl` in `ai-negotiation/ml`

Command:
```powershell
python ai-negotiation/ml/train.py
```

## 5.3 Feature alignment at inference

Inference code one-hot encodes and then does:
- `df.reindex(columns=model.feature_names_in_, fill_value=0)`

This ensures trained feature order/shape compatibility even if some categories are absent in input.

## 6) Secondary ML Service (Optional)

Separate backend endpoint:
- `POST /predict` in `ai-negotiation/backend/routes/predict.py`
- returns only:
```json
{"predicted_settlement": 65972}
```

It uses similar feature preprocessing but does not produce low/high boundaries.

Use this only if you intentionally run that service.
Main app already provides full boundaries via `/negotiation-boundaries`.

## 7) Frontend Integration Recommendations

Recommended usage pattern:

1. Run `POST /intake`
2. Pass returned intake object to `POST /negotiation-boundaries`
3. Show boundary band in UI:
   - "Suggested range: boundary_low - boundary_high"
4. Start round 1 using `/negotiate`:
   - either omit positions and let backend use ML automatically
   - or send explicit `party1_position=boundary_high`, `party2_position=boundary_low`
5. For rounds 2/3:
   - send positions from previous round response

Suggested UI fields:
- `predictedSettlement`
- `boundaryLow`
- `boundaryHigh`
- `boundarySource` (`"ml"` or `"fallback"`)

## 8) Validation and Edge Cases

Behavior to expect:

- Missing/weak intake fields:
  - prediction still runs with defaults
  - quality may degrade

- Claim amount <= 0:
  - prediction is not upper-capped by claim
  - bounds still non-negative

- Missing model file:
  - `/negotiation-boundaries` returns 500
  - `/negotiate` continues with fallback positions and `ml_boundaries: null`

- External AI delays in `/negotiate`:
  - advocate/mediator model calls use timeout settings in their modules
  - frontend should still implement retry/cancel UX

## 9) Test Checklist for Frontend Team

1. Call `/negotiation-boundaries` with full intake and confirm:
   - fields exist and are numbers
   - `boundary_low <= predicted_settlement <= boundary_high`

2. Call `/negotiate` round 1 without explicit positions and verify:
   - `data.ml_boundaries` is present
   - round runs successfully

3. Call `/negotiate` round 1 with explicit positions from boundaries and verify:
   - no errors
   - positions and messages returned

4. Remove/rename model file (dev test only) and verify:
   - `/negotiation-boundaries` returns 500
   - `/negotiate` still works with `ml_boundaries: null`

## 10) Copy-Paste Example for Frontend

Boundary request:
```json
{
  "intake": {
    "amount": 280000,
    "dispute_type": "Service Failure",
    "strength_assessment": "Moderate",
    "key_facts": [
      "Delayed delivery by 3 weeks",
      "120 units defective",
      "Payment withheld"
    ],
    "disputed_clauses": [
      "delivery schedule",
      "quality warranty"
    ]
  }
}
```

Boundary response (example):
```json
{
  "success": true,
  "data": {
    "predicted_settlement": 65972,
    "boundary_low": 56076,
    "boundary_high": 75867
  }
}
```

Round-1 negotiate request using boundaries explicitly:
```json
{
  "intake": {
    "amount": 280000,
    "dispute_type": "Service Failure",
    "strength_assessment": "Moderate",
    "key_facts": [
      "Delayed delivery by 3 weeks",
      "120 units defective",
      "Payment withheld"
    ],
    "disputed_clauses": [
      "delivery schedule",
      "quality warranty"
    ]
  },
  "precedents": [],
  "round_num": 1,
  "party1_position": 75867,
  "party2_position": 56076
}
```

---

This document is the complete contract reference for negotiation boundaries in the current codebase.
