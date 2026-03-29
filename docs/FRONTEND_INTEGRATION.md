# NyayBot API - Frontend Integration Document

This document describes the complete backend feature set in this repository and how to integrate it from a frontend application.

## 1) Backend Scope

Primary backend app:
- `main.py` (FastAPI app to be used by frontend)

Core domain modules:
- `agents/intake.py`
- `agents/rag.py`
- `agents/advocate.py`
- `agents/mediator.py`
- `agents/drafter.py`
- `agents/negotiation_bounds.py`
- `agents/utils.py`

Optional separate service (not required for main frontend flow):
- `ai-negotiation/backend/app.py` with `/predict`

## 2) Base URL and Startup

Recommended local run:
- `python -m uvicorn main:app --reload --port 8010`

Base URL:
- `http://127.0.0.1:8010`

Swagger docs:
- `http://127.0.0.1:8010/docs`

## 3) Environment Variables

Required for full functionality:
- `GEMINI_API_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`

If these are missing:
- AI endpoints may fail with 500.
- RAG search may return empty or fail.

## 4) API Endpoints (Primary App)

## 4.1 `GET /health`

Purpose:
- Health check and metadata.

Response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "nyaybot-engine-v2"
}
```

---

## 4.2 `POST /extract-document`

Purpose:
- Extract text from uploaded file for downstream intake.

Content-Type:
- `multipart/form-data` with key `file`.

Supported extensions:
- `.pdf`
- `.docx`
- `.txt`
- `.csv`

Response:
```json
{
  "success": true,
  "data": {
    "filename": "contract.pdf",
    "text": "extracted text up to 5000 chars...",
    "length": 12345
  }
}
```

Important behavior:
- `data.text` is truncated to 5000 characters.
- Unsupported format still returns 200 with message text like `[Unsupported format: ...]`.
- Parser failures may return bracketed error text in `data.text`.

---

## 4.3 `POST /intake`

Purpose:
- Convert unstructured dispute text into structured legal intake data.

Request:
```json
{
  "raw_text": "full case narrative here",
  "party1": "Party 1",
  "party2": "Party 2",
  "amount": 280000
}
```

Response shape:
```json
{
  "success": true,
  "data": {
    "dispute_type": "Service Failure",
    "amount": 280000,
    "key_facts": ["..."],
    "disputed_clauses": ["..."],
    "forum_recommendation": "Consumer Commission",
    "case_summary": "...",
    "strength_assessment": "Moderate",
    "strength_reasoning": "...",
    "case_id": "NB-2026-AB12",
    "party1": "Party 1",
    "party2": "Party 2"
  }
}
```

Notes:
- If `amount > 0` in request, backend overrides AI-extracted amount with request amount.
- `case_id` is auto-generated server-side.

---

## 4.4 `POST /precedents`

Purpose:
- Retrieve similar precedents from vector search (Qdrant + embeddings).

Request:
```json
{
  "query": "MSME supply dispute delayed defective goods payment withheld",
  "top_k": 3,
  "dispute_type": "MSME Supply Dispute"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "cases": [
      {
        "id": "CASE-001",
        "title": "ABC vs XYZ",
        "forum": "NCDRC",
        "year": 2022,
        "dispute_type": "Service Failure",
        "facts": "...",
        "disputed_clause": "...",
        "claimed_amount": 300000,
        "settled_amount": 180000,
        "win_probability": 62,
        "duration_months": 14,
        "outcome": "settled",
        "key_principle": "...",
        "similarity": 0.81
      }
    ],
    "avg_settled": 180000,
    "count_searched": 100000
  }
}
```

Notes:
- `count_searched` is currently hardcoded.
- If retrieval fails, endpoint may return empty `cases`.

---

## 4.5 `POST /batna`

Purpose:
- Compute litigation expected value and settlement range using precedent-informed heuristics.

Request:
```json
{
  "amount": 280000,
  "precedents": []
}
```

Response:
```json
{
  "success": true,
  "data": {
    "litigate": {
      "duration_months": 14,
      "legal_cost": 62000,
      "win_probability": 60,
      "expected_award": 151200,
      "net_expected_value": 89200
    },
    "settle": {
      "range_low": 142800,
      "range_high": 193200,
      "recommended": 168000,
      "duration_days": 30,
      "cost": 0
    },
    "advantage": 78800,
    "recommendation": "SETTLE"
  }
}
```

---

## 4.6 `POST /negotiation-boundaries`

Purpose:
- ML prediction for settlement and negotiation boundaries.

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

Response:
```json
{
  "success": true,
  "data": {
    "predicted_settlement": 63436,
    "boundary_low": 53920,
    "boundary_high": 72951
  }
}
```

ML dependency:
- Requires `ai-negotiation/ml/model.pkl`.
- If model file missing, endpoint returns 500.

---

## 4.7 `POST /negotiate`

Purpose:
- Run one negotiation round (Advocate A, Advocate B, Mediator).

Request:
```json
{
  "intake": {
    "amount": 280000,
    "dispute_type": "Service Failure",
    "strength_assessment": "Moderate",
    "key_facts": ["Delayed delivery", "Defective units"],
    "disputed_clauses": ["delivery schedule", "quality warranty"]
  },
  "precedents": [],
  "round_num": 1,
  "party1_position": null,
  "party2_position": null
}
```

Response:
```json
{
  "success": true,
  "data": {
    "round": 1,
    "advocate_a": {
      "position": 73000,
      "message": "..."
    },
    "advocate_b": {
      "position": 54000,
      "message": "..."
    },
    "mediator": {
      "zopa_low": 54000,
      "zopa_high": 73000,
      "recommended_settlement": 63500,
      "converged": false,
      "message": "..."
    },
    "converged": false,
    "ml_boundaries": {
      "predicted_settlement": 63436,
      "boundary_low": 53920,
      "boundary_high": 72951
    }
  }
}
```

Round behavior:
- Intended for rounds 1..3.
- Round 1 defaults:
  - Uses `party1_position` / `party2_position` if provided.
  - Else uses ML boundaries if available.
  - Else fallback to `amount` and `0`.
- Round 2/3:
  - Frontend should pass previous positions back.

Timeout behavior:
- Advocate and mediator calls have explicit 30s request timeout to Gemini.

---

## 4.8 `POST /draft`

Purpose:
- Generate settlement agreement text + key terms.

Request:
```json
{
  "intake": {
    "dispute_type": "Service Failure",
    "amount": 280000
  },
  "precedents": [],
  "settlement_amount": 76000,
  "party1": "M/s Alpha Components",
  "party2": "Beta Retail Pvt Ltd",
  "case_id": "NB-2026-AB12"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "agreement_text": "FULL AGREEMENT TEXT...",
    "key_terms": [
      { "term": "Settlement Amount", "value": "₹76,000" },
      { "term": "Payment Timeline", "value": "30 days" }
    ]
  }
}
```

---

## 4.9 `POST /translate`

Purpose:
- Translate legal text (commonly agreement output).

Request:
```json
{
  "text": "agreement text in English",
  "language": "Hindi",
  "context": "legal settlement agreement"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "language": "Hindi",
    "translated_text": "...",
    "original_length": 4500,
    "translated_length": 5200
  }
}
```

Known language mappings:
- Hindi
- Tamil
- Telugu
- Marathi
- Bengali
- Kannada

If another language is provided:
- Backend uses it directly in prompt.

## 5) Full Frontend Flow (Recommended)

Use this sequence in UI:

1. Optional: `POST /extract-document`
2. `POST /intake`
3. `POST /precedents`
4. `POST /batna`
5. Optional: `POST /negotiation-boundaries`
6. `POST /negotiate` round 1
7. `POST /negotiate` round 2 (use round-1 positions)
8. `POST /negotiate` round 3 or early stop when `converged=true`
9. `POST /draft`
10. Optional: `POST /translate`

## 6) Frontend State Model (Suggested)

```ts
type AppState = {
  case: {
    case_id?: string;
    party1?: string;
    party2?: string;
    intake?: Record<string, unknown>;
  };
  documents?: {
    filename?: string;
    text?: string;
    length?: number;
  };
  precedents?: {
    cases: Record<string, unknown>[];
    avg_settled?: number;
    count_searched?: number;
  };
  batna?: {
    litigate?: Record<string, unknown>;
    settle?: Record<string, unknown>;
    advantage?: number;
    recommendation?: "SETTLE" | "NEGOTIATE" | string;
  };
  boundaries?: {
    predicted_settlement?: number;
    boundary_low?: number;
    boundary_high?: number;
  };
  negotiation?: {
    round?: number;
    advocate_a?: { position?: number; message?: string };
    advocate_b?: { position?: number; message?: string };
    mediator?: Record<string, unknown>;
    converged?: boolean;
    history?: Record<string, unknown>[];
  };
  draft?: {
    agreement_text?: string;
    key_terms?: { term: string; value: string }[];
  };
  translation?: {
    language?: string;
    translated_text?: string;
    original_length?: number;
    translated_length?: number;
  };
  errors?: { endpoint: string; status?: number; detail?: string; retriable?: boolean }[];
};
```

## 7) Error and UX Handling

Expected statuses:
- `200`: success
- `422`: request validation error
- `500`: backend/AI/ML/runtime error

Frontend handling recommendations:
- Show endpoint-level error toast with `detail` from error body.
- Keep partial progress in state; allow retry per step.
- Add loading and cancel controls for AI-heavy steps:
  - intake
  - precedents
  - negotiate
  - draft
  - translate
- For `extract-document`, detect bracketed parser messages and show as warning.

## 8) ML Module Details

Main app uses:
- `agents/negotiation_bounds.py`

Model file path:
- `ai-negotiation/ml/model.pkl`

Training:
- `python ai-negotiation/ml/train.py`

Feature mapping used by predictor:
- `claim` from `intake.amount`
- mapped `type` from `intake.dispute_type`
- `severity` from lengths of `key_facts` + `disputed_clauses` (capped at 5)
- `evidence` from `strength_assessment` map (Strong/Moderate/Weak)
- fixed `aggressiveness=3`, `flexibility=3`

Boundary computation:
- Predicted settlement +/- 15%
- Clamped to claim amount where applicable

## 9) Security and Deployment Notes

- CORS currently allows all origins/methods/headers.
- No authentication/authorization is present.
- Use API gateway or middleware auth before production exposure.
- Do not keep real secrets in committed `.env`.

## 10) Optional Secondary Service (`ai-negotiation/backend`)

This is a separate minimal FastAPI app:
- `GET /` returns backend running message.
- `POST /predict` returns `predicted_settlement`.

If frontend uses main app (`main.py`), you do not need this service.

## 11) Quick Example Payload Set

Minimal working case inputs:

`/intake`:
```json
{
  "raw_text": "M/s Alpha Components supplied 500 units to Beta Retail. Delivery delayed by 3 weeks and 120 units were defective. Payment of INR 280000 withheld.",
  "party1": "M/s Alpha Components",
  "party2": "Beta Retail Pvt Ltd",
  "amount": 280000
}
```

`/negotiation-boundaries`:
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

`/negotiate` round 1:
```json
{
  "intake": {
    "amount": 280000,
    "dispute_type": "Service Failure",
    "strength_assessment": "Moderate",
    "key_facts": ["Delayed delivery", "Defective units"],
    "disputed_clauses": ["delivery schedule", "quality warranty"]
  },
  "precedents": [],
  "round_num": 1
}
```

---

This document is intended as the frontend contract reference for the current repository state.
