# INDUX — AI System Implementation PRD

**Project:** Mistranics / INDUX  
**Module:** AI-powered anomaly management and intelligent troubleshooting  
**Document type:** Backend and AI system implementation specification  
**Priority:** Prototype implementation  
**Architecture:** Extend existing backend; do not rebuild it

---

## 1. Project Context

INDUX is an industrial machine monitoring and troubleshooting platform.

The existing application already has a working backend. This implementation introduces the AI system as an additional capability that integrates with the existing infrastructure.

The AI system consists of two major subsystems:

1. **Anomaly Detection and Incident Management**
2. **AI Troubleshooting and Chatbot**

These subsystems must remain logically independent but communicate through standardized machine context, anomaly events and incident records.

### 1.1 Core responsibilities

**Anomaly Detection System**

- Evaluate incoming machine telemetry.
- Execute manufacturer-limit checks.
- Execute statistical anomaly detection using Isolation Forest.
- Aggregate detector outputs.
- Maintain anomaly incidents.
- Expose structured anomaly information to the troubleshooting system.

**AI Troubleshooting System**

- Provide a conversational troubleshooting interface.
- Understand operator questions.
- Retrieve relevant manufacturer documentation through RAG.
- Retrieve current and historical machine context.
- Correlate machine evidence with documentation.
- Generate structured troubleshooting recommendations.
- Maintain conversation history and operator feedback.

The AI system must never treat a statistical anomaly as a confirmed mechanical failure.

---

## 2. Critical Implementation Instruction: Audit Before Development

This is a mandatory first phase.

The backend is already functional. The implementation agent must understand its current architecture before changing anything.

### 2.1 Repository audit

Inspect the existing project and identify:

- Backend framework and application entry points.
- Existing API routes and endpoint conventions.
- Database technology and current schema.
- Existing database models and relationships.
- MQTT broker connection and subscription implementation.
- Sensor ingestion and telemetry processing pipeline.
- Existing 3-second processing mechanism.
- Existing 3-second and 15-second feature-window implementation.
- Detector A implementation.
- Detector B / Isolation Forest implementation.
- Existing manufacturer-limit storage and verification workflow.
- Existing PDF processing and document upload implementation.
- Existing vector database and embedding integration, if any.
- Existing LLM integration, if any.
- Existing WebSocket implementation.
- Existing frontend/backend communication patterns.
- Environment variables and configuration management.
- Existing logging and error-handling conventions.

### 2.2 Audit output

Before implementation, create:

`AI_SYSTEM_AUDIT.md`

It must contain:

| Area            | Existing implementation | Missing functionality     | Required action |
| --------------- | ----------------------- | ------------------------- | --------------- |
| MQTT            | Inspect                 | Identify gaps             | Reuse or extend |
| Telemetry       | Inspect                 | Identify gaps             | Reuse or extend |
| Feature windows | Inspect                 | Identify gaps             | Reuse or extend |
| Detector A      | Inspect                 | Identify gaps             | Reuse or extend |
| Detector B      | Inspect                 | Identify gaps             | Reuse or extend |
| Database        | Inspect                 | Identify missing entities | Extend schema   |
| PDF processing  | Inspect                 | Identify gaps             | Reuse or extend |
| Vector DB       | Inspect                 | Identify gaps             | Reuse or add    |
| LLM integration | Inspect                 | Identify gaps             | Reuse or add    |
| WebSocket       | Inspect                 | Identify missing events   | Extend          |

The audit must distinguish:

- Already implemented and working.
- Implemented but incomplete.
- Not implemented.
- Unclear and requiring verification.

Do not assume a feature is absent merely because its implementation is located somewhere unexpected.

### 2.3 Non-negotiable preservation rules

