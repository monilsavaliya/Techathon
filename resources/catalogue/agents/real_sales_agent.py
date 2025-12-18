import os
import json
import re
import math
import time
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

load_dotenv()

class RealSalesAgent:
    def __init__(self, settings_path="settings.json"):
        # 1. Setup Paths
        self.base_dir = Path(__file__).parent
        self.settings_path = self.base_dir / settings_path
        self.logistic_master_path = self.base_dir / "logistic_master.json"

        # 2. Load API Keys
        self.api_keys = self.load_api_keys()
        self.current_key_index = 0

        if self.api_keys:
            self._configure_genai()
        else:
            print("❌ CRITICAL: No GOOGLE_API_KEY found.")

        # 3. Load Settings
        self.factory_lat = 21.1702
        self.factory_lon = 72.8311
        self.load_settings()

        # 4. Load Logistic Zones
        self.zones = self.load_logistic_zones()

    def load_api_keys(self):
        keys = []
        for i in range(1, 6):
            k = os.getenv(f"GOOGLE_API_KEY_{i}")
            if k: keys.append(k)
        if os.getenv("GOOGLE_API_KEY"):
            if os.getenv("GOOGLE_API_KEY") not in keys:
                keys.append(os.getenv("GOOGLE_API_KEY"))
        return keys

    def _configure_genai(self):
        if genai and self.api_keys:
            try:
                genai.configure(api_key=self.api_keys[self.current_key_index])
            except Exception as e:
                print(f"⚠️ genai.configure() failed: {e}")

    def rotate_api_key(self):
        if not self.api_keys: return
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"🔑 Rotating to API Key #{self.current_key_index + 1}")
        self._configure_genai()

    def load_settings(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r') as f:
                    data = json.load(f)
                    log_conf = data.get("logistics_config", {})
                    self.factory_lat = float(log_conf.get("factory_lat", 21.1702))
                    self.factory_lon = float(log_conf.get("factory_lon", 72.8311))
            except Exception: pass

    def load_logistic_zones(self):
        try:
            if self.logistic_master_path.exists():
                with open(self.logistic_master_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return []
        return []

    def haversine_distance(self, lat1, lon1, lat2, lon2):
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

    def extract_pdf_text(self, file_path):
        try:
            reader = PdfReader(file_path)
            texts = []
            for page in reader.pages:
                t = page.extract_text() or ""
                if t: texts.append(t)
            return "\n\n".join(texts)
        except Exception as e:
            return ""

    def build_example_json(self):
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
                        "raw_description": "Supply of 33kV 3 core 400sqmm Copper LSZH Armoured Cable",
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

    def prepare_prompt(self, pdf_text):
        example = self.build_example_json()
        example_str = json.dumps(example, indent=2)
        
        if self.zones:
            zone_desc = "\n".join([f"- {z['zone_code']}: {z['zone_type']} (Keywords: {z['zone_type'].replace('_', ' ')})" for z in self.zones])
        else:
            zone_desc = "- Z-01: Plains_Highway (Default)"

        prompt = f"""You are an expert Technical Sales Engineer. Your job is to extract RFP details from the text below and map them STRICTLY to the provided JSON schema.

**CRITICAL INSTRUCTION FOR LOGISTICS:**
- Extract the "delivery_location".
- Based on the location name, ESTIMATE the "delivery_coordinates" (Latitude and Longitude).
- **ZONE DETECTION:** Analyze the location and match it to one of these zones:
{zone_desc}
  - If the terrain matches (e.g. Hilly, Desert, Coastal), use that 'zone_code' and 'zone_type'.
  - If uncertain, default to "Z-01".

**CRITICAL INSTRUCTION FOR TECHNICAL ATTRIBUTES:**
The 'technical_attributes' keys MUST match the keys used in our internal 'product_master.json'.
- Use "insulation" (not insulation_type).
- Use "sheath" (not sheath_type).
- Use "armour_type" (e.g., "Steel Wire", "Flat Strip").
- Use "screen" if applicable (e.g., "Copper Tape").
- For "cross_section_sqmm", extract ONLY the number (e.g. 400).
- For "core_count", extract the number (e.g. 3 or 3.5).

Example JSON to follow (keys & structure):
{example_str}

Rules:
1. rfp_unique_id: generate a random unique id string (e.g. "RFP-<RANDOM>").
2. Output JSON only — no markdown formatting, no comments.

PDF Text:
{pdf_text[:30000]}
"""
        return prompt

    def try_generate_with_models(self, prompt):
        if genai is None: raise RuntimeError("google.generativeai SDK not installed")

        # --- FIX: USE ONLY VALID PUBLIC MODELS ---
        model_candidates = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        max_rotations = len(self.api_keys)

        for _ in range(max_rotations + 1): 
            for model_name in model_candidates:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    return resp.text
                except Exception as e:
                    err = str(e).lower()
                    print(f"⚠️ Model {model_name} failed: {err}")
                    if "429" in err or "quota" in err:
                        print("⏳ Quota Limit. Rotating key...")
                        self.rotate_api_key()
                        time.sleep(1)
                        break 
                    time.sleep(1)
                    continue 
            
            self.rotate_api_key()
            
        raise RuntimeError("All models/keys failed.")

    def safe_parse_json(self, text):
        if not text: return {}
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, flags=re.S)
            if m:
                try: return json.loads(m.group(0))
                except: pass
        return {}

    def sanitize_and_fill(self, parsed):
        template = self.build_example_json()

        # 1. Processing Tracker
        processing = template["processing_stage_tracker"].copy()
        parsed_proc = parsed.get("processing_stage_tracker") or {}
        if isinstance(parsed_proc, dict):
            for k in processing.keys():
                v = parsed_proc.get(k)
                if v: processing[k] = v

        result = {
            "rfp_unique_id": parsed.get("rfp_unique_id") or f"RFP-{uuid.uuid4().hex[:8].upper()}",
            "status": parsed.get("status") or "New",
            "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "processing_stage_tracker": processing,
            "sales_agent_output": {}
        }

        # 2. Extract Sales Output Sections
        p_sales = parsed.get("sales_agent_output") or {}

        # -- Summary --
        summary = {}
        for k in template["sales_agent_output"]["summary"].keys():
            val = (p_sales.get("summary") or {}).get(k)
            summary[k] = val if val not in (None, "", []) else "NOT SPECIFIED"

        # -- Logistics (With Distance Calc) --
        logistics = {}
        p_log = p_sales.get("logistics_constraints") or {}
        
        for k in template["sales_agent_output"]["logistics_constraints"].keys():
            val = p_log.get(k)
            logistics[k] = val if val not in (None, "", []) else "NOT SPECIFIED"

        dest_coords = p_log.get("delivery_coordinates")
        distance = 0
        if dest_coords and isinstance(dest_coords, dict):
            try:
                d_lat = float(dest_coords.get("lat", 0))
                d_lon = float(dest_coords.get("lon", 0))
                if d_lat != 0:
                    distance = self.haversine_distance(self.factory_lat, self.factory_lon, d_lat, d_lon)
            except: pass
        
        logistics["distance_from_factory_km"] = distance
        logistics["factory_coordinates"] = {"lat": self.factory_lat, "lon": self.factory_lon}

        detected_code = logistics.get("zone_code", "Z-01")
        valid_zone = next((z for z in self.zones if z['zone_code'] == detected_code), None)
        if valid_zone:
            logistics['zone_type'] = valid_zone['zone_type']
        else:
            logistics['zone_code'] = "Z-01"
            logistics['zone_type'] = "Plains_Highway"

        # -- Commercial --
        commercial = {}
        for k in template["sales_agent_output"]["commercial_terms"].keys():
            val = (p_sales.get("commercial_terms") or {}).get(k)
            commercial[k] = val if val not in (None, "", []) else "NOT SPECIFIED"

        # -- Line Items (Deep Fill) --
        final_items = []
        raw_items = p_sales.get("line_items_extracted") or []
        if isinstance(raw_items, list):
            for i, item in enumerate(raw_items, 1):
                if not isinstance(item, dict): continue
                
                ta = item.get("technical_attributes") or {}
                filled_ta = {}
                template_ta = template["sales_agent_output"]["line_items_extracted"][0]["technical_attributes"]
                for tk in template_ta.keys():
                    tv = ta.get(tk)
                    filled_ta[tk] = tv if tv not in (None, "", []) else "NOT SPECIFIED"

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

    def process_rfp(self, filepath, filename="doc.pdf"):
        print(f"🤖 SALES AGENT: Processing {filename}...")
        text = self.extract_pdf_text(filepath)
        if not text:
            return {"error": "Could not extract text from PDF"}

        prompt = self.prepare_prompt(text)

        try:
            raw_text = self.try_generate_with_models(prompt)
            parsed_json = self.safe_parse_json(raw_text)
            final_data = self.sanitize_and_fill(parsed_json)
            return final_data
        except Exception as e:
            print(f"❌ Sales Agent Error: {e}")
            return {"error": str(e)}