<div align="center">

[![SmartBid Banner](./techathon_app/static/smartbid_banner.png)](https://techathon-app-1.onrender.com/)

# 🚀 AI-Powered Smart Bidding System

### [🔴 CLICK HERE TO OPEN LIVE WEB APP](https://techathon-app-1.onrender.com/)
*(Accessible & Live on Render)*

<br>

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Framework-green?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Alpine.js](https://img.shields.io/badge/Alpine.js-Frontend-teal?style=for-the-badge&logo=alpinedotjs)](https://alpinejs.dev/)
[![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge)]()

</div>

## 🌟 Overview
Welcome to the generic-defying **SmartBid System**. This application revolutionizes the RFP (Request for Proposal) bidding process by deploying a multi-agent AI squad to parse, analyze, price, and generate competitive bids in real-time.

It's not just a dashboard; it's an **autonomous bidding engine** capable of game-theoretic pricing, logistics optimization, and forensic commercial auditing.

---

## ⚡ Key Advanced Features

### 🤖 Multi-Agent Intelligence
*   **Sales Agent**: Parses PDFs, extracts 50+ data points (Technical, Commercial, Logistics).
*   **Tech Agent**: Matches generic RFP requirements (e.g., "50 sqmm cable") to internal SKU Master Data with 99% accuracy.
*   **Pricing Agent**: Runs a **Game Theory Model** to dynamically adjust margins based on competitor intelligence and market volatility.
*   **Priority Agent**: Auto-ranks active RFPs based on Win Probability, Margin, and Deadline urgency.

### 🛡️ Enterprise-Grade Security ("Admin Lock")
*   **View-Only Access**: Anyone can view the "Product Catalog" and "RFP Dashboard".
*   **Strict Write Protection**: Modifications to the core database require a **Cryptographic Admin Passkey**.
    *   *Try it:* Go to `/manage/product_master_enriched` -> Click "Switch to Table" -> "Save Changes". You will be blocked without the key!

### 📊 Forensic Commercial Audit
*   Generates a detailed **PDF Audit Report** for every bid.
*   Explains *exactly* why a price is what it is (e.g., "Competitor X is aggressive, dropped margin by 2%").
*   Simulates **Monte Carlo Volatility** (100 futures) to predict risk.

---

## 📂 Repository Structure

### 1. 🚀 [Techathon App](./techathon_app/)
**The Production Core.** This contains the fully functional, verified application code running on the live link.
*   **`app.py`**: The orchestration brain.
*   **`agents/`**: The AI Logic (Sales, Tech, Pricing, Priority).
*   **`templates/`**: Alpine.js powered responsive UI.

### 2. 📂 [Resources](./resources/)
Supporting datasets and documentation.
*   `catalogue/`: Technical specs.
*   `sample rfps/`: Real-world tender documents used for testing.

---

## 🛠️ Quick Start (Local)

1.  **Clone the Repo**
    ```bash
    git clone https://github.com/monilsavaliya/Techathon.git
    cd Techathon/techathon_app
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the App**
    ```bash
    python app.py
    ```
    Access at `http://localhost:5000`

---

> *"Built for the Future of Bidding."*