1. Do not replace the existing backend.
2. Do not create a second MQTT ingestion system.
3. Do not duplicate existing telemetry processing.
4. Do not create duplicate database models for information already stored.
5. Do not create a second WebSocket infrastructure if the existing one can be extended.
6. Do not replace working Detector A or Detector B implementations without identifying a specific defect.
7. Preserve existing API contracts unless a change is necessary and documented.
8. Do not introduce unnecessary microservices.
9. Do not reorganize the entire repository.
10. Keep the implementation small, understandable and easy to debug.

**The objective is integration, not architectural reinvention.**

---

## 3. Product Architecture

The proposed logical architecture is:

```text
                    EXISTING BACKEND
                          |
                    MQTT TELEMETRY
                          |
                  EXISTING PROCESSING
                          |
                FEATURE GENERATION
                   3s + 15s windows
                          |
             +------------+------------+
             |                         |
         DETECTOR A                DETECTOR B
     Manufacturer limits        Isolation Forest
             |                         |
             +------------+------------+
                          |
                 EVENT NORMALIZATION
                          |
              INCIDENT AGGREGATION
                          |
                 INCIDENT MANAGER
                          |
                SHARED MACHINE CONTEXT
                          |
               AI TROUBLESHOOTING
                          |
             +------------+------------+
             |                         |
        MACHINE CONTEXT             RAG SYSTEM
        AND HISTORY                 MANUALS
             |                         |
             +------------+------------+
                          |
                   LLM REASONING
                          |
                RESPONSE VALIDATION
                          |
                 CHATBOT INTERFACE
                          |
                 OPERATOR FEEDBACK
```

The architecture above describes logical responsibilities. These components may be implemented as modules within the existing backend application.

---

# PART A — ANOMALY DETECTION AND INCIDENT MANAGEMENT

## 4. Anomaly Detection Pipeline

### 4.1 Existing processing configuration

Preserve the following established design:

| Property               | Requirement                  |
| ---------------------- | ---------------------------- |
| Processing frequency   | Every 3 seconds              |
| Current feature window | 3 seconds                    |
| Temporal context       | 15 seconds                   |
| Detector A             | Manufacturer-approved limits |
| Detector B             | Isolation Forest             |
| Detector execution     | Independent evaluations      |

The feature generator should provide one combined feature row containing information from the current 3-second window and recent 15-second context.

Do not introduce another telemetry ingestion or processing loop if the existing backend already performs these functions.

### 4.2 Feature generation

The feature-generation module must:

1. Collect readings belonging to the current 3-second window.
2. Maintain rolling telemetry history for the previous 15 seconds.
3. Calculate the configured features.
4. Produce the combined feature row.
5. Associate the feature row with a machine ID and timestamp.
6. Handle missing and invalid sensor values explicitly.

Candidate features include:

- Mean.
- Minimum.
- Maximum.
- Standard deviation.
- Variance.
- Rate of change.
- Difference between recent windows.

The final feature list must be based on available sensor data and model validation. Do not arbitrarily introduce features that cannot be calculated reliably.

Preserve extrema when instantaneous limit violations matter. An average alone can hide a short-duration spike.

### 4.3 Detector A — Manufacturer Limit Checks

**Objective:** Detect violations of verified manufacturer operating limits.

The detector must retrieve approved limits from the existing authoritative database or configuration mechanism.

Basic evaluation:

`approved_min <= observed_value <= approved_max`

Required behaviour:

- Identify the correct machine and sensor parameter.
- Retrieve the active approved configuration.
- Check unit compatibility.
- Evaluate the observed measurement.
- Generate a limit-violation result when appropriate.
- Preserve the observed value and approved limits used.
- Record the limit configuration version.

Do not use unverified LLM-extracted limits.

If an approved limit is unavailable, report that the check could not be performed. Never treat unavailable limits as normal operation.

Where manufacturer limits vary by operating mode, use the correct applicable configuration.

### 4.4 Detector B — Isolation Forest

**Objective:** Identify statistically unusual machine behaviour.

Use the existing Isolation Forest implementation if it passes the repository audit.

The detector must:

