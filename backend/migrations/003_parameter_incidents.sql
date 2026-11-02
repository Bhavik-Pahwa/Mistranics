-- Preserve legacy machine-level grouping while allowing explicitly scoped incidents.
ALTER TABLE alerts ADD COLUMN incident_key varchar NOT NULL DEFAULT '__machine__';
DROP INDEX uq_active_machine_incident;
CREATE UNIQUE INDEX uq_active_machine_incident ON alerts(asset_id,incident_key)
WHERE status IN ('active','acknowledged');
