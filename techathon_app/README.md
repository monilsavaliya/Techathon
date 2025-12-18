# Techathon Application (Main Project)

This is the **production-ready** version of the Techathon agentic application. It is built using Flask and orchestrates multiple AI agents to handle RFPs, pricing, and sales priority.

## 📂 Folder Structure

*   **`app.py`**: The entry point of the Flask application.
*   **`agents/`**: Contains the logic for individual agents:
    *   `pricing_agent.py`: Calculates margins and pricing strategies.
    *   `priority_agent.py`: Determines lead scores and sales priority.
    *   `tech_agent.py`: Handles technical specifications and matching.
    *   `real_sales_agent.py`: Manages the sales pipeline.
*   **`templates/`**: HTML templates for the frontend (`index.html`, `dashboard.html`, etc.).
*   **`static/`**: CSS, JavaScript, and other static assets.
*   **`database/`**: Active JSON databases used by the running app.

## 🚀 How to Run

1.  **Prerequisites**: Ensure you have Python installed.
2.  **Environment**: Create and activate a virtual environment (recommended).
3.  **Run**:
    ```bash
    python app.py
    ```
4.  **Access**: Open your browser and go to `http://localhost:5000` (or the port specified in the console).

## 🧩 Key Features
- **Automated RFP Analysis**: Agents parse and analyze incoming RFPs.
- **Dynamic Pricing**: Real-time margin calculation based on competitor data.
- **Sales Intelligence**: Prioritizes leads based on win probability and deal size.
