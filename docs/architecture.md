# Architecture, Data Flow &amp; Trust Boundaries

## 1. System overview

Terraledger is a modular monolith (see [ADR-001](#adr-001-modular-monolith-over-microservices)
below) with four cooperating layers:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (React SPA)                                                │
│  Served by nginx · no direct DB or filesystem access                 │
└───────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTPS / REST (JSON)
┌───────────────────────────────▼───────────────────────────────────────┐
│  Backend API (FastAPI)                                                │
│  applications · documents · review · analytics · assistant · ml       │
└───────┬───────────┬────────────┬─────────────┬──────────────┬────────┘
        │            │            │             │              │
   ┌────▼───┐   ┌────▼─────┐ ┌────▼──────┐ ┌────▼───────┐ ┌────▼─────┐
   │Extract-│   │Validation│ │  Fraud    │ │  Scoring   │ │    ML     │
   │  ion   │   │  Engine  │ │ Detection │ │  Engine    │ │ (GBM+SHAP)│
   └────┬───┘   └──────────┘ └───────────┘ └────────────┘ └──────────┘
        │
   ┌────▼──────────────────────────────────────────────────────────┐
   │  Local object storage (documents) + PostgreSQL (all records)   │
   └──────────────────────────────────────────────────────────────┘
```

## 2. End-to-end data flow

```
Applicant submits
      │
      ▼
[Application created]  status=SUBMITTED
      │
      ▼
[Documents uploaded]  -> stored locally, content-hashed, never leave
      │                  the deployment
      ▼
POST /applications/{id}/process
      │
      ▼
PROCESSING  -> extraction_service: text/OCR/xlsx amounts, language
      │          detection, structured field extraction
      ▼
VALIDATED   -> validation_service: completeness, eligibility,
      │          contradiction checks (all config-driven, see
      │          app/rules/*.yaml)
      ▼
      +-------> fraud_service: duplicate / document-reuse / date
      │           anomaly signals
      ▼
AI_ANALYZED -> scoring_service: deterministic weighted rubric
      │          + ml_scoring_service: GBM prediction + SHAP
      │          explanation (only if a model has been trained)
      ▼
REVIEW_PENDING -> assigned to a reviewer
      │
      ▼
UNDER_REVIEW -> reviewer approves / rejects / requests info
      │           (override requires a reason; both AI recommendation
      │            and human decision are recorded)
      ▼
APPROVED / REJECTED / NEEDS_INFO -> CLOSED
```

Every arrow above also writes exactly one `AuditLog` row (see
`app/services/audit_service.py`), so the full history is reconstructable
from that table alone.

## 3. Trust boundaries

| Boundary | What crosses it | Control |
|---|---|---|
| Browser ↔ Backend | JSON over HTTPS, uploaded files | CORS allow-list (`CORS_ORIGINS`), input validation via Pydantic schemas |
| Backend ↔ Database | All structured records | Local network only in Docker Compose (`eco-review-net`); not exposed publicly by default |
| Backend ↔ Local storage | Raw uploaded documents | Filesystem path scoped per-application; documents are never served directly, only processed |
| Backend ↔ AI provider | Only if `AI_PROVIDER=openai` | See §4 — restricted data never crosses this boundary by design |
| Backend ↔ ML model | Feature vectors (numeric only, see `app/ml/feature_engineering.py`) | Fully local inference; no document content or PII is ever a model feature |

## 4. Data sovereignty control

Every `Application` record is tagged `sensitivity: RESTRICTED | SYNTHETIC`
(`app/models/enums.py::DataSensitivity`). The **model/provider abstraction**
(`app/services/ai_provider.py`) is the single choke point for any call that
could leave the deployment:

- `AI_PROVIDER=mock` (default): `MockAIProvider` is fully deterministic,
  template-based, and makes zero network calls. This is what an air-gapped
  or on-prem deployment should run in production.
- `AI_PROVIDER=openai`: opt-in only, intended for development against
  synthetic data. No code path automatically routes a `RESTRICTED`
  application's raw document text to this provider — summaries and
  explanations are built from structured fields (scores, validation
  messages) rather than raw uploaded text.

The ML model (`app/ml/`) never calls out at all — training and inference
are both pure local scikit-learn/SHAP computation.

## 5. Configurability (no hardcoded business logic)

- `app/rules/eligibility_rules.yaml` — per-scheme budget ranges, required
  documents, contradiction tolerance, certificate age limits.
- `app/rules/scoring_weights.yaml` — the scoring rubric and risk/recommendation
  thresholds.

Adding a new government scheme, or re-tuning what counts as "high risk,"
is a YAML edit — never a code change or redeploy of business logic.

## 6. ADRs

### ADR-001: Modular monolith over microservices
For a POC of this scope, a modular FastAPI monolith with clearly separated
service modules (`extraction`, `validation`, `fraud`, `scoring`, `ml`,
`workflow`, `assistant`) gives the same separation-of-concerns benefits as
microservices without the operational overhead of a POC-stage team running
a service mesh. Each service module has a single responsibility and could
be extracted into its own deployable unit later without a rewrite — the
`AIService`/provider-abstraction pattern in particular is already
service-boundary-shaped.

### ADR-002: Deterministic scoring stays authoritative
The ML model (`app/ml/`) is deliberately a *second opinion*, not the score
of record. `scoring_service.compute_score()` computes the rule-based total
first; the ML prediction can only add a concern + risk bump on
disagreement, never silently change the recommendation. This keeps the
number reviewers see reproducible and auditable independent of model
drift.

### ADR-003: SHAP + GradientBoostingClassifier over a black-box model
`shap.TreeExplainer` gives exact (non-sampled) per-prediction attributions
for tree ensembles, which matters when the explanation is shown directly
to a government reviewer. A more complex model (e.g. a neural net) would
need a slower, approximate explainer (KernelSHAP) for a marginal accuracy
gain that isn't the bottleneck at this POC's data scale.