1. Receive the combined feature row.
2. Validate its inputs.
3. Apply the expected preprocessing.
4. Execute the model.
5. Apply the configured anomaly threshold.
6. Produce a standardized result.
7. Record the model version.

Suggested output:

```json
{
	"detector": "DETECTOR_B",
	"machine_id": "MACHINE_001",
	"timestamp": "2026-11-02T12:30:00Z",
	"result": "ANOMALY",
	"anomaly_score": -0.72,
	"model_version": "iforest_v1",
	"features": {
		"temperature_mean": 65.2,
		"pressure_max": 13.5,
		"vibration_std": 0.82
	}
}
```

Values are illustrative.

Do not interpret the anomaly score as a probability of failure.

Do not retrain or replace an existing model automatically during this integration.

### 4.5 Standardized detector output

Both detectors must produce compatible structured results.

Each result should contain:

- Unique result ID.
- Machine ID.
- Detector name.
- Timestamp.
- Parameter or feature association.
- Result classification.
- Observed value where applicable.
- Relevant threshold or score.
- Configuration/model version.
- Evidence metadata.

The detectors must remain independent. A failure in one must not prevent the other from executing.

---

## 5. Event Aggregation and Incident Management

This is a new core requirement unless equivalent functionality already exists.

### 5.1 Distinction

**Detector result:** One evaluation by Detector A or Detector B.

**Anomaly event:** A normalized record of an abnormal observation.

**Incident:** A persistent or correlated machine condition containing one or more events and observations.

Repeated detector results must not create a new incident every three seconds.

### 5.2 Aggregation workflow

1. Receive detector results.
2. Normalize machine IDs, parameter IDs and timestamps.
3. Create standardized anomaly events.
4. Search for a matching active incident.
5. Attach the event to the incident if correlation criteria match.
6. Otherwise create a new incident.
7. Update incident metadata.
8. Persist the event and incident state.
9. Publish meaningful incident updates.

### 5.3 Incident correlation

Initially correlate using:

- Same machine.
- Same parameter or explicitly configured parameter group.
- Compatible event time.
- Existing active incident.

Do not automatically group unrelated abnormalities from the same machine into a single incident.

Use configurable correlation intervals. Do not hard-code an arbitrary time interval without documenting its purpose.

### 5.4 Deduplication

The system must distinguish between:

- Deduplicating repeated notifications.
- Preserving repeated observations.

Every relevant detector evaluation should remain available for incident history and trend analysis.

Repeated observations should update:

- Last detected timestamp.
- Observation count.
- Current severity.
- Trend information.
- Detector contributions.

Only meaningful changes should generate new operator-facing notifications.

### 5.5 Incident lifecycle

Implement the following initial lifecycle:

- `ACTIVE`
- `RECOVERING`
- `RESOLVED`
- `CLOSED`

Operator acknowledgement should be tracked separately from machine-condition state.

Recovery must use configurable persistence/hysteresis criteria rather than a single normal reading.

A resolved incident may be reopened if the same condition reappears within the defined correlation policy.

### 5.6 Incident data structure

Suggested schema:

```json
{
	"incident_id": "INC_001",
	"machine_id": "MACHINE_001",
	"status": "ACTIVE",
	"severity": "HIGH",
	"first_detected_at": "2026-11-02T12:30:00Z",
	"last_detected_at": "2026-11-02T12:30:06Z",
	"observation_count": 3,
	"affected_parameters": ["pressure"],
	"detectors": ["DETECTOR_A", "DETECTOR_B"],
	"acknowledged": false,
	"resolution_status": null
}
```

This is a proposed schema. Reuse compatible existing models where possible.

---

## 6. Anomaly Event Contract

The incident manager must expose a standardized event contract to the troubleshooting subsystem.

Suggested contract:

