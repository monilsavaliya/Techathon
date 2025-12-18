import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import json
import re
import math
import uuid
from pathlib import Path
from datetime import datetime, timezone
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# Optional SDK import
try:
    import google.generativeai as genai
except ImportError:
    genai = None

load_dotenv(override=True)

app = FastAPI()

# ================= CONFIGURATION =================
FACTORY_LAT = 21.1702
FACTORY_LON = 72.8311
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Point specifically to the 'database' folder
LOGISTIC_MASTER_FILE = BASE_DIR / "database" / "logistic_master.json"

# ================= HELPER FUNCTIONS =================
def load_logistic_zones():
    try:
        if LOGISTIC_MASTER_FILE.exists():
            with open(LOGISTIC_MASTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        lon1, lat1, lon2, lat2 = map(math.radians, [float(lon1), float(lat1), float(lon2), float(lat2)])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a)) 
        r = 6371 
        return round(c * r, 2)
    except Exception:
        return 0

def extract_text_from_bytes(file_bytes):
    from io import BytesIO
    try:
        reader = PdfReader(BytesIO(file_bytes))
        texts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t: texts.append(t)
        return "\n\n".join(texts)
    except Exception as e:
        return ""

def build_example_json():
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
                "delivery_coordinates": {"lat": 28.73, "lon": 77.19},
                "distance_from_factory_km": 0,
                "zone_code": "Z-04",
                "zone_type": "Urban_Restricted",
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
                        "insulation": "XLPE",
                        "screen": "Copper Tape",
                        "armour_type": "Steel Wire",
                        "sheath": "LSZH",
                        "standards": ["BS 7835"]
                    }
                }
            ]
        }
    }

def prepare_prompt(pdf_text, zones):
    example = build_example_json()
    example_str = json.dumps(example, indent=2)
    
    if zones:
        zone_desc = "\n".join([f"- {z['zone_code']}: {z['zone_type']} (Keywords: {z['zone_type'].replace('_', ' ')})" for z in zones])
    else:
        zone_desc = "- Z-01: Plains_Highway (Default)"

    prompt = f"""
You are an expert Technical Sales Engineer. Your job is to extract RFP details from the text below and map them STRICTLY to the provided JSON schema.

**CRITICAL INSTRUCTION FOR LOGISTICS:**
- Extract the "delivery_location".
- Based on the location name, ESTIMATE the "delivery_coordinates" (Latitude and Longitude).
- **ZONE DETECTION:** Analyze the location and match it to one of these zones:
{zone_desc}
  - If the terrain matches (e.g. Hilly, Desert, Coastal), use that 'zone_code' and 'zone_type'.
  - If uncertain, default to "Z-01".

Example JSON to follow (keys & structure):
{example_str}

PDF Text:
{pdf_text[:30000]}
"""
    return prompt

def try_generate_with_models(prompt):
    """
    Robust Retry Logic (Deep Try/Except from Streamlit)
    """
    # 1. Load API Key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key: api_key = os.getenv("GOOGLE_API_KEY_1")
    if not api_key: raise RuntimeError("No API Key found")

    genai.configure(api_key=api_key)

    # 2. Your Exact Model List
    model_candidates = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-pro-latest",
    ]
    methods = ["generate_content", "generate_text"]

    last_err = None
    
    for m in model_candidates:
        try:
            # Init model
            model = genai.GenerativeModel(m)
        except Exception as e:
            last_err = e
            continue

        for method in methods:
            if not hasattr(model, method):
                continue
            try:
                fn = getattr(model, method)
                # Attempt generation
                try:
                    resp = fn(prompt)
                except TypeError:
                    resp = fn({"prompt": prompt})

                # Extract Text (Deep Search)
                text = None
                if hasattr(resp, "text") and isinstance(resp.text, str):
                    text = resp.text
                else:
                    try:
                        if hasattr(resp, "to_dict"): d = resp.to_dict()
                        else: d = resp.__dict__
                    except: d = None
                    
                    def deep_search(o):
                        if isinstance(o, str): return o
                        if isinstance(o, dict):
                            for v in o.values():
                                r = deep_search(v)
                                if r: return r
                        if isinstance(o, list):
                            for el in o:
                                r = deep_search(el)
                                if r: return r
                        return None
                    
                    cand = deep_search(d)
                    if cand: text = cand
                
                if not text: text = str(resp)
                return text

            except Exception as e:
                # IMPORTANT: Swallow 404/API errors here and try next method/model
                last_err = e
                continue

    raise RuntimeError(f"All model attempts failed. Last error: {last_err}")

