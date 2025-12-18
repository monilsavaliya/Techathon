import json
import csv
import os

# -------- FILE PATHS --------
input_json = "extracted_rfp.json"
output_csv = "rfp_summary.csv"   # existing OR new CSV

# -------- LOAD JSON --------
with open(input_json, "r", encoding="utf-8") as f:
    data = json.load(f)

# -------- EXTRACT FIELDS --------
rfp_id = data.get("rfp_unique_id", "Not specified")

company_name = (
    data.get("sales_agent_output", {})
        .get("summary", {})
        .get("client_name", "Not specified")
)

submission_deadline = (
    data.get("sales_agent_output", {})
        .get("summary", {})
        .get("submission_deadline", "Not specified")
)

line_items = (
    data.get("sales_agent_output", {})
        .get("line_items_extracted", [])
)

product_names = [
    item.get("raw_description", "")
    for item in line_items
    if item.get("raw_description")
]

product_names_str = ", ".join(product_names)

# -------- CHECK IF CSV EXISTS --------
file_exists = os.path.isfile(output_csv)

# -------- WRITE / APPEND CSV --------
with open(output_csv, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    # Write header ONLY if file does not exist
    if not file_exists:
        writer.writerow([
            "RFP_ID",
            "Company_Name",
            "Submission_Deadline",
            "Product_Names"
        ])

    # Append current RFP row
    writer.writerow([
        rfp_id,
        company_name,
        submission_deadline,
        product_names_str
    ])