```json
{
	"schema_version": "1.0",
	"event_id": "EVT_001",
	"incident_id": "INC_001",
	"machine_id": "MACHINE_001",
	"event_type": "ANOMALY_UPDATED",
	"timestamp": "2026-11-02T12:30:06Z",
	"incident_status": "ACTIVE",
	"findings": [
		{
			"detector": "DETECTOR_A",
			"parameter": "pressure",
			"observed_value": 13.5,
			"unit": "bar",
			"approved_min": 0,
			"approved_max": 12,
			"result": "LIMIT_VIOLATION"
		},
		{
			"detector": "DETECTOR_B",
			"parameter": "pressure",
			"result": "ANOMALY",
			"anomaly_score": -0.72,
			"model_version": "iforest_v1"
		}
	],
	"temporal_context": {
		"window_seconds": 15,
		"trend": "INCREASING"
	}
}
```

Additional fields may include source configuration version, first detection timestamp, evidence references and severity.

Do not send complete sensor histories through the event payload. Use database references and API retrieval instead.

The contract must be versioned.

---

# PART B — AI TROUBLESHOOTING SYSTEM

## 7. Chatbot Functionality

The chatbot must support two entry paths.

### 7.1 Anomaly-triggered troubleshooting

When a meaningful incident is created or escalated:

1. The incident manager publishes an incident update.
2. The troubleshooting manager receives it.
3. It checks whether an appropriate session already exists.
4. It creates or updates the troubleshooting session.
5. It retrieves relevant machine context.
6. It retrieves relevant manufacturer documentation.
7. It prepares an initial assessment.
8. The frontend receives the session update.

Do not generate a new LLM request for every repeated detector observation.

### 7.2 Operator-initiated troubleshooting

An operator must be able to initiate a conversation without an active anomaly.

Examples:

- Why is vibration increasing?
- What is the current pressure?
- What does the manufacturer recommend for this component?
- Has this issue occurred previously?
- Explain the recent temperature trend.

The conversation manager should identify the question type and retrieve the relevant information.

---

## 8. Conversation Manager

Create or extend a conversation-management module.

Responsibilities:

- Create troubleshooting sessions.
- Associate sessions with machine IDs.
- Associate sessions with incident IDs when applicable.
- Store messages.
- Maintain conversation history.
- Identify relevant machine context.
- Route questions to the appropriate retrieval operations.
- Persist generated responses.
- Track operator feedback.

A session must be retrievable after page refresh or reconnection.

### 8.1 Conversation context

Maintain two forms of context:

**Short-term context**

- Current conversation.
- Recent operator questions.
- Previous AI responses.
- Current troubleshooting steps.

**Persistent machine context**

- Machine configuration.
- Approved manufacturer limits.
- Historical anomaly incidents.
- Sensor history.
- Previous troubleshooting records.
- Operator-reported maintenance history.

Do not treat operator statements as independently verified facts.

For example, "I replaced the bearing" must be stored as operator-reported maintenance, not as proof that the bearing was replaced successfully.

---

## 9. Machine Context Retrieval

The chatbot must retrieve machine information selectively.

| Question                      | Required context                             |
| ----------------------------- | -------------------------------------------- |
| Current pressure              | Fresh sensor reading                         |
| Why pressure is increasing    | Recent sensor history and active incident    |
| Manufacturer's pressure limit | Approved limit configuration                 |
| What the manual says          | Relevant RAG passages                        |
| Has this happened before?     | Historical incidents                         |
| Did the intervention work?    | Recent telemetry and incident recovery state |

The chatbot must not blindly load all telemetry and documentation for every question.

### Data ownership

- Telemetry service owns sensor readings.
- Configuration workflow owns approved limits.
- Incident manager owns incident state.
- RAG subsystem owns retrieval operations and evidence references.
- Troubleshooting subsystem owns sessions, messages and operator-reported actions.

The chatbot must not directly modify detector configurations or approved manufacturer limits.

---

## 10. RAG — Manufacturer Documentation

Reuse the existing document upload and processing workflow if available.

### 10.1 Document ingestion

