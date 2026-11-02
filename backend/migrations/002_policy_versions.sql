CREATE TABLE policy_versions (
    version varchar PRIMARY KEY,
    payload jsonb NOT NULL,
    registered_at timestamptz NOT NULL
);
