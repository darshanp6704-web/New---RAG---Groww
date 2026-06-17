# Implementation Plan: Mutual Fund FAQ Assistant (Facts-Only RAG)

This document maps out the phased implementation plan to build the Mutual Fund FAQ Assistant.

---

## Phase 1: Environment & Project Setup
Initialize the project structure, dependencies, and environment configuration.

- **Tasks**:
  1. Create a Python virtual environment (`python3 -m venv venv`).
  2. Setup project folder structure:
     ```text
     ├── docs/                 # Documentation (Problem Statement, Architecture)
     ├── src/
     │   ├── ingestion/        # Scrapers, parsers, and DB ingestion
     │   ├── engine/           # Retrieval, intent classification, LLM prompt logic
     │   ├── ui/               # Streamlit application UI
     │   └── config.py         # App configuration & environment variables
     ├── data/                 # Raw PDFs and local vector DB storage
     ├── requirements.txt      # Dependency list
     └── implementation.md     # This plan
     ```
  3. Prepare `requirements.txt` with essential dependencies:
     - Frameworks: `fastapi`, `uvicorn`, `streamlit`
     - RAG/Embeddings: `langchain`, `langchain-community`, `chromadb`, `sentence-transformers`
     - Scrapers/Parsers: `beautifulsoup4`, `requests`, `pypdf`
     - Utilities: `python-dotenv`, `pydantic`

---

## Phase 2: Corpus Definition & Ingestion (Offline Pipeline)
Curate documents from a single selected Asset Management Company (AMC) and build the data processing pipeline.

  - **Tasks**:
  1. **Select AMC & Schemes [Completed]**: Focus on **HDFC Mutual Fund** schemes hosted on Groww and configure the target ingestion URLs:
     - https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
     - https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
     - https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth
     - https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth
     - https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth
  2. **Scraper & Parser Script [Completed]**:
     - Implement python scripts in `src/ingestion/fetch.py` to fetch HTML pages and save them in `data/raw/`.
     - Implement a robust HTML parser `src/ingestion/parse.py` to extract text along with metadata (Source URL, Last Updated Date, fetch timestamp).
  3. **Chunking & Vector Storage [Completed]**:
     - **Chunking Strategy**: Adopt **Single-Scheme Profile Chunking (Document-as-a-Chunk)**. Each fund's compiled `summary_text` (approx. 1,000–1,500 characters) will be stored as a single, atomic document chunk in ChromaDB. This prevents key numeric parameters (NAV, minimum investment, exit load, expense ratio) from being decoupled or cross-contaminated with other schemes.
     - Generate embeddings using a local HuggingFace/SentenceTransformers model (e.g., `all-MiniLM-L6-v2`).
     - Load chunks and metadata into a local ChromaDB instance stored under `data/vector_db/`.

---

## Phase 3: Intent Classification & Refusal Engine (Guardrails) [Completed]
Enforce strict safety controls to filter out advisory queries before they reach the generation phase.

- **Tasks**:
  1. **Intent Classifier [Completed] (`src/engine/guardrails.py`)**:
     - Implement a semantic rule-based/regex filter combined with a zero-shot prompt classification to identify advisory/subjective/recommendation queries (e.g. "which is the best fund to buy?", "should I invest in ELSS?").
  2. **Refusal Engine [Completed]**:
     - Map flagged queries directly to static refusal templates returning educational links (e.g. AMFI/SEBI).
     - Ensure zero LLM hallucination for out-of-bounds/advisory prompts.

---

## Phase 4: Core Retrieval & LLM Generation (Query Pipeline) [Completed]
Implement the core facts-only RAG loop.

- **Tasks**:
  1. **Retriever [Completed] (`src/engine/retriever.py`)**:
     - **Strategy**: Implement **Metadata-Scoped Filtered Retrieval**. Parse the query to identify which of the 5 HDFC schemes is referenced.
     - **Metadata Filter (K=1)**: If a specific scheme is identified (e.g. Mid-Cap, Defence), query ChromaDB with a strict metadata filter (e.g. `where={"scheme_name": "<fund_name>"}`) to retrieve exactly `k=1` chunk. This prevents parameter mixing and guarantees context isolation.
     - **Fallback Search (K=2)**: If no specific fund is referenced in the query, run a fallback semantic vector similarity search across all documents with `k=2`.
  2. **Prompt Engineering [Completed] (`src/engine/generator.py`)**:
     - Design strict system instructions requiring response constraints:
       - Factual, objective answers only.
       - Maximum 3 sentences.
       - Exactly one citation link in format: `Source: <source_url>`.
       - Last updated date footer: `Last updated from sources: <date>`.
  3. **LLM Integration [Completed]**:
     - Connect to the LLM backend via Groq API (utilizing models like `llama-3.1-70b-versatile` or `llama-3.1-8b-instant`) with `temperature = 0`.
  4. **Post-Validation Parser [Completed]**:
     - Run a regex-based programmatic check on the LLM output to verify it meets length limits, contains a valid source link, and includes the footer.

---

## Phase 5: Streamlit User Interface [Completed]
Develop a clean and premium front-end for users.

- **Tasks**:
  1. **Layout Design [Completed] (`src/ui/app.py`)**:
     - Create a modern, responsive layout.
     - Include a high-visibility disclaimer at the top: **“Facts-only. No investment advice.”**
     - Display a welcome message and a list of 3 clickable example questions (e.g., "What is the exit load for HDFC Gold ETF?", "What is the lock-in period for ELSS?", "Should I invest in HDFC Mid-Cap Fund?").
  2. **Interactive Chat [Completed]**:
     - Stream answers directly or present them in a clear, card-based interface.
     - Differentiate factual answers from refusal answers visually.

---

## Phase 6: Ingestion Pipeline Scheduler [Completed]
Implement a daily background scheduler to refresh the vector store automatically.

- **Tasks**:
  1. **Scheduler Daemon [Completed] (`src/ingestion/scheduler.py`)**:
     - Implement timezone-aware runtime calculation targeting **10:00 AM IST** (UTC +5:30) daily.
     - Sequence execution flow: download latest Groww HTML files -> parse profiles to JSON -> upsert updated embeddings to ChromaDB.
     - Implement robust error catching to ensure single download failures don't crash the persistent daemon loop.
     - Output log tracing to `data/scheduler.log`.
  2. **Dry-Run CLI Trigger [Completed]**:
     - Support a `--now` argument to force execution of the ingestion pipeline immediately for manual testing and validation.

---

## Verification Plan

### 1. Ingestion Check
- Verify ChromaDB collection counts match chunk sizes and metadata profiles.

### 2. Guardrail Testing
- **Test Case A**: Input: *"What is the expense ratio for HDFC Large Cap Fund?"*
  - **Expected**: Fact-based response $\le 3$ sentences + citation + date footer.
- **Test Case B**: Input: *"Should I buy HDFC Mid-Cap Fund?"*
  - **Expected**: Polite refusal stating advisory queries are not allowed + AMFI/SEBI links.
- **Test Case C**: Input: *"Which mutual fund has the highest return?"*
  - **Expected**: Refusal or redirection to official factsheet links.

### 3. UI Check
- Ensure Streamlit application runs locally via `streamlit run src/ui/app.py`.
- Confirm disclaimer banner and example questions are interactive.
