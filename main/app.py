from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
import datetime
from main_agent import MainAgent

app = Flask(__name__)
app.secret_key = "super_secret_key" 
agent = MainAgent()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
# Ensure this points to where your JSON files actually are
DB_FOLDER = os.path.join(BASE_DIR, "database") 
UPLOAD_FOLDER = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Main Database File
CENTRAL_DB = os.path.join(DB_FOLDER, "central_rfp_database.json")

# SECURITY KEY (Hardcoded as requested)
ADMIN_PASSKEY = "sexymono"

def load_json(filepath):
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, 'r') as f: return json.load(f)
    except: return []

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def dashboard():
    data = load_json(CENTRAL_DB)
    active = [x for x in data if not x.get('is_archived', False)]
    archived = [x for x in data if x.get('is_archived', False)]
    
    total_val = 0
    high_pri = 0
    for x in active:
        try: total_val += int(x.get('pricing_agent_output', {}).get('financial_summary', {}).get('final_bid_value', 0))
        except: pass
        try: 
            if x.get('sales_agent_2_output', {}).get('priority_rank') == 'High': high_pri += 1
        except: pass

    # Sort by Priority
    active.sort(key=lambda x: x.get('sales_agent_2_output', {}).get('priority_score', 0), reverse=True)

    return render_template('dashboard.html', active=active, archived=archived, kpi={'val': total_val, 'count': len(active), 'high': high_pri})

# --- UPDATED DATABASE MANAGER WITH SECURITY ---
@app.route('/manage/<filename>', methods=['GET', 'POST'])
def manage_db(filename):
    file_path = os.path.join(DB_FOLDER, f"{filename}.json")
    
    if request.method == 'POST':
        # 1. SECURITY CHECK
        user_key = request.form.get('passkey', '')
        if user_key != ADMIN_PASSKEY:
            return f"<h1>403 Forbidden</h1><p>Invalid Admin Passkey. Access Denied.</p><a href='/manage/{filename}'>Go Back</a>", 403

        # 2. SAVE CHANGES
        try:
            raw_json = request.form['json_data']
            updated_data = json.loads(raw_json)
            save_json(file_path, updated_data)
            return redirect(url_for('manage_db', filename=filename))
        except Exception as e:
            return f"Error saving data: {e}"

    # LOAD DATA
    data = load_json(file_path)
    
    titles = {
        "client_master": "Client Database",
        "competitors": "Competitor Intelligence",
        "material_master": "Raw Material Pricing",
        "product_master": "Product Catalog",
        "logistic_master": "Logistics Rates",
        "test_master": "Testing Charges"
    }
    
    return render_template('data_manager.html', 
                           data=data, 
                           filename=filename, 
                           title=titles.get(filename, filename))

@app.route('/invoice/<rfp_id>')
def invoice_page(rfp_id):
    data = load_json(CENTRAL_DB)
    rfp = next((x for x in data if x['rfp_unique_id'] == rfp_id), None)
    if not rfp: return "RFP Not Found", 404
    return render_template('invoice.html', rfp=rfp, date=datetime.date.today())

@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    if request.method == 'POST':
        if 'rfp_file' not in request.files: return "No File", 400
        f = request.files['rfp_file']
        if f.filename == '': return "No File", 400
        
        save_path = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(save_path)
        
        rfp_id = agent.create_rfp_card(save_path)
        if rfp_id:
            agent.run_full_pipeline(rfp_id)
            return redirect(url_for('view_rfp', rfp_id=rfp_id))
            
    return render_template('upload.html')

@app.route('/rfp/<rfp_id>')
def view_rfp(rfp_id):
    data = load_json(CENTRAL_DB)
    rfp = next((x for x in data if x['rfp_unique_id'] == rfp_id), None)
    if not rfp: return "Not Found", 404
    return render_template('rfp_detail.html', rfp=rfp)

@app.route('/archive/<rfp_id>')
def archive(rfp_id):
    agent.toggle_archive(rfp_id)
    # If we just archived it, stay on Active to see it gone, or go to Junk?
    # Let's stay on active so the user sees the list shrink.
    return redirect(url_for('dashboard'))

@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    # 1. Handle Save
    if request.method == 'POST':
        try:
            new_settings = {
                "sales_config": {
                    "default_priority_threshold": int(request.form.get('sales_prio', 75)),
                    "high_value_client_multiplier": float(request.form.get('sales_mult', 1.2)),
                    "deadline_warning_days": int(request.form.get('sales_days', 5))
                },
                "tech_config": {
                    "strict_compliance_mode": 'tech_strict' in request.form,
                    "allow_alternative_materials": 'tech_alt' in request.form,
                    "competitor_match_threshold": float(request.form.get('tech_thresh', 0.85))
                },
                "pricing_config": {
                    "base_margin_percent": float(request.form.get('price_margin', 18.0)),
                    "logistics_rate_per_km_ton": float(request.form.get('price_logistics', 12.5)),
                    "packaging_cost_per_drum": int(request.form.get('price_pkg', 12000)),
                    "testing_cost_base": int(request.form.get('price_test', 15000)),
                    "competitor_undercut_percent": float(request.form.get('price_undercut', 2.0))
                }
            }
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(new_settings, f, indent=2)
                
            # Ideally, trigger a re-run of agents here to apply new settings
            return redirect(url_for('settings_page'))
            
        except Exception as e:
            return f"Error saving settings: {e}"

    # 2. Load Current Settings
    if not os.path.exists(SETTINGS_FILE):
        return "Settings file missing. Please create settings.json."
        
    with open(SETTINGS_FILE, 'r') as f:
        current_settings = json.load(f)
        
    return render_template('settings.html', config=current_settings)

if __name__ == '__main__':
    print(f">>> SERVER STARTED. Admin Passkey: {ADMIN_PASSKEY}")
    app.run(debug=True, port=5000)