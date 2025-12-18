import json
import os
import re
import datetime
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"

FILES = {
    "DB": "central_rfp_database.json",
    "PRODUCTS": "product_master_enriched.json",
    "CLIENTS": "client_master.json"
}

# --- WEIGHTS (From Friend's Non-ML Model) ---
WEIGHTS = {
    "PRODUCT_FIT": 0.4,
    "RELATIONSHIP": 0.4,
    "URGENCY": 0.2
}
MAX_URGENCY_DAYS = 90

class RealPriorityAgent:
    def __init__(self):
        self.products = self._load_json(FILES["PRODUCTS"])
        self.clients = self._load_json(FILES["CLIENTS"])
        
        # Load Settings
        try:
            # Explicitly construct path to final/settings.json
            with open(BASE_DIR / "settings.json", 'r') as f:
                self.settings = json.load(f)
        except:
             self.settings = {}

        p_config = self.settings.get("priority_config", {})
        
        # Override defaults if settings exist
        self.weights = {
            "PRODUCT_FIT": p_config.get("weight_product_fit", 0.4),
            "RELATIONSHIP": p_config.get("weight_relationship", 0.4),
            "URGENCY": p_config.get("weight_urgency", 0.2)
        }
        self.max_urgency_days = p_config.get("max_urgency_days", 90)

        # Pre-process inventory names for faster matching
        self.inventory_tokens = [
            self._tokenize(p.get('product_name', '')) 
            for p in self.products
        ]

    def _load_json(self, fname):
        # Handle relative path for settings.json which is in parent dir
        if fname.startswith(".."):
            path = BASE_DIR / fname.replace("../", "")
        else:
            path = DB_DIR / fname
            
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {} # Return dict for settings safety
        return [] if "settings" not in fname else {}

    # --- 1. PRODUCT MATCHING LOGIC (Better Score Calculator) ---
    def _tokenize(self, text):
        if not text: return set()
        return set(re.findall(r"\w+", str(text).lower()))

    def _calculate_similarity(self, text_a, tokens_b):
        tokens_a = self._tokenize(text_a)
        if not tokens_a or not tokens_b: return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union

    def get_product_fit_score(self, rfp_items):
        """
        Returns 0.0 to 1.0 based on how well we stock the requested items.
        """
        if not rfp_items: return 0.0
        
        item_scores = []
        for item in rfp_items:
            desc = item.get('raw_description', '')
            # Compare against all inventory items, take best match
            best_sim = 0.0
            for inv_tok in self.inventory_tokens:
                sim = self._calculate_similarity(desc, inv_tok)
                if sim > best_sim: best_sim = sim
            
            # Threshold logic (from friend's script)
            if best_sim >= 0.65: score = 1.0
            elif best_sim >= 0.40: score = 0.7
            elif best_sim >= 0.20: score = 0.4
            else: score = 0.0
            item_scores.append(score)
            
        return sum(item_scores) / len(item_scores) if item_scores else 0.0

    # --- 2. RELATIONSHIP SCORE LOGIC ---
    def get_relationship_score(self, client_name):
        """
        0.9 for Gold/Existing, 0.6 for new/unknown.
        """
        name_lower = str(client_name).lower()
        
        # Check Client Master
        for client in self.clients:
            if client.get('client_name', '').lower() in name_lower:
                status = client.get('loyalty_status', 'New')
                if status == 'Gold': return 0.9
                if status == 'Silver': return 0.8
                if status == 'Bronze': return 0.7
                return 0.6 # Known but no tier
        
        return 0.5 # Completely unknown

    # --- 3. URGENCY LOGIC (TIMEZONE-AWARE FOR RENDER DEPLOYMENT) ---
    def get_urgency_score(self, deadline_str):
        """
        Calculate urgency based on days remaining until deadline.
        Uses UTC timezone-aware datetime for consistency across deployments.
        """
        if not deadline_str: return 0.0
        try:
            # Parse deadline (remove 'Z' suffix if present, treat as UTC)
            deadline_clean = str(deadline_str).replace('Z', '+00:00')
            deadline = datetime.datetime.fromisoformat(deadline_clean)
            
            # CRITICAL: Always use UTC for deployed environments (Render, etc.)
            # This ensures urgency is calculated consistently regardless of server timezone
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # If deadline is naive (no timezone), assume UTC
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=datetime.timezone.utc)
            
            days_left = (deadline - now).days
            
            # Logic: Closer date = Higher score
            if days_left < 0: 
                print(f"⚠️ Expired deadline: {deadline_str} (was {abs(days_left)} days ago)")
                return 0.0
            
            d_clamped = max(0, min(days_left, self.max_urgency_days))
            urgency = 1.0 - (d_clamped / self.max_urgency_days)
            
            # Debug log (visible in Render logs)
            if urgency > 0.5:
                print(f"⏰ High Urgency: {days_left} days left → {urgency:.2f}")
            
            return urgency
        except Exception as e:
            print(f"❌ Urgency calc error for '{deadline_str}': {e}")
            return 0.0

    # --- MAIN EXECUTION ---
    def recalculate_all_priorities(self):
        """
        Reads the CENTRAL DB, recalculates scores for ALL active RFPs,
        Assigns Ranks (1, 2, 3...), and saves back to DB.
        """
        print("⚡ [Priority Agent] Recalculating Queue...")
        
        db_path = DB_DIR / FILES["DB"]
        if not db_path.exists(): return

        with open(db_path, 'r', encoding='utf-8') as f:
            rfp_list = json.load(f)

        # 1. Calculate Scores
        scored_rfps = []
        for rfp in rfp_list:
            if rfp.get('is_archived', False): 
                rfp['sales_agent_2_output'] = {"rank": -1, "priority_score": 0, "status": "Archived"}
                continue

            sales_out = rfp.get('sales_agent_output', {})
            summary = sales_out.get('summary', {})
            
            # A. Product Fit (Smart Upgrade)
            tech_out = rfp.get('tech_agent_output', {})
            if tech_out and tech_out.get('matched_line_items'):
                # Use Verified Tech Match!
                items = tech_out.get('matched_line_items', [])
                total_match = sum([item.get('match_score', 0) for item in items])
                p_score = (total_match / len(items)) / 100.0 if items else 0.0
            else:
                # Fallback to Sales Estimation
                p_score = self.get_product_fit_score(sales_out.get('line_items_extracted', []))
            
            # B. Relationship
            r_score = self.get_relationship_score(summary.get('client_name', ''))
            
            # C. Urgency
            u_score = self.get_urgency_score(summary.get('submission_deadline'))
            
            # D. Multiplicative Priority Logic (Legacy Agent Style)
            # 1. Estimate Win Probability (average of Fit and Relationship)
            p_win = (p_score + r_score) / 2.0
            
            # 2. Apply Urgency Multiplier (Gamma = 0.5)
            # Priority = P(Win) * (1 + Gamma * Urgency)
            gamma = 0.5
            total_score = p_win * (1.0 + (gamma * u_score))
            
            # Normalize to roughly 0-1 range for consistency, though >1 is possible
            # Max possible = 1.0 * 1.5 = 1.5. So divide by 1.5 to keep 0-1 scale?
            # User wants "detailed ordering", raw score is fine.
            # But UI expects 0-100 usually. 
            
            scored_rfps.append({
                "id": rfp['rfp_unique_id'],
                "total": total_score,
                "breakdown": {
                    "product_fit": round(p_score, 2),
                    "relationship": round(r_score, 2),
                    "urgency": round(u_score, 2),
                    "p_win_est": round(p_win, 2)
                }
            })

        # 2. Sort by Score (Highest First)
        scored_rfps.sort(key=lambda x: x['total'], reverse=True)
        
        # 3. Assign Ranks & Save back to Objects
        rank_map = {item['id']: i+1 for i, item in enumerate(scored_rfps)}
        
        for rfp in rfp_list:
            rid = rfp['rfp_unique_id']
            if rid in rank_map:
                # Find the score object
                score_data = next(x for x in scored_rfps if x['id'] == rid)
                
                rfp['sales_agent_2_output'] = {
                    "rank": rank_map[rid],
                    "priority_score": round(score_data['total'] * 100, 1), # Convert to 0-100
                    "breakdown": score_data['breakdown']
                }

        # 4. Save DB
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(rfp_list, f, indent=2)
            
        print("✅ [Priority Agent] Queue Updated.")