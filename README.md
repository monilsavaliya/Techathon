# Techathon Project Repository

Welcome to the **Techathon** project repository. This codebase is organized into three main components to ensure modularity and ease of use.

## Repository Structure

### 1. 🚀 [Techathon App](./techathon_app/)
**The Core Application**. This directory contains the main Flask application, agent logic, and the primary codebase for the final project.
*   **Run here**: `python app.py`
*   **Key Files**: `app.py`, `templates/`, `static/`, `agents/`

### 2. 📂 [Resources](./resources/)
**Assets & Data**. A collection of supporting files used by the application and for documentation.
*   **Contents**:
    *   `catalogue/`: Product specifications and PDFs.
    *   `explaination_videos/`: Demo videos and agent briefings.
    *   `sample rfps/`: Example Request for Proposal documents.
    *   `database_backup/`: JSON backups of the system databases.

### 3. 🏛️ [Legacy Agents](./legacy_agents/)
**Archive**. Contains experimental or standalone versions of agents developed during earlier phases.
*   **Purpose**: Reference code. These are not required to run the main application.

---

## Quick Start
To run the main application:

1.  Navigate to the app directory:
    ```bash
    cd techathon_app
    ```
2.  Install dependencies (if listed) or ensure environment is set up.
3.  Run the application:
    ```bash
    python app.py
    ```
