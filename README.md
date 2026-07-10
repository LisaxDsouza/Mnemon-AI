# Recall AI - Semantic Memory Infrastructure

<!--
NOTE: GitHub only renders an inline, playable video for files uploaded through
its own asset pipeline (drag-and-drop into the README/issue/PR edit box on
github.com), which produces a `https://github.com/user-attachments/assets/...`
link. A .mp4 committed to the repo and referenced by a relative path, like the
<video> tag below, will NOT autoplay inline for everyone — GitHub's markdown
sanitizer strips `src` on non-whitelisted hosts in a lot of contexts, so it
often falls back to a plain download link instead of a player.

To get the guaranteed inline player:
  1. Open this file in the GitHub web editor (or start a new issue/PR).
  2. Drag "Mnemon Demo.mp4" into the text box — GitHub uploads it and inserts
     a working `user-attachments` link automatically.
  3. Replace the <video> block below with that inserted link, then delete
     this comment.
-->

<video src="Mnemon%20Demo.mp4" controls width="100%">
  Demo video — view it directly: <a href="Mnemon%20Demo.mp4">Mnemon Demo.mp4</a>
</video>

Recall AI is an agentic memory infrastructure platform that captures, structures, retrieves, and reconstructs a user’s digital learning and browsing history. It acts as a semantic memory layer for the web, tracking user engagement, identifying context sessions, and enabling intelligent retrieval through agentic workflows while maintaining strict, user-controlled privacy guardrails.

---

## 🏗️ System Architecture

```text
Browser Extension (Real-time tracking, blocklist validation, and pause state)
        ↓
FastAPI Ingestion Service (API Gateway, Capture Decision System, and DB layer)
        ↓
Background Extraction Pipeline (Readability, YouTube transcript, GitHub API, and PDF parsers)
        ↓
SQLite/PostgreSQL Database (ORM mapping for memory logs, sessions, and privacy rules)
        ↓
FAISS/Qdrant Vector Database (Dense semantic embedding index)
        ↓
Agentic Retrieval Console (Planner, Retriever, Timeline, Summarizer, and Reflection agents)
        ↓
Next.js Dashboard Frontend (Timeline visualizer, grouped sessions, agent chat, and privacy panel)
```

---

## 🛡️ Privacy & Exclusion Infrastructure

Recall AI treats privacy as a core engineering feature:
- **Default Domain Blocklist**: Automatic blocklist covering banking portal domains, auth services, password managers, and identity gates (e.g. `paypal.com`, `auth`, `signin`, `login`).
- **User Domain Exclusions**: Custom wildcard domain matches configurable in the dashboard or toggleable with a single click inside the extension popup.
- **Category Permissions**: Toggles for tracking Articles, YouTube, GitHub, PDFs, and Social Media/AI Chats.
- **Onboarding signup**: Initial configuration of settings when a user first enters the dashboard.
- **Interactive Controls**: Pausing capture for specific intervals (10m, 1h) or permanently resetting stored memory history.

---

## 📂 Project Directory Structure

```text
├── backend/                  # FastAPI Application
│   ├── database.py           # SQLAlchemy database configuration
│   ├── models.py             # SQLite/PostgreSQL schemas
│   ├── vector_store.py       # Dual FAISS & Qdrant vector manager
│   ├── parsers.py            # YouTube, GitHub, Web, PDF, and Search extractors
│   ├── clustering.py         # Temporal & semantic session clusterer
│   ├── agents.py             # Planner, Retriever, Timeline, Summarizer, Reflection agents
│   └── main.py               # Ingestion & Query REST endpoints
├── extension/                # Chrome Extension (Self-contained client)
│   ├── manifest.json         # Extension Manifest v3
│   ├── background.js         # Navigation tracker & backend communicator
│   ├── content.js            # Active timer & scroll depth listener
│   ├── popup.html            # Extension popup layout
│   ├── popup.js              # Pause, toggle-block, and tracking status panel
│   └── style.css             # Extension styling
├── frontend/                 # Next.js Dashboard Frontend
└── requirements.txt          # Python dependencies
```

---

## 🚀 Setup & Execution

### 1. Backend API

Ensure you have created a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_key
DATABASE_URL=sqlite:///./backend/recall_ai.db
UPLOAD_DIR=./backend/uploads
FAISS_INDEX_PATH=./backend/vector_db
```

Create the virtual environment, install python dependencies, and start the backend from the **project root directory** (running from the root ensures SQLite/FAISS paths resolve correctly):

**On Windows (PowerShell):**
```powershell
# Create the virtual environment inside backend/venv
python -m venv backend/venv

# Install dependencies
.\backend\venv\Scripts\pip install -r requirements.txt

# Run the backend
.\backend\venv\Scripts\python backend/main.py
```

**On macOS/Linux:**
```bash
# Create the virtual environment inside backend/venv
python3 -m venv backend/venv

# Install dependencies
./backend/venv/bin/pip install -r requirements.txt

# Run the backend
./backend/venv/bin/python backend/main.py
```

### 2. Next.js Dashboard

Navigate to the frontend folder, install node modules, and launch the development dashboard server:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to access the dashboard.

### 3. Chrome Extension

To install the extension for live capture:
1. Open Google Chrome and go to `chrome://extensions/`.
2. Toggle **Developer mode** in the top right.
3. Click **Load unpacked** in the top left.
4. Select the `extension` folder inside this project directory.