```text
PDF Upload
    ↓
Text Extraction
    ↓
OCR Fallback Where Necessary
    ↓
Section-Aware Chunking
    ↓
Metadata Attachment
    ↓
Embedding Generation
    ↓
Vector Database
```

Requirements:

- Preserve document ID.
- Preserve document version.
- Preserve page numbers.
- Preserve section headings.
- Preserve machine/model applicability.
- Preserve source text.
- Handle tables and technical specifications carefully.
- Avoid indexing duplicate document versions as interchangeable evidence.

### 10.2 Retrieval pipeline

```text
Operator Question
      ↓
Query Preparation
      ↓
Metadata Filtering
      ↓
Hybrid Retrieval
      ↓
Evidence Ranking
      ↓
Relevant Passages
      ↓
LLM Reasoning
```

Recommended retrieval design:

- Vector similarity retrieval.
- Keyword/BM25 retrieval where supported.
- Metadata filtering by manufacturer, machine model and document version.
- Reranking when the existing stack supports it and the benefit justifies the added complexity.

Hybrid retrieval is important because exact component identifiers and numerical specifications may not be retrieved reliably by semantic similarity alone.

Do not introduce a complex retrieval infrastructure if the existing vector database and retrieval implementation are sufficient for the prototype.

### 10.3 Evidence requirements

Every retrieved passage must retain its document and page reference.

The LLM must not invent:

- Manufacturer limits.
- Inspection procedures.
- Technical specifications.
- Corrective actions.
- Safety instructions.

If the available evidence is insufficient, the chatbot must state that limitation and request the missing information.

The structured approved-limits database remains authoritative for Detector A. RAG is for documentation retrieval, not authoritative numerical configuration.

---

## 11. LLM Reasoning Engine

The reasoning engine receives:

1. User message.
2. Relevant conversation history.
3. Machine context.
4. Active incident evidence, if any.
5. Retrieved manufacturer documentation.
6. Previous troubleshooting actions.

It must generate:

- Current condition summary.
- Evidence-backed possible causes.
- Supporting evidence.
- Contradicting evidence where available.
- Missing information.
- Prioritized diagnostic checks.
- Corrective actions supported by manufacturer documentation.
- Safety warnings.
- Source references.

### 11.1 Reasoning principles

The system must distinguish:

- Verified sensor readings.
- Manufacturer documentation.
- Detector findings.
- AI-generated hypotheses.
- Operator-reported observations.
- Verified maintenance outcomes.

Never present an AI hypothesis as a confirmed mechanical failure.

Do not give unsupported instructions when manufacturer evidence is unavailable.

Do not recommend bypassing safety interlocks, defeating guards or conducting hazardous inspections on energized equipment.

### 11.2 Structured response format

The LLM must return structured output that the frontend can render consistently.

Suggested response schema:

```json
{
	"session_id": "TS_001",
	"incident_id": "INC_001",
	"response_type": "TROUBLESHOOTING",
	"condition": {
		"parameter": "pressure",
		"observed_value": 13.5,
		"unit": "bar",
		"status": "ABOVE_APPROVED_LIMIT"
	},
	"possible_causes": [
		{
			"cause": "Pressure regulation issue",
			"supporting_evidence": ["Pressure exceeds approved maximum"],
			"confidence": "MEDIUM"
		}
	],
	"instructions": [
		{
			"step": 1,
			"title": "Review pressure regulation system",
			"description": "Follow the applicable manufacturer inspection procedure.",
			"source": {
				"document_id": "DOC_001",
				"page": 18
			},
			"requires_technician": true
		}
	],
	"missing_information": [],
	"safety_warnings": [],
	"sources": [
		{
			"document_id": "DOC_001",
			"page": 18
		}
	]
}
```

The schema is illustrative. Adapt it to the existing frontend and backend conventions.

### 11.3 Response validation

Before returning a response:

