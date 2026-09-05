"""Ordered, append-only DuckDB schema migrations."""

MIGRATIONS = [
    (
        1,
        "initial versioned benchmark-bank schema",
        r"""
        CREATE TABLE IF NOT EXISTS bank_sources (
            source_id VARCHAR NOT NULL,
            revision INTEGER NOT NULL,
            is_current BOOLEAN NOT NULL,
            content_hash VARCHAR NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            organization VARCHAR,
            source_type VARCHAR,
            publication_date DATE,
            review_status VARCHAR,
            payload_json VARCHAR NOT NULL,
            PRIMARY KEY (source_id, revision)
        );

        CREATE TABLE IF NOT EXISTS bank_projects (
            project_id VARCHAR NOT NULL,
            revision INTEGER NOT NULL,
            is_current BOOLEAN NOT NULL,
            content_hash VARCHAR NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            project_name VARCHAR,
            country_iso3 VARCHAR,
            region VARCHAR,
            technology VARCHAR,
            project_type VARCHAR,
            revenue_model VARCHAR,
            identity_status VARCHAR,
            payload_json VARCHAR NOT NULL,
            PRIMARY KEY (project_id, revision)
        );

        CREATE TABLE IF NOT EXISTS bank_ingestion_runs (
            ingestion_run_id VARCHAR NOT NULL,
            revision INTEGER NOT NULL,
            is_current BOOLEAN NOT NULL,
            content_hash VARCHAR NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            source_id VARCHAR,
            adapter_name VARCHAR,
            adapter_version VARCHAR,
            status VARCHAR,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            payload_json VARCHAR NOT NULL,
            PRIMARY KEY (ingestion_run_id, revision)
        );

        CREATE TABLE IF NOT EXISTS bank_observations (
            observation_id VARCHAR NOT NULL,
            revision INTEGER NOT NULL,
            is_current BOOLEAN NOT NULL,
            content_hash VARCHAR NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            source_id VARCHAR,
            project_id VARCHAR,
            ingestion_run_id VARCHAR,
            metric VARCHAR,
            observation_type VARCHAR,
            value_status VARCHAR,
            raw_value_numeric DOUBLE,
            raw_value_text VARCHAR,
            raw_low DOUBLE,
            raw_high DOUBLE,
            raw_unit VARCHAR,
            normalized_value DOUBLE,
            normalized_low DOUBLE,
            normalized_high DOUBLE,
            normalized_unit VARCHAR,
            currency VARCHAR,
            price_year INTEGER,
            statistic VARCHAR,
            economic_perimeter VARCHAR,
            quality_level VARCHAR,
            review_status VARCHAR,
            payload_json VARCHAR NOT NULL,
            PRIMARY KEY (observation_id, revision)
        );

        CREATE TABLE IF NOT EXISTS bank_normalization_events (
            normalization_event_id VARCHAR NOT NULL,
            revision INTEGER NOT NULL,
            is_current BOOLEAN NOT NULL,
            content_hash VARCHAR NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            ingestion_run_id VARCHAR,
            observation_id VARCHAR,
            field_name VARCHAR,
            rule_id VARCHAR,
            rule_version VARCHAR,
            created_at TIMESTAMPTZ,
            payload_json VARCHAR NOT NULL,
            PRIMARY KEY (normalization_event_id, revision)
        );

        CREATE INDEX IF NOT EXISTS idx_projects_current_technology
            ON bank_projects (is_current, technology, region, country_iso3);
        CREATE INDEX IF NOT EXISTS idx_observations_current_metric
            ON bank_observations (is_current, metric, project_id);
        CREATE INDEX IF NOT EXISTS idx_observations_source
            ON bank_observations (is_current, source_id);
        CREATE INDEX IF NOT EXISTS idx_events_observation
            ON bank_normalization_events (is_current, observation_id);

        CREATE OR REPLACE VIEW current_sources AS
            SELECT * FROM bank_sources WHERE is_current;
        CREATE OR REPLACE VIEW current_projects AS
            SELECT * FROM bank_projects WHERE is_current;
        CREATE OR REPLACE VIEW current_ingestion_runs AS
            SELECT * FROM bank_ingestion_runs WHERE is_current;
        CREATE OR REPLACE VIEW current_observations AS
            SELECT * FROM bank_observations WHERE is_current;
        CREATE OR REPLACE VIEW current_normalization_events AS
            SELECT * FROM bank_normalization_events WHERE is_current;
        """,
    ),
]
