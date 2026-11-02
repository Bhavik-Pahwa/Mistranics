-- Additive AI/ML extension tables; existing telemetry and incidents are reused.

CREATE TABLE ai_documents (
	id VARCHAR NOT NULL, 
	document_id VARCHAR NOT NULL, 
	version VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	manufacturer VARCHAR NOT NULL, 
	machine_model VARCHAR NOT NULL, 
	sha256 VARCHAR NOT NULL, 
	embedding_model VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id, version), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id)
)

;

CREATE TABLE ai_event_outbox (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	event_type VARCHAR NOT NULL, 
	payload JSONB NOT NULL, 
	delivered BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id)
)

;
CREATE INDEX ix_outbox_delivery ON ai_event_outbox (delivered, created_at);

CREATE TABLE ai_document_chunks (
	id VARCHAR NOT NULL, 
	manual_id VARCHAR NOT NULL, 
	page INTEGER NOT NULL, 
	section VARCHAR NOT NULL, 
	text VARCHAR NOT NULL, 
	embedding JSONB NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(manual_id) REFERENCES ai_documents (id)
)

;
CREATE INDEX ix_chunks_manual ON ai_document_chunks (manual_id);

CREATE TABLE ml_processed_windows (
	reading_id VARCHAR NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (reading_id), 
	FOREIGN KEY(reading_id) REFERENCES sensor_readings (id)
)

;

CREATE TABLE anomaly_events (
	id VARCHAR NOT NULL, 
	result_id VARCHAR NOT NULL, 
	incident_id VARCHAR NOT NULL, 
	finding_key VARCHAR NOT NULL, 
	parameter VARCHAR NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	evidence JSONB NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (result_id, finding_key), 
	FOREIGN KEY(result_id) REFERENCES detector_results (id), 
	FOREIGN KEY(incident_id) REFERENCES alerts (id)
)

;
CREATE INDEX ix_anomaly_incident ON anomaly_events (incident_id, observed_at);

CREATE TABLE troubleshooting_sessions (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	incident_id VARCHAR, 
	document_id VARCHAR, 
	document_version VARCHAR, 
	state VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id), 
	UNIQUE (incident_id), 
	FOREIGN KEY(incident_id) REFERENCES alerts (id)
)

;
CREATE INDEX ix_sessions_asset ON troubleshooting_sessions (asset_id, created_at);

CREATE TABLE chat_messages (
	id VARCHAR NOT NULL, 
	session_id VARCHAR NOT NULL, 
	request_id VARCHAR NOT NULL, 
	user_text VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	attempts INTEGER NOT NULL, 
	response JSONB, 
	error VARCHAR, 
	processing_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (session_id, request_id), 
	FOREIGN KEY(session_id) REFERENCES troubleshooting_sessions (id)
)

;
CREATE INDEX ix_messages_session ON chat_messages (session_id, created_at);

CREATE TABLE retrieved_evidence (
	id VARCHAR NOT NULL, 
	message_id VARCHAR NOT NULL, 
	chunk_id VARCHAR NOT NULL, 
	snapshot JSONB NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (message_id, chunk_id), 
	FOREIGN KEY(message_id) REFERENCES chat_messages (id), 
	FOREIGN KEY(chunk_id) REFERENCES ai_document_chunks (id)
)

;

CREATE TABLE troubleshooting_steps (
	id VARCHAR NOT NULL, 
	session_id VARCHAR NOT NULL, 
	message_id VARCHAR NOT NULL, 
	instruction JSONB NOT NULL, 
	state VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES troubleshooting_sessions (id), 
	FOREIGN KEY(message_id) REFERENCES chat_messages (id)
)

;

CREATE TABLE troubleshooting_feedback (
	id VARCHAR NOT NULL, 
	session_id VARCHAR NOT NULL, 
	incident_id VARCHAR, 
	step_id VARCHAR, 
	kind VARCHAR NOT NULL, 
	text VARCHAR NOT NULL, 
	provenance VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES troubleshooting_sessions (id), 
	FOREIGN KEY(incident_id) REFERENCES alerts (id), 
	FOREIGN KEY(step_id) REFERENCES troubleshooting_steps (id)
)

;