- Validate JSON/schema.
- Validate that source references exist.
- Check that cited passages were actually retrieved.
- Ensure unsupported numerical limits are not introduced.
- Check required safety warnings.
- Ensure incomplete evidence is communicated.
- Handle malformed LLM output gracefully.

Do not trust LLM-generated confidence values as calibrated probabilities.

---

## 12. Troubleshooting Feedback and Resolution

The operator must be able to report:

- Step completed.
- Step could not be completed.
- Issue persists.
- Condition appears improved.
- Additional observations.

Store this feedback against the session and incident.

Crucial rule:

**Completing a troubleshooting step must not automatically resolve an incident.**

The system must distinguish:

1. Step completed.
2. Operator reports improvement.
3. Telemetry indicates recovery.
4. Fault resolution verified.

The incident manager should update the incident based on its configured recovery criteria and any required authorized confirmation.

---

# PART C — BACKEND INTEGRATION

## 13. Database Integration

Audit and extend the existing database.

Do not create duplicate entities if equivalent models already exist.

Required logical entities:

| Entity                     | Purpose                             |
| -------------------------- | ----------------------------------- |
| `machines`                 | Machine identity and configuration  |
| `sensor_readings`          | Existing telemetry                  |
| `approved_limits`          | Verified manufacturer limits        |
| `detector_results`         | Individual detector evaluations     |
| `anomaly_events`           | Normalized anomaly records          |
| `anomaly_incidents`        | Incident lifecycle                  |
| `incident_observations`    | Incident evidence/history           |
| `troubleshooting_sessions` | Chatbot sessions                    |
| `chat_messages`            | Conversation history                |
| `retrieved_evidence`       | Manual references used in reasoning |
| `troubleshooting_steps`    | Recommended and reported actions    |

Use the existing database technology and naming conventions.

Database migrations must be safe and must preserve existing data.

---

## 14. API Requirements

Add or extend endpoints according to existing backend conventions.

Suggested endpoints:

### Anomaly and incidents

- `GET /machines/{machine_id}/anomalies`
- `GET /incidents/{incident_id}`
- `GET /machines/{machine_id}/incidents`

### Troubleshooting

- `POST /troubleshooting/sessions`
- `GET /troubleshooting/sessions/{session_id}`
- `POST /troubleshooting/sessions/{session_id}/messages`
- `POST /troubleshooting/sessions/{session_id}/feedback`
- `GET /troubleshooting/sessions/{session_id}/evidence`

### Document retrieval

Reuse existing document endpoints wherever possible.

The endpoint list is logical guidance, not a requirement to create duplicate routes.

---

## 15. WebSocket Integration

Reuse the existing WebSocket infrastructure.

Add the necessary event types:

- `anomaly.detected`
- `incident.updated`
- `incident.resolved`
- `troubleshooting.started`
- `troubleshooting.processing`
- `troubleshooting.response`
- `troubleshooting.step_updated`
- `troubleshooting.resolution_updated`

WebSocket is used for real-time notification only.

The database and APIs remain the source of truth.

On reconnect, the frontend must retrieve current session and incident state through APIs.

If event publication and database persistence are separate operations, implement a reliable retry/outbox mechanism appropriate to the existing architecture.

---

## 16. Integration and Failure Handling

The system must handle:

| Failure                    | Expected behaviour                                  |
| -------------------------- | --------------------------------------------------- |
| MQTT disconnected          | Mark telemetry stale                                |
| Missing readings           | Apply explicit missing-data policy                  |
| Detector A unavailable     | Report unavailable evaluation                       |
| Detector B unavailable     | Detector A continues independently                  |
| Missing approved limits    | Do not claim a successful limit check               |
| Vector DB unavailable      | Explain that documentation retrieval is unavailable |
| LLM timeout                | Preserve the conversation and offer retry           |
| Invalid LLM output         | Validate and retry or return a controlled error     |
| Database unavailable       | Avoid silently losing critical incident records     |
| WebSocket disconnected     | Recover using APIs                                  |
| No relevant manual passage | Communicate insufficient documentation evidence     |

