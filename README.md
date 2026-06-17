# Mutual Fund FAQ Assistant (Facts-Only Q&A)

An AI-powered, compliance-first FAQ assistant for HDFC mutual fund schemes, inspired by the Groww product context. The assistant answers objective, verifiable queries by retrieving information exclusively from official public pages parsed into a local vector database. It strictly filters out personal information (PII), generic off-topic prompts, and advisory queries (recommendations or investment advice).

---

## 📈 Selected AMC & Schemes (Scope)
The ingestion corpus is strictly limited to the following **5 HDFC Mutual Fund schemes**:
1.  **HDFC Mid-Cap Opportunities Fund**: [groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)
2.  **HDFC Top 100 Fund (Large Cap)**: [groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth)
3.  **HDFC Small Cap Fund**: [groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth)
4.  **HDFC Gold ETF Fund of Fund**: [groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth)
5.  **HDFC Defence Fund**: [groww.in/mutual-funds/hdfc-defence-fund-direct-growth](https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth)

---

## 🛠️ Architecture Overview (RAG Approach)
The system is split into two pipelines:

### 1. Ingestion Pipeline (Offline)
*   **Web Scraper (`fetch.py`)**: Fetches raw pages, injects fetch timestamps, and tracks downloads in `manifest.json`.
*   **Content Parser (`parse.py`)**: Strips navigation chrome/headers/footers and extracts **9 key sections** (overview, expense_ratio, exit_load, minimum_investment, benchmark, tax, fund_management, investment_objective, fund_house).
*   **Single-Scheme Chunking**: Saves each scheme profile as a single, atomic chunk. This prevents numeric data points (like NAV or exit load) from being decoupled, eliminating parameter mixing.
*   **Vector Store (`vector_store.py`)**: Generates 384-dimensional dense vectors using a local `all-MiniLM-L6-v2` model and stores them in local **ChromaDB**.

### 2. Inference Pipeline (Online)
*   **Query Guardrail Classifier (`guardrails.py`)**:
    *   *PII Scanner*: Intercepts and rejects PAN cards, Aadhaar numbers, emails, phone numbers, or OTP sequences.
    *   *Advisory Interceptor*: Flags queries seeking recommendations or comparing funds (e.g. *"should I buy"*, *"which is better"*).
    *   *Zero-Shot LLM Routing*: Classifies user intent (factual, advisory, out_of_scope, ambiguous) using Groq API.
    *   *Refusal Engine*: Routes rejected requests to static, compliant templates with AMFI/SEBI links.
*   **Metadata-Scoped Retriever (`retriever.py`)**: Routes queries to the correct scheme based on keywords and queries ChromaDB with a strict metadata filter (`where={"scheme_name": "..."}`) with `k=1`, completely avoiding cross-scheme parameter hallucination.
*   **Post-Validation Generator (`generator.py`)**: Designs strict prompts (max 3 sentences, exactly 1 citation, date-updated footer) and programmatically corrects LLM outputs to guarantee formatting compliance.

---

## ⚡ Setup & Launch Instructions

### Prerequisites
*   Python 3.9+ installed on your system.

### 1. Clone & Initialize Environment
Clone the project files to your directory, navigate to the folder, and run:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory and copy the contents from `.env.example`:
```bash
cp .env.example .env
```
Fill in your Groq API Key:
```text
GROQ_API_KEY=gsk_your_actual_groq_api_key
```
*(Note: If no API key is provided, the backend automatically switches to a **Mock-Factual fallback** mode, allowing you to test the complete database retrieval and guardrail pipeline locally without calling the API).*

### 3. Run Ingestion (Optional)
The pre-scraped and parsed JSON profiles are already bundled. To re-run the full offline ingestion pipeline and rebuild the Chroma vector database:
```bash
# Step 1: Fetch raw pages
python3 src/ingestion/fetch.py

# Step 2: Parse sections
python3 src/ingestion/parse.py

# Step 3: Embed and Index into ChromaDB
python3 src/ingestion/vector_store.py
```

### 4. Launch the Streamlit Web Application
Run the Streamlit application from the root directory:
```bash
PYTHONPATH=. streamlit run src/ui/app.py
```
This will start a local web server (typically at `http://localhost:8501`) and automatically open it in your browser.

---

## ⚠️ Known Limitations
1.  **Scope Limit**: Limited exclusively to the 5 configured HDFC mutual fund URLs. Queries referencing other funds or general non-financial topics are systematically refused.
2.  **HTML Structure dependency**: The DOM parsing patterns in `parse.py` are mapped to the reference layout of Groww's desktop scheme pages. If Groww modifies its CSS class mappings or text structure, the parser might require regex tuning.
3.  **Local Embedding latency**: On the first run, the local SentenceTransformers model downloads and caches files (~90MB), which can result in a minor startup latency. Subsequent operations run with zero network overhead.

---

## ⚖️ Disclaimer Snippet
> **“Facts-only. No investment advice.”**
> All responses are extracted strictly from official AMC filings. The system does not provide performance predictions, comparative analysis, or buy/sell recommendations.
