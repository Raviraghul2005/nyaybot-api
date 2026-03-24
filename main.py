import uuid
import io
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from agents.intake import run_intake
from agents.rag import search_precedents
from agents.advocate import run_advocate_a, run_advocate_b
from agents.mediator import run_mediator
from agents.drafter import run_drafter
from agents.negotiation_bounds import predict_boundary_values

app = FastAPI(title="NyayBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all (for development)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "model": "nyaybot-engine-v2"}


# ── Document Extraction ───────────────────────────────────────────
@app.post("/extract-document")
async def extract_document(file: UploadFile = File(...)):
    """
    Accepts PDF, DOCX, or TXT upload and returns extracted text.
    """
    try:
        content = await file.read()
        filename = file.filename or ""
        extracted = ""

        if filename.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                extracted = f"[PDF extraction error: {e}]"

        elif filename.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(io.BytesIO(content))
                extracted = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as e:
                extracted = f"[DOCX extraction error: {e}]"

        elif filename.endswith(".txt") or filename.endswith(".csv"):
            extracted = content.decode("utf-8", errors="replace")

        else:
            extracted = f"[Unsupported format: {filename}]"

        return {
            "success": True,
            "data": {
                "filename": filename,
                "text": extracted[:5000],  # cap at 5000 chars for Gemini context
                "length": len(extracted),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Request / Response Models ─────────────────────────────────────
class IntakeRequest(BaseModel):
    raw_text: str
    party1: Optional[str] = "Party 1"
    party2: Optional[str] = "Party 2"
    amount: Optional[int] = 0

class PrecedentsRequest(BaseModel):
    query: str                   # built from intake output
    top_k: Optional[int] = 3
    dispute_type: Optional[str] = None

class BatnaRequest(BaseModel):
    amount: int
    precedents: list             # from /precedents response

class NegotiateRequest(BaseModel):
    intake: dict
    precedents: list
    round_num: int               # 1, 2, or 3
    party1_position: Optional[int] = None   # current positions (None on round 1)
    party2_position: Optional[int] = None
    custom_strategy: Optional[str] = None

class BoundaryRequest(BaseModel):
    intake: dict

class DraftRequest(BaseModel):
    intake: dict
    precedents: list
    settlement_amount: int
    party1: str
    party2: str
    case_id: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────

@app.post("/intake")
async def intake_route(req: IntakeRequest):
    try:
        result = run_intake(req.raw_text)
        # Override amount if user provided it
        if req.amount and req.amount > 0:
            result["amount"] = req.amount
        result["case_id"] = f"NB-2026-{uuid.uuid4().hex[:4].upper()}"
        result["party1"] = req.party1
        result["party2"] = req.party2
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/precedents")
async def precedents_route(req: PrecedentsRequest):
    try:
        cases = search_precedents(req.query, top_k=req.top_k, dispute_type=req.dispute_type)
        avg_settled = sum(c.get("settled_amount", 0) for c in cases) // len(cases) if cases else 0
        return {
            "success": True,
            "data": {
                "cases": cases,
                "avg_settled": avg_settled,
                "count_searched": 100000,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batna")
async def batna_route(req: BatnaRequest):
    try:
        precedents = req.precedents
        
        # Calculate averages from precedent data
        claimed_amounts = [p.get("claimed_amount", req.amount) for p in precedents]
        settled_amounts = [p.get("settled_amount", int(req.amount * 0.6)) for p in precedents]
        
        # Determine average settlement ratio from precedents
        if settled_amounts and claimed_amounts:
            ratios = [s / c for s, c in zip(settled_amounts, claimed_amounts) if c > 0]
            avg_claim_ratio = sum(ratios) / len(ratios) if ratios else 0.6
        else:
            avg_claim_ratio = 0.6
            
        win_probs = [p.get("win_probability", 60) for p in precedents if "win_probability" in p]
        avg_win = sum(win_probs) // len(win_probs) if win_probs else 60
        
        durations = [p.get("duration_months", 12) for p in precedents if "duration_months" in p]
        avg_dur = sum(durations) // len(durations) if durations else 14

        # Litigation Scenario Calculations
        # Expected court award if you win is typically 90% of your claim
        expected_award_if_win = int(req.amount * 0.9)
        
        # Dynamic Legal Costs
        # Base fee (₹15,000) + fixed cost per month of hearing (₹2,500) + percentage (4%) of the claim value
        base_fee = 15000
        hearing_fees = avg_dur * 2500
        percentage_fee = int(req.amount * 0.04)
        legal_cost = base_fee + hearing_fees + percentage_fee
        
        # Net Expected Value calculation properly weighting the win probability
        expected_court_award = int((avg_win / 100) * expected_award_if_win)
        net_ev = expected_court_award - legal_cost

        # Settlement ZOPA (Zone of Possible Agreement) based on claim ratios
        settle_low = int(req.amount * avg_claim_ratio * 0.85)
        settle_high = int(req.amount * avg_claim_ratio * 1.15)
        
        # Cap the settlement high at the original requested amount
        if settle_high > req.amount:
            settle_high = req.amount
            
        recommended_settle = int((settle_low + settle_high) / 2)

        return {
            "success": True,
            "data": {
                "litigate": {
                    "duration_months": avg_dur,
                    "legal_cost": legal_cost,
                    "win_probability": avg_win,
                    "expected_award": expected_court_award,
                    "net_expected_value": net_ev,
                },
                "settle": {
                    "range_low": settle_low,
                    "range_high": settle_high,
                    "recommended": recommended_settle,
                    "duration_days": 30,
                    "cost": 0,
                },
                "advantage": recommended_settle - net_ev,
                "recommendation": "SETTLE" if net_ev < recommended_settle else "NEGOTIATE",
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/negotiate")
async def negotiate_route(req: NegotiateRequest):
    """
    Run one round of negotiation. Call 3 times (round 1→2→3).
    Returns positions and messages from all 3 agents.
    """
    try:
        amount = req.intake.get("amount", 280000)
        ml_boundaries = None

        # Try ML boundaries first; keep API resilient if model is unavailable.
        try:
            ml_boundaries = predict_boundary_values(req.intake)
        except Exception:
            ml_boundaries = None

        # Starting positions if round 1
        if req.party1_position is not None:
            a_pos = req.party1_position
        else:
            a_pos = (
                ml_boundaries["boundary_high"]
                if ml_boundaries
                else amount
            )

        if req.party2_position is not None:
            b_pos = req.party2_position
        else:
            b_pos = (
                ml_boundaries["boundary_low"]
                if ml_boundaries
                else 0
            )

        # Run the 3 agents in sequence
        advocate_a = run_advocate_a(req.intake, req.precedents, a_pos, req.round_num, req.custom_strategy)
        advocate_b = run_advocate_b(req.intake, req.precedents, b_pos, req.round_num)
        mediator = run_mediator(
            req.intake, req.precedents,
            advocate_a["position"], advocate_b["position"],
            advocate_a["message"], advocate_b["message"],
            req.round_num
        )

        return {
            "success": True,
            "data": {
                "round": req.round_num,
                "advocate_a": advocate_a,
                "advocate_b": advocate_b,
                "mediator": mediator,
                "converged": mediator.get("converged", False),
                "ml_boundaries": ml_boundaries,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/negotiation-boundaries")
async def boundaries_route(req: BoundaryRequest):
    """
    Predicts ML-powered settlement boundary values from intake data.
    """
    try:
        boundaries = predict_boundary_values(req.intake)
        return {"success": True, "data": boundaries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/draft")
async def draft_route(req: DraftRequest):
    try:
        case_id = req.case_id or f"NB-2026-{uuid.uuid4().hex[:4].upper()}"
        result = run_drafter(
            req.intake, req.settlement_amount,
            req.party1, req.party2,
            case_id, req.precedents
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Translation ───────────────────────────────────────────────────
class TranslateRequest(BaseModel):
    text: str
    language: str          # e.g. "Hindi", "Tamil", "Telugu", "Marathi", "Bengali", "Kannada"
    context: Optional[str] = "legal settlement agreement"

@app.post("/translate")
async def translate_route(req: TranslateRequest):
    """
    Translates an English settlement agreement into the requested Indian language.
    Uses AI to produce a natural, legally accurate translation.
    """
    try:
        import google.generativeai as genai
        import os
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        lang_scripts = {
            "Hindi": "Hindi (Devanagari script)",
            "Tamil": "Tamil (Tamil script, தமிழ்)",
            "Telugu": "Telugu (Telugu script, తెలుగు)",
            "Marathi": "Marathi (Devanagari script, मराठी)",
            "Bengali": "Bengali (Bengali script, বাংলা)",
            "Malayalam": "Malayalam (Malayalam script, മലയാളം)",
            "Kannada": "Kannada (Kannada script, ಕನ್ನಡ)",
        }

        target = lang_scripts.get(req.language, req.language)

        prompt = f"""You are an expert legal translator specializing in Indian law and court documents.

Translate the following {req.context} from English into {target}.

Rules:
1. Produce a COMPLETE, accurate translation — do not skip any section.
2. Keep all monetary amounts (₹ figures), case IDs, party names, and dates exactly as-is.
3. Use formal, legally appropriate language suitable for a court-submitted document.
4. Preserve the document structure (headings, numbered clauses, etc.).
5. Do NOT add translator notes or commentary — only output the translated text.

---
{req.text}
---

Translate now:"""

        response = model.generate_content(prompt)
        translated = response.text.strip()

        return {
            "success": True,
            "data": {
                "language": req.language,
                "translated_text": translated,
                "original_length": len(req.text),
                "translated_length": len(translated),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