Do not allow failure in the chatbot to interrupt anomaly detection.

Do not allow failure in Detector B to stop Detector A.

---

# PART D — FRONTEND INTEGRATION

## 17. Chatbot Interface

Integrate the chatbot with the existing frontend architecture.

The interface should support:

- Machine selection/context.
- Active incident information.
- Detector findings.
- Current readings and approved limits.
- Conversation history.
- User message input.
- AI response rendering.
- Possible causes.
- Ordered diagnostic instructions.
- Manual citations and page references.
- Safety warnings.
- Operator feedback.
- Loading and error states.

Keep the conversation area as the primary interaction.

The anomaly summary and evidence should be accessible without dominating the chat interface.

### 17.1 Interaction states

Implement:

- Empty conversation.
- Loading response.
- Active conversation.
- Anomaly-triggered session.
- User-initiated session.
- Response with citations.
- Insufficient evidence.
- LLM/API error.
- Session reconnection.
- Completed troubleshooting step.
- Incident recovery update.

Do not invent new visual design patterns if the project already has established frontend design conventions. Reuse existing components and styling.

---

# PART E — IMPLEMENTATION PLAN

## 18. Implementation Phases

The implementation agent should follow this order.

### Phase 0 — Repository Audit

- Inspect existing backend.
- Create `AI_SYSTEM_AUDIT.md`.
- Identify reusable services.
- Identify missing components.
- Document integration strategy.

Do not begin large-scale code changes before completing the audit.

### Phase 1 — Anomaly Pipeline Integration

- Verify Detector A and Detector B.
- Verify 3-second processing.
- Verify 3-second and 15-second feature windows.
- Implement missing standardized event models.
- Implement event aggregation.
- Implement incident lifecycle.
- Add persistence and incident APIs.

### Phase 2 — Troubleshooting Backend

- Implement session management.
- Implement message persistence.
- Implement machine-context retrieval.
- Implement incident-to-session integration.
- Implement operator feedback.

### Phase 3 — RAG Integration

- Reuse document processing.
- Verify page-aware extraction and chunking.
- Integrate vector retrieval.
- Implement metadata filtering.
- Implement relevant evidence retrieval.
- Preserve source references.

### Phase 4 — LLM Reasoning

- Integrate the existing LLM provider or add one only if necessary.
- Implement context assembly.
- Implement structured prompts.
- Implement structured response generation.
- Implement response validation.
- Implement error handling.

### Phase 5 — Frontend Integration

- Connect chatbot UI.
- Display incident evidence.
- Display AI responses and citations.
- Support feedback.
- Handle real-time updates.

### Phase 6 — End-to-End Validation

- Validate the anomaly-to-troubleshooting flow.
- Validate operator-initiated questions.
- Validate RAG citations.
- Validate persistence.
- Validate incident recovery.

---

## 19. Testing Requirements

### Anomaly tests

- Normal readings.
- Values exactly at approved boundaries.
- Values outside approved boundaries.
- Missing approved limits.
- Unit mismatch.
- Invalid sensor values.
- Detector A/B independent execution.
- Repeated anomaly observations.
- Multiple unrelated anomalies.
- Incident recovery and reopening.
- Duplicate message handling.

### RAG tests

- Correct manual retrieval.
- Exact technical term retrieval.
- Machine-model filtering.
- Document version filtering.
- Page reference preservation.
- No relevant documentation.
- Conflicting manual passages.
- Table-based specification retrieval.

### Chatbot tests

- Current sensor value questions.
- Historical anomaly questions.
- Manual-based questions.
- Questions with insufficient evidence.
- Follow-up conversation context.
- Invalid LLM output.
- LLM timeout.
- Operator feedback persistence.

### Integration tests

Test the complete workflow:

