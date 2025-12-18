from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
import datetime
from dotenv import load_dotenv

# 1. LOAD ENV VARS IMMEDIATELY
load_dotenv()

# --- IMPORT AGENTS ---
from main_agent import MainAgent
from agents.tech_agent import RealTechAgent
from agents.pricing_agent import RealPricingAgent
from agents.priority_agent import RealPriorityAgent

app = Flask(__name__, template_folder='templates')
app.secret_key = "super_secret_key" 

# Initialize Orchestrator
agent = MainAgent()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DB_FOLDER = os.path.join(BASE_DIR, "database") 
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "rfp_docs")

# Main Database File
CENTRAL_DB = os.path.join(DB_FOLDER, "central_rfp_database.json")

# SECURITY KEY
ADMIN_PASSKEY = "sexymono"

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)

# --- HELPER FUNCTIONS ---
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return []
    return []

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

# ==============================================================================
# ROUTES
# ==============================================================================

@app.route('/')
def dashboard():
    """
    HOMEPAGE: Loads the database and displays the Executive Dashboard.
    """
    data = load_json(CENTRAL_DB)
    
    # 1. Calculate KPIs
    active_rfps = [r for r in data if not r.get('is_archived')]
    total_val = 0
    for r in active_rfps:
        # Safe access to nested pricing data
        val = r.get('pricing_agent_output', {}).get('financial_summary', {}).get('final_bid_value', 0)
        total_val += val
    
    kpi = {
        "count": len(active_rfps),
        "val": total_val
    }
    
    # 2. Sort by Rank (Rank 1 at top, unranked at bottom)
    # RFPs with no rank get 999 to push them to the end
    data.sort(key=lambda x: x.get('sales_agent_2_output', {}).get('rank', 999))

    return render_template('dashboard.html', rfps=data, kpi=kpi)

@app.route('/upload_page')
def upload_page():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'rfp_file' not in request.files:
        flash("No file part", "error")
        return redirect(request.url)
        
    file = request.files['rfp_file']
    if file.filename == '':
        flash("No selected file", "error")
        return redirect(request.url)

    if file:
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # --- FEATURE: AUTO VS MANUAL FLOW ---
        # Get mode from form (default to 'auto')
        mode = request.form.get('flow_mode', 'auto')
        auto_mode = (mode == 'auto')

        # Pass auto_mode to the main agent
        rfp_id = agent.process_rfp(filepath, filename, auto_mode=auto_mode)
        
        flash(f"RFP Uploaded! ID: {rfp_id}. Workflow: {mode.upper()}", "success")
        return redirect(url_for('dashboard'))

@app.route('/products')
def products():
    """
    DISPLAYS PRODUCT CATALOG
    """
    file_path = os.path.join(DB_FOLDER, "product_master_enriched.json")
    raw_data = load_json(file_path)
    
    # Normalize data list
    products = []
    if isinstance(raw_data, list):
        products = raw_data
    elif isinstance(raw_data, dict):
        products = raw_data.get('products', []) or raw_data.get('items', []) or list(raw_data.values())

    return render_template('products.html', products=products)



@app.route('/clients')
def clients():
    """ DISPLAYS CLIENT DATABASE """
    file_path = os.path.join(DB_FOLDER, "client_master.json")
    clients = load_json(file_path)
    return render_template('clients.html', clients=clients)

@app.route('/competitors')
def competitors():
    """ DISPLAYS COMPETITOR INTELLIGENCE """
    file_path = os.path.join(DB_FOLDER, "competitors.json")
    competitors = load_json(file_path)
    return render_template('competitors.html', competitors=competitors)

@app.route('/rfp/<rfp_id>')
def view_rfp(rfp_id):
    data = load_json(CENTRAL_DB)
    rfp = next((item for item in data if item['rfp_unique_id'] == rfp_id), None)
    if not rfp: return "RFP Not Found", 404
    return render_template('rfp_detail.html', rfp=rfp)

# --- AGENT RE-RUN LOGIC ---
@app.route('/run_agent/<agent_type>/<rfp_id>')
def run_specific_agent(agent_type, rfp_id):
    data = load_json(CENTRAL_DB)
    record = next((item for item in data if item['rfp_unique_id'] == rfp_id), None)
    
    if not record:
        flash(f"RFP {rfp_id} not found.", "error")
        return redirect(url_for('dashboard'))
        
    try:
        # 1. TECH RE-RUN
        if agent_type == 'tech':
            flash(f"Re-running Technical Analysis for {rfp_id}...", "info")
            if not record.get('sales_agent_output'):
                flash("Sales data missing. Cannot run Tech Agent.", "error")
            else:
                tech_bot = RealTechAgent()
                tech_output = tech_bot.process_rfp_data(record['sales_agent_output'])
                
                record['tech_agent_output'] = tech_output
                record['processing_stage_tracker']['tech_agent'] = 'Completed'
                record['status'] = 'Technical Analysis Done'
                
                # If Pricing was already done, mark it pending to force update
                if record['processing_stage_tracker']['pricing_agent'] == 'Completed':
                     record['processing_stage_tracker']['pricing_agent'] = 'Pending'
                
                save_json(CENTRAL_DB, data)
                flash("Technical Analysis Updated!", "success")

        # 2. PRICING RE-RUN
        elif agent_type == 'pricing':
            flash(f"Re-calculating Pricing for {rfp_id}...", "info")
            
            # Check dependencies
            tech_status = record.get('processing_stage_tracker', {}).get('tech_agent')
            if tech_status not in ['Completed', 'Completed (Manual)']:
                 flash("Tech analysis pending. Please run Tech Agent first.", "warning")
            else:
                pricing_bot = RealPricingAgent()
                pricing_output = pricing_bot.process_pricing(record)
                
                record['pricing_agent_output'] = pricing_output
                record['processing_stage_tracker']['pricing_agent'] = 'Completed'
                record['status'] = 'Bid Ready for Review'
                
                save_json(CENTRAL_DB, data)
                
                # Auto-update Priority whenever price changes
                try: RealPriorityAgent().recalculate_all_priorities()
                except: pass
                
                flash("Pricing Updated! New Audit Report Generated.", "success")

        # 3. PRIORITY RE-RUN
        elif agent_type == 'priority':
            flash("Recalculating Global Priority Queue...", "info")
            RealPriorityAgent().recalculate_all_priorities()
            flash("Priority Queue Updated.", "success")

    except Exception as e:
        flash(f"Agent Error: {str(e)}", "error")
        print(f"Error: {e}")

    return redirect(url_for('view_rfp', rfp_id=rfp_id))

