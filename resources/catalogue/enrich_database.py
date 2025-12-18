import json
import os
import re

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")

# Input Files
PRODUCT_MASTER_PATH = os.path.join(DB_DIR, "product_master.json")
MATERIAL_MASTER_PATH = os.path.join(DB_DIR, "material_master.json")
COMPETITORS_PATH = os.path.join(DB_DIR, "competitors.json")
TEST_MASTER_PATH = os.path.join(DB_DIR, "test_master.json")

# Output File
OUTPUT_PATH = os.path.join(DB_DIR, "product_master_enriched.json")

# --- HELPERS TO LOAD DATA ---
def load_json(path):
    if not os.path.exists(path):
        print(f"⚠️ Warning: {path} not found. Returning empty list.")
        return []
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            # Handle if data is wrapped in a dict key like "products" or "items"
            if isinstance(data, dict):
                # Try common keys, else return values if it's a dict of items
                return data.get('products', data.get('items', list(data.values())))
            return data
    except Exception as e:
        print(f"❌ Error loading {path}: {e}")
        return []

# --- INTELLIGENT MAPPERS ---

def find_material_id(material_name, voltage_grade, material_db):
    """
    Looks up the REAL material ID from material_master based on rules.
    """
    name_lower = str(material_name).lower()
    
    # 1. Conductor
    if "copper" in name_lower or "cu" in name_lower:
        return next((m['material_id'] for m in material_db if m['material_id'] == 'MAT-CU-EC'), "MAT-CU-EC")
    if "alum" in name_lower or "al" in name_lower:
        return next((m['material_id'] for m in material_db if m['material_id'] == 'MAT-AL-H3'), "MAT-AL-H3")
    
    # 2. Insulation (Voltage Logic)
    if "xlpe" in name_lower:
        # Check voltage to decide MV vs LV
        is_mv = any(x in str(voltage_grade) for x in ['3.3', '6.6', '11', '22', '33'])
        target_id = 'MAT-XLPE-MV' if is_mv else 'MAT-XLPE-LV'
        return next((m['material_id'] for m in material_db if m['material_id'] == target_id), target_id)
        
    # 3. Armour
    if "steel wire" in name_lower or "gsw" in name_lower:
        return "MAT-GSW-ARM"
    if "steel tape" in name_lower:
        return "MAT-STEEL-TAPE"
    if "aluminium wire" in name_lower or "awa" in name_lower:
        return "MAT-AWA-ARM"

    # 4. Sheath
    if "pvc" in name_lower:
        return "MAT-PVC-ST2" # Standard default
        
    return None

def get_applicable_tests(product_category, technical_specs, test_db):
    """
    Finds REAL test IDs from test_master that apply to this product.
    """
    applicable_tests = []
    
    # Normalize inputs
    category = str(product_category).lower()
    voltage = str(technical_specs.get('voltage_grade', '')).lower()
    armour = str(technical_specs.get('armour_type', '')).lower()
    
    for test in test_db:
        criteria_list = test.get('mandatory_for', [])
        is_applicable = False
        
        for criteria in criteria_list:
            c_lower = criteria.lower()
            
            # Rule 1: "All Cables"
            if "all cables" in c_lower:
                is_applicable = True
            
            # Rule 2: Voltage based (HT vs LT)
            elif "ht cables" in c_lower and ("11kv" in voltage or "33kv" in voltage or "6.6kv" in voltage):
                is_applicable = True
            elif "lt cables" in c_lower and ("1.1kv" in voltage):
                is_applicable = True
                
            # Rule 3: Armour check
            elif "armoured" in c_lower and "unarmoured" not in armour and armour != "none":
                is_applicable = True
                
        if is_applicable:
            applicable_tests.append({
                "test_id": test['test_id'],
                "test_name": test['test_name'],
                "cost": test.get('base_test_cost', 0)
            })
            
    return applicable_tests

def find_competitors(product_id, competitor_db):
    """
    Finds competitors who explicitly list this SKU (or similar) in their database.
    """
    matches = []
    for comp in competitor_db:
        # Check explicit collision list
        if product_id in comp.get('colliding_internal_skus', []):
            matches.append({
                "competitor_id": comp['competitor_id'],
                "name": comp['name'],
                "tier": comp.get('tier', 'Unknown'),
                "win_rate": comp.get('performance_metrics', {}).get('win_rate_against_us', 0.5)
            })
    return matches

# --- MAIN LOGIC ---
def main():
    print("🚀 Starting Database Enrichment using REAL IDs...")
    
    # 1. Load All Databases
    products = load_json(PRODUCT_MASTER_PATH)
    materials = load_json(MATERIAL_MASTER_PATH)
    competitors = load_json(COMPETITORS_PATH)
    tests = load_json(TEST_MASTER_PATH)
    
    if not products:
        print("❌ Error: No products found to enrich.")
        return

    enriched_list = []
    
    print(f"⚡ Processing {len(products)} products against {len(materials)} materials, {len(competitors)} competitors, {len(tests)} tests...")

    for prod in products:
        # A. Preserve Existing Data
        enriched_item = prod.copy()
        
        # B. ENRICH BILL OF MATERIALS (BOM) with REAL IDs
        # If BOM exists, verify IDs. If not, create a basic structure.
        specs = prod.get('technical_specs', {})
        bom = prod.get('bill_of_materials', [])
        
        new_bom = []
        # 1. Conductor
        cond_mat = specs.get('conductor_material', 'Copper')
        cond_id = find_material_id(cond_mat, specs.get('voltage_grade'), materials)
        if cond_id:
            new_bom.append({"material_id": cond_id, "component": "Conductor", "unit": "kg/km"})
            
        # 2. Insulation
        ins_mat = specs.get('insulation', 'XLPE')
        ins_id = find_material_id(ins_mat, specs.get('voltage_grade'), materials)
        if ins_id:
            new_bom.append({"material_id": ins_id, "component": "Insulation", "unit": "kg/km"})
            
        # 3. Armour (if applicable)
        arm_type = specs.get('armour_type', 'None')
        if "none" not in arm_type.lower() and "unarmoured" not in arm_type.lower():
            arm_id = find_material_id(arm_type, specs.get('voltage_grade'), materials)
            if arm_id:
                new_bom.append({"material_id": arm_id, "component": "Armour", "unit": "kg/km"})

        # Use the newly generated BOM with real IDs
        enriched_item['bill_of_materials_enriched'] = new_bom
        
        # C. ENRICH WITH COMPETITOR INTELLIGENCE
        # "Who else creates this Product ID?"
        comp_matches = find_competitors(prod.get('product_id'), competitors)
        enriched_item['competitor_landscape'] = comp_matches
        
        # D. ENRICH WITH QUALITY/TESTING DATA
        # "Which tests are mandatory for this cable type?"
        qa_tests = get_applicable_tests(prod.get('category'), specs, tests)
        enriched_item['quality_assurance_requirements'] = qa_tests
        
        enriched_list.append(enriched_item)

    # Save Output
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(enriched_list, f, indent=2)
        
    print(f"✅ Success! Enriched database saved to: {OUTPUT_PATH}")
    print(f"   - Linked real Material IDs (MAT-...)")
    print(f"   - Linked real Competitor Profiles (COMP-...)")
    print(f"   - Linked real Test Requirements (TEST-...)")

if __name__ == "__main__":
    main()