# LAWGIC - From Contracts to Executable Business Rules

> **LAWGIC** is a production-quality AI contract intelligence platform that converts natural language contractual clauses into structured, machine-readable Legal Intermediate Representation (IR), validates those rules, executes them using a **deterministic rule engine**, allows users to perform what-if financial simulations, and generates transparent, auditable explanations that trace every result back to the original contract clause.

---

## 🌟 Key Differentiator

> *"Traditional contract AI helps users understand what a contract says. LAWGIC goes one step further by converting contractual language into executable logic."*

**The Core Pipeline**:
`CONTRACT → UNDERSTANDING → STRUCTURED LEGAL IR → VALIDATION → DETERMINISTIC EXECUTION → FINANCIAL RESULT → WHAT-IF SIMULATION → AUDITABLE EXPLANATION`

**Strict Architectural Rule**: The LLM **NEVER** performs final financial calculations. The LLM extracts and structures contractual text into JSON Legal IR. A pure Python **deterministic rule engine** executes all mathematical logic, caps, grace periods, discounts, and SLA deductions for 100% reproducible, zero-hallucination results.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic v2, PyPDF, python-docx, Pytest
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons, Recharts
- **Database**: SQLite (Zero-config out-of-the-box, PostgreSQL ready)
- **RAG & Vector Search**: SentenceTransformers / Cosine statutory law index
- **LLM Integrations**: OpenAI, Google Gemini, or Built-in Offline Mock Extractor

---

## 🚀 Quick Start Instructions

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows activate:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run pytest unit test suite
pytest

# Launch FastAPI backend server
uvicorn app.main:app --reload --port 8000
```

The backend server will start at `http://localhost:8000`. It automatically seeds the SQLite database with the demo contract (`ABC Tech Master Supplier Agreement`), extracted Legal IR rules, and initial execution history.

API Documentation is available at: `http://localhost:8000/docs`.

### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```

The application will launch at `http://localhost:3000`.

---

## 🧪 Running Automated Unit Tests

Run the test suite to verify deterministic math calculations, grace periods, penalty caps, and IR schema validation:

```bash
cd backend
pytest -v
```

Tests included:
- `test_late_payment_interest_execution`: Validates grace period deduction & monthly interest rate calculation.
- `test_delivery_delay_penalty_with_cap`: Validates weekly penalty rounding and 10% maximum liability cap enforcement.
- `test_volume_discount`: Validates volume tier discount application.
- `test_valid_rule_validation`: Validates schema checks and unknown variable flagging (`NEEDS_REVIEW`).
- `test_what_if_scenario_simulation`: Validates multi-scenario baseline vs scenario delta calculations.

---

## 📄 Demo Walkthrough (3-5 Minutes)

1. **Dashboard Overview**: View executive KPI metrics (Total Contracts, Clauses Extracted, Active Rules, Pending Reviews, Potential Penalties, Volume Discounts).
2. **Contracts Studio**: Open `ABC Tech Master Supplier Agreement` to inspect the 3-pane view (PDF/Text Viewer on left, Extracted Clauses in center, Deterministic Sandbox on right).
3. **Inspect Legal IR**: Click **View IR** on any clause card to view the machine-readable JSON representation.
4. **Deterministic Sandbox Execution**: Change parameters (e.g. Delivery Delay = 24 days) and click **Execute Deterministic Rules**. View step-by-step trace and subtotal.
5. **What-If Simulator**: Navigate to **What-If Simulator**, move delay sliders, and click **RUN WHAT-IF SIMULATION** to compare Baseline vs Scenario A vs Scenario B with visual bar charts and delta metrics.
6. **Auditable Explanation ("Show Evidence")**: Click **Show Evidence** on any step to open the transparent provenance modal showing original clause text, section number, page number, and decompiled logic.