@app.route('/archive_rfp/<rfp_id>')
def archive_rfp(rfp_id):
    agent.toggle_archive_status(rfp_id)
    # Trigger Priority Re-Calc on archive toggle
    try: RealPriorityAgent().recalculate_all_priorities()
    except: pass
    return redirect(url_for('dashboard'))

@app.route('/delete_rfp/<rfp_id>')
def delete_rfp(rfp_id):
    data = load_json(CENTRAL_DB)
    # Remove record
    data = [d for d in data if d['rfp_unique_id'] != rfp_id]
    save_json(CENTRAL_DB, data)
    
    # Re-calculate ranks for everyone else
    try: RealPriorityAgent().recalculate_all_priorities()
    except: pass
    
    flash(f"RFP {rfp_id} deleted.", "success")
    return redirect(url_for('dashboard'))

# --- DATA MANAGER ROUTE (Updated for Robustness) ---
@app.route('/manage/<filename>', methods=['GET', 'POST'])
def manage_db(filename):
    file_path = os.path.join(DB_FOLDER, f"{filename}.json")
    
    if request.method == 'POST':
        user_key = request.form.get('passkey', '')
        if user_key != ADMIN_PASSKEY:
            flash("Invalid Admin Passkey.", "error")
            return redirect(url_for('manage_db', filename=filename))

        try:
            raw_json = request.form['json_data']
            updated_data = json.loads(raw_json)
            
            # Save the updated data
            save_json(file_path, updated_data)
            
            # If products changed, re-run priority agent to update scores
            if filename == 'product_master_enriched':
                try: RealPriorityAgent().recalculate_all_priorities()
                except: pass
                
            flash(f"{filename} updated successfully.", "success")
            return redirect(url_for('manage_db', filename=filename))
        except Exception as e:
            flash(f"Error saving data: {e}", "error")

    # --- CRITICAL FIX: DATA NORMALIZATION ---
    # This guarantees 'data' is always a list, even if the file wraps it in 'products': [...]
    raw_data = load_json(file_path)
    data = []
    
    if isinstance(raw_data, list):
        data = raw_data
    elif isinstance(raw_data, dict):
        # Unpack wrapped lists if they exist
        data = (
            raw_data.get('products') or 
            raw_data.get('items') or 
            raw_data.get('data') or 
            list(raw_data.values())
        )

    titles = {
        "client_master": "Client Database",
        "competitors": "Competitor Intelligence",
        "material_master": "Raw Material Pricing",
        "product_master_enriched": "Product Catalog (Enriched)",
        "logistic_master": "Logistics Rates",
        "test_master": "Testing Standards"
    }
    title = titles.get(filename, filename.replace('_', ' ').title())
    
    return render_template('data_manager.html', data=data, title=title, filename=filename)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        try:
            new_config = {
                "sales_config": {
                    "default_priority_threshold": int(request.form.get('sales_priority', 75)),
                    "high_value_client_multiplier": float(request.form.get('sales_multiplier', 1.2)),
                    "deadline_warning_days": int(request.form.get('deadline_days', 5))
                },
                "tech_config": {
                    "strict_compliance_mode": 'strict_mode' in request.form,
                    "competitor_match_threshold": float(request.form.get('comp_threshold', 0.85)),
                    "allow_alternative_materials": False
                },
                "pricing_config": {
                    "base_margin_percent": float(request.form.get('base_margin', 0.18)),
                    "competitor_undercut_percent": float(request.form.get('price_undercut', 2.0)),
                    "logistics_rate_per_km_ton": float(request.form.get('price_logistics', 12.5)),
                    "packaging_cost_per_drum": int(request.form.get('price_pkg', 12000)),
                    "testing_cost_base": 15000
                },
                "priority_config": {
                    "weight_product_fit": float(request.form.get('w_product', 0.4)),
                    "weight_relationship": float(request.form.get('w_rel', 0.4)),
                    "weight_urgency": float(request.form.get('w_urgency', 0.2)),
                    "max_urgency_days": int(request.form.get('max_days', 90))
                }
            }
            with open(SETTINGS_FILE, 'w') as f: json.dump(new_config, f, indent=2)
            try: RealPriorityAgent().recalculate_all_priorities()
            except: pass
            flash("Configuration Saved.", "success")
        except Exception as e:
            flash(f"Error saving settings: {e}", "error")
            
    if not os.path.exists(SETTINGS_FILE): config = {}
    else:
        with open(SETTINGS_FILE, 'r') as f: config = json.load(f)
    return render_template('settings.html', config=config)

if __name__ == '__main__':
    app.run(debug=True, port=5000)