1. Send simulated sensor readings.
2. Trigger a manufacturer-limit violation.
3. Execute the statistical detector independently.
4. Generate a normalized anomaly event.
5. Create or update an incident.
6. Trigger a troubleshooting session.
7. Retrieve machine context.
8. Retrieve relevant manual passages.
9. Generate an AI response.
10. Verify source references.
11. Submit operator feedback.
12. Send new telemetry.
13. Verify incident recovery behaviour.

Do not claim that any test passed until it has actually been executed.

---

## 20. Acceptance Criteria

The implementation is acceptable when:

- [ ] Existing backend functionality remains intact.
- [ ] No duplicate MQTT or telemetry pipeline has been introduced.
- [ ] Existing detector implementations are reused where valid.
- [ ] Detector A uses only approved manufacturer limits.
- [ ] Detector B processes the established feature structure.
- [ ] Both detectors operate independently.
- [ ] Events are normalized into a common contract.
- [ ] Repeated observations update incidents rather than generating duplicate incidents.
- [ ] Incident state is persisted.
- [ ] Incident APIs are functional.
- [ ] Troubleshooting sessions can be created from incidents.
- [ ] Operators can initiate conversations independently.
- [ ] Machine context is selectively retrieved.
- [ ] RAG returns relevant manufacturer evidence with source references.
- [ ] LLM responses follow the structured schema.
- [ ] Unsupported claims are handled safely.
- [ ] Operator feedback is persisted.
- [ ] Completing a step does not automatically resolve an incident.
- [ ] WebSocket updates integrate with the existing infrastructure.
- [ ] Frontend can recover state after reconnection.
- [ ] The complete integration workflow is tested.

---

## 21. Deliverables

The implementation agent must produce:

1. `AI_SYSTEM_AUDIT.md` — existing backend audit and integration plan.
2. Updated backend implementation — only necessary additions and modifications.
3. Database migrations — where required.
4. AI system API documentation.
5. Updated WebSocket event documentation.
6. Configuration and environment-variable documentation.
7. `AI_SYSTEM_IMPLEMENTATION.md` — explanatory implementation document.
8. Test files and test execution results.
9. A concise list of unresolved limitations and future improvements.

### Implementation documentation requirements

`AI_SYSTEM_IMPLEMENTATION.md` must explain:

- What was already present.
- What was reused.
- What was added.
- What existing files were modified.
- How the anomaly pipeline works.
- How incident aggregation works.
- How the chatbot works.
- How RAG retrieval works.
- How the LLM receives machine context.
- How the frontend communicates with the backend.
- How to configure and run the AI system.
- How to troubleshoot common failures.
- Which features remain incomplete.

Do not document features as implemented if they are only planned.

---

## 22. Final Development Constraints

The implementation must remain a clean, understandable prototype.

- Keep the directory structure minimal.
- Avoid unnecessary abstraction.
- Avoid unnecessary microservices.
- Avoid excessive dependency additions.
- Reuse existing utilities and conventions.
- Keep configuration in environment variables.
- Add basic, useful logging.
- Use clear error messages.
- Keep functions and modules understandable.
- Avoid large rewrites.
- Preserve the existing project architecture unless a change is justified.
- Do not use mock data in place of real backend integrations in the final implementation.
- If an external API or credential is unavailable, implement a clearly isolated integration boundary and document the limitation.

**Most importantly: audit, reuse, extend, integrate and validate. Do not rebuild the working backend.**

---

## 23. Definition of Done

The AI system is complete when an abnormal machine condition can travel through the existing telemetry backend, be evaluated by both detectors, become a persisted incident, initiate an evidence-grounded troubleshooting conversation, and receive operator feedback.

The operator must be able to understand:

- What the system detected.
- Which detector identified it.
- What measured evidence supports it.
- What the manufacturer documentation says.
- What diagnostic action is recommended.
- Whether the machine condition has actually recovered.

The final implementation should demonstrate this complete workflow without compromising the existing backend.
