-- Immutable initial PostgreSQL schema.

CREATE TABLE assets (
	asset_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	metadata JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (asset_id)
)

;

CREATE TABLE anomaly_decisions (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	window_id VARCHAR NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	final_status VARCHAR NOT NULL, 
	policy_version VARCHAR NOT NULL, 
	evidence JSONB NOT NULL, 
	decision_reason JSONB NOT NULL, 
	alert_processed BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (asset_id, window_id, policy_version), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id)
)

;

CREATE TABLE sensor_readings (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	device_id VARCHAR NOT NULL, 
	window_id VARCHAR NOT NULL, 
	measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE, 
	ingested_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	schema_version VARCHAR NOT NULL, 
	quality_status VARCHAR NOT NULL, 
	operating_context JSONB NOT NULL, 
	readings JSONB NOT NULL, 
	original JSONB NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (asset_id, window_id), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id)
)

;

CREATE TABLE alerts (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	decision_id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR NOT NULL, 
	severity VARCHAR, 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	metadata JSONB NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id), 
	FOREIGN KEY(decision_id) REFERENCES anomaly_decisions (id)
)

;

CREATE TABLE detector_results (
	id VARCHAR NOT NULL, 
	asset_id VARCHAR NOT NULL, 
	window_id VARCHAR NOT NULL, 
	run_id VARCHAR NOT NULL, 
	detector VARCHAR NOT NULL, 
	evaluated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR NOT NULL, 
	schema_version VARCHAR NOT NULL, 
	model_version VARCHAR, 
	config_version VARCHAR, 
	feature_schema_version VARCHAR, 
	payload JSONB NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(asset_id, window_id) REFERENCES sensor_readings (asset_id, window_id), 
	UNIQUE (asset_id, window_id, detector, run_id), 
	FOREIGN KEY(asset_id) REFERENCES assets (asset_id)
)

;

CREATE TABLE alert_events (
	id VARCHAR NOT NULL, 
	alert_id VARCHAR NOT NULL, 
	event_type VARCHAR NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	details JSONB NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alert_id) REFERENCES alerts (id)
)

;
CREATE INDEX ix_decisions_asset_time ON anomaly_decisions (asset_id, decided_at);
CREATE INDEX ix_readings_event ON sensor_readings (asset_id, measured_at, window_id);
CREATE UNIQUE INDEX uq_active_machine_incident ON alerts (asset_id) WHERE status IN ('active', 'acknowledged');
CREATE INDEX ix_results_asset_time ON detector_results (asset_id, evaluated_at);