def safe_parse_json(text):
    if not text: return {}
    try: return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m: 
            try: return json.loads(m.group(0))
            except: pass
    return {}

def sanitize_and_fill(parsed, zones):
    template = build_example_json()

    # processing tracker
    processing = template["processing_stage_tracker"].copy()
    parsed_proc = parsed.get("processing_stage_tracker") or {}
    if isinstance(parsed_proc, dict):
        for k in processing.keys():
            v = parsed_proc.get(k)
            if v: processing[k] = v

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
        summary[k] = v if v else "NOT SPECIFIED"

    # logistics
    parsed_log = (parsed.get("sales_agent_output") or {}).get("logistics_constraints") or {}
    logistics = {}
    for k in template["sales_agent_output"]["logistics_constraints"].keys():
        v = parsed_log.get(k)
        logistics[k] = v if v else "NOT SPECIFIED"
    
    # Distance
    dist = 0
    try:
        coords = parsed_log.get("delivery_coordinates")
        if coords:
            dist = haversine_distance(FACTORY_LAT, FACTORY_LON, coords.get('lat',0), coords.get('lon',0))
    except: pass
    logistics['distance_from_factory_km'] = dist
    logistics["factory_coordinates"] = {"lat": FACTORY_LAT, "lon": FACTORY_LON}

    # Zone
    detected_code = logistics.get("zone_code", "Z-01")
    valid_zone = next((z for z in zones if z['zone_code'] == detected_code), None)
    if valid_zone:
        logistics['zone_type'] = valid_zone['zone_type']
    else:
        logistics['zone_code'] = "Z-01"
        logistics['zone_type'] = "Plains_Highway"

    # commercial
    parsed_comm = (parsed.get("sales_agent_output") or {}).get("commercial_terms") or {}
    commercial = {}
    for k in template["sales_agent_output"]["commercial_terms"].keys():
        v = parsed_comm.get(k)
        commercial[k] = v if v else "NOT SPECIFIED"

    # line items
    final_items = []
    raw_items = (parsed.get("sales_agent_output") or {}).get("line_items_extracted") or parsed.get("line_items_extracted") or []
    if isinstance(raw_items, list):
        for i, item in enumerate(raw_items, 1):
            if not isinstance(item, dict): continue
            ta = item.get("technical_attributes") or {}
            filled_ta = {}
            template_ta = template["sales_agent_output"]["line_items_extracted"][0]["technical_attributes"]
            for tk in template_ta.keys():
                tv = ta.get(tk)
                filled_ta[tk] = tv if tv else "NOT SPECIFIED"
            
            lot = {
                "lot_id": item.get("lot_id") or f"L{i:03d}",
                "raw_description": item.get("raw_description") or "NOT SPECIFIED",
                "quantity": item.get("quantity") or "NOT SPECIFIED",
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

# ================= API ENDPOINT =================
@app.post("/process-rfp")
async def process_rfp_endpoint(file: UploadFile = File(...)):
    print(f"📥 API received file: {file.filename}")
    
    content = await file.read()
    text = extract_text_from_bytes(content)
    
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")
        
    zones = load_logistic_zones()
    
    try:
        prompt = prepare_prompt(text, zones)
        raw_text = try_generate_with_models(prompt)
        parsed = safe_parse_json(raw_text)
        final_data = sanitize_and_fill(parsed, zones)
        return final_data
    except Exception as e:
        print(f"❌ API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Sales API Server starting on port 8000...")
    uvicorn.run(app, host="127.0.0.1", port=8000)