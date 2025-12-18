"""
app_genie_json_download_only.py

Streamlit app:
- Upload a PDF
- Use Gemini to extract structured JSON following example schema
- Return only a downloadable JSON file when successful (no previews)
"""

import streamlit as st
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime, timezone
import json
import re
from PyPDF2 import PdfReader

# optional SDK import (may be None if not installed)
try:
    import google.generativeai as genai
except Exception:
    genai = None

load_dotenv()

# ----------------- Helpers -----------------
def now_iso_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def extract_pdf_text(uploaded_file):
    """Extract textual content from an uploaded PDF file using PyPDF2."""
    try:
        reader = PdfReader(uploaded_file)
    except Exception as e:
        raise RuntimeError(f"Unable to read PDF: {e}")
    texts = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t:
            texts.append(t)
    if not texts:
        raise RuntimeError("No selectable text found in PDF. If PDF is scanned, use OCR or provide a searchable PDF.")
    return "\n\n".join(texts)

def build_example_json():
    """Return the example JSON structure (as Python dict)."""
    return {
        "rfp_unique_id": "RFP-2025-DMRC-003",
        "status": "New",
        "last_updated": "2025-11-01T09:00:00Z",
        "processing_stage_tracker": {
            "sales_agent": "Completed",
            "tech_agent": "Pending",
            "pricing_agent": "Pending",
            "final_review": "Pending"
        },
        "sales_agent_output": {
            "summary": {
                "client_name": "Delhi Metro Rail Corporation (DMRC)",
                "project_title": "Underground Tunnel Electrification - Phase 4",
                "tender_ref_no": "DMRC/ELECT/UG/2025/44",
                "submission_deadline": "2025-12-15T14:00:00",
                "contract_currency": "INR",
                "emd_amount": "500000.0",
                "emd_type": "Bank Guarantee"
            },
            "logistics_constraints": {
                "delivery_location": "Mukundpur Depot, Delhi",
                "delivery_timeline_days": 60,
                "unloading_scope": "Client Scope"
            },
            "commercial_terms": {
                "payment_terms": "100% against GRN within 30 days",
                "penalty_clause": "0.5% per week, max 5%",
                "price_basis": "FOR Destination"
            },
            "line_items_extracted": [
                {
                    "lot_id": "L001",
                    "raw_description": "Supply of 33kV 3 core 400sqmm Copper LSZH Armoured Cable for Tunnel Power",
                    "quantity": 5000,
                    "unit": "Meter",
                    "technical_attributes": {
                        "voltage_grade": "33kV",
                        "core_count": 3,
                        "cross_section_sqmm": 400,
                        "conductor_material": "Copper",
                        "insulation_type": "XLPE",
                        "sheath_type": "LSZH (Low Smoke Zero Halogen)",
                        "standards": ["BS 7835", "IEC 60502"]
                    }
                }
            ]
        }
    }

def prepare_prompt(pdf_text: str):
    """Prepare a safe prompt embedding example JSON and the PDF text."""
    if not pdf_text:
        raise ValueError("pdf_text cannot be empty")

    example = build_example_json()
    example_str = json.dumps(example, indent=2)
    prompt = f"""
You are an accurate information extractor. Produce ONLY a JSON (no commentary) that follows EXACTLY the schema, structure, and keys used in this example. Replace the example values with values extracted from the provided PDF.

Example JSON to follow (keys & structure):
{example_str}

Rules:
1. rfp_unique_id: generate a random unique id string (e.g. "RFP-<RANDOM>").
2. last_updated: use the current UTC timestamp (ISO 8601).
3. Keep the exact keys inside "processing_stage_tracker" unchanged: sales_agent, tech_agent, pricing_agent, final_review.
4. For "line_items_extracted" include one object per product found. If the PDF has N products, include N objects in that list. If some attribute is missing for a product, use the string "NOT SPECIFIED".
5. Output JSON only — nothing else.

PDF Text:
{pdf_text}
"""
    return prompt

def safe_parse_json(text: str):
    """Try to parse text to JSON. If text contains extra characters, attempt to extract first JSON object."""
    if not text:
        raise ValueError("Empty text for JSON parsing.")
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            candidate = m.group(0)
            try:
                return json.loads(candidate)
            except Exception as e:
                raise ValueError(f"Could not parse JSON from model output: {e}")
        raise ValueError("Model output is not valid JSON and no JSON object could be extracted.")

def sanitize_and_fill(parsed: dict):
    """Ensure schema exists, fill missing entries with 'NOT SPECIFIED', set rfp id and timestamp."""
    template = build_example_json()

    # processing tracker: preserve keys from template, accept values from parsed if provided
    processing = template["processing_stage_tracker"].copy()
    parsed_proc = parsed.get("processing_stage_tracker") or {}
    if isinstance(parsed_proc, dict):
        for k in processing.keys():
            v = parsed_proc.get(k)
            if v not in (None, "", []):
                processing[k] = v

    result = {
        "rfp_unique_id": parsed.get("rfp_unique_id") or f"RFP-{uuid.uuid4().hex[:8].upper()}",
        "status": parsed.get("status") or template["status"],
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "processing_stage_tracker": processing,
        "sales_agent_output": {}
    }

    # summary
    parsed_summary = (parsed.get("sales_agent_output") or {}).get("summary") or {}
    summary = {}
    for k in template["sales_agent_output"]["summary"].keys():
        v = parsed_summary.get(k)
        summary[k] = v if v not in (None, "", []) else "NOT SPECIFIED"

    # logistics
    parsed_log = (parsed.get("sales_agent_output") or {}).get("logistics_constraints") or {}
    logistics = {}
    for k in template["sales_agent_output"]["logistics_constraints"].keys():
        v = parsed_log.get(k)
        logistics[k] = v if v not in (None, "", []) else "NOT SPECIFIED"

    # commercial
    parsed_comm = (parsed.get("sales_agent_output") or {}).get("commercial_terms") or {}
    commercial = {}
    for k in template["sales_agent_output"]["commercial_terms"].keys():
        v = parsed_comm.get(k)
        commercial[k] = v if v not in (None, "", []) else "NOT SPECIFIED"

    # line items
    parsed_items = (parsed.get("sales_agent_output") or {}).get("line_items_extracted") or parsed.get("line_items_extracted") or []
    final_items = []
    if isinstance(parsed_items, list):
        for i, item in enumerate(parsed_items, start=1):
            if not isinstance(item, dict):
                continue
            ta = item.get("technical_attributes") or {}
            filled_ta = {}
            template_ta = template["sales_agent_output"]["line_items_extracted"][0]["technical_attributes"]
            for tk in template_ta.keys():
                tv = ta.get(tk)
                filled_ta[tk] = tv if tv not in (None, "", []) else "NOT SPECIFIED"

            lot = {
                "lot_id": item.get("lot_id") or f"L{i:03d}",
                "raw_description": item.get("raw_description") or "NOT SPECIFIED",
                "quantity": item.get("quantity") if item.get("quantity") not in (None, "") else "NOT SPECIFIED",
                "unit": item.get("unit") or "NOT SPECIFIED",
                "technical_attributes": filled_ta
            }
            final_items.append(lot)

    result["sales_agent_output"] = {
        "summary": summary,
        "logistics_constraints": logistics,
        "commercial_terms": commercial,
        "line_items_extracted": final_items
    }

    return result

# ----------------- Gemini calling (adaptive) -----------------
def configure_genai(api_key):
    if genai is None:
        raise RuntimeError("google.generativeai SDK is not available in this environment.")
    genai.configure(api_key=api_key)

def try_generate_with_models(prompt, model_candidates=None, methods=None):
    """
    Try several model names & methods until one returns text.
    Returns the raw text.
    """
    if genai is None:
        raise RuntimeError("google.generativeai SDK not available.")

    if model_candidates is None:
        model_candidates = [
            "gemini-2.5-flash",
            "gemini-2.1",
            "gemini-pro",
            "text-bison-001",
        ]
    if methods is None:
        methods = ["generate_content", "generate_text", "generate_message", "generate"]

    last_err = None
    for m in model_candidates:
        try:
            model = genai.GenerativeModel(m)
        except Exception as e:
            last_err = e
            continue
        for method in methods:
            if not hasattr(model, method):
                continue
            try:
                fn = getattr(model, method)
                try:
                    resp = fn(prompt)
                except TypeError:
                    resp = fn({"prompt": prompt})
                # extract text
                text = None
                if hasattr(resp, "text") and isinstance(resp.text, str):
                    text = resp.text
                else:
                    # attempt to find a textual candidate in repr / dict
                    try:
                        if hasattr(resp, "to_dict"):
                            d = resp.to_dict()
                        else:
                            d = resp.__dict__
                    except Exception:
                        d = None
                    # deep search for first string
                    def deep_search(o):
                        if isinstance(o, str):
                            return o
                        if isinstance(o, dict):
                            for v in o.values():
                                r = deep_search(v)
                                if r:
                                    return r
                        if isinstance(o, list):
                            for el in o:
                                r = deep_search(el)
                                if r:
                                    return r
                        return None
                    cand = deep_search(d)
                    if cand:
                        text = cand
                if not text:
                    text = str(resp)
                return text
            except Exception as e:
                last_err = e
                continue
    raise RuntimeError(f"All model attempts failed. Last error: {last_err}")

# ----------------- Streamlit UI (minimal / download-only) -----------------
st.set_page_config(page_title="PDF → RFP JSON (Download Only)", layout="centered")
st.title("PDF → RFP JSON Filler (Download Only)")
st.write("Upload an RFP/Tender PDF and get a downloadable JSON following the required schema. No previews will be shown for professionalism.")

uploaded_file = st.file_uploader("Upload PDF (RFP/Tender)", type=["pdf"])
if not uploaded_file:
    st.info("Upload a PDF to extract data.")
    st.stop()

# Check API key and configure genai
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Please set GOOGLE_API_KEY in your environment or .env file.")
    st.stop()

try:
    configure_genai(API_KEY)
except Exception as e:
    st.error(f"Failed to configure Gemini SDK: {e}")
    st.stop()

# PROCESS button
if st.button("PROCESS"):
    # extract text
    try:
        pdf_text = extract_pdf_text(uploaded_file)
    except Exception as e:
        st.error(f"PDF extraction failed: {e}")
        st.stop()

    # build prompt
    prompt = prepare_prompt(pdf_text)

    # call model
    try:
        raw_output_text = try_generate_with_models(prompt)
    except Exception as e:
        st.error(f"Model generation failed: {e}")
        st.stop()

    # parse JSON
    try:
        parsed = safe_parse_json(raw_output_text)
    except Exception as e:
        st.error(f"Failed to parse JSON from model output: {e}")
        st.stop()

    # sanitize & fill
    final_response = sanitize_and_fill(parsed)

    # Prepare download bytes
    json_bytes = json.dumps(final_response, indent=2, ensure_ascii=False).encode("utf-8")

    # Show minimal success and download button only
    st.success("JSON extraction complete. Click the button below to download the file.")
    st.download_button(
        "Download extracted JSON",
        data=json_bytes,
        file_name="extracted_rfp.json",
        mime="application/json"
    )
