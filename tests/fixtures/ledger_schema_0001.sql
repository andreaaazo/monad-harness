-- Schema del registro reale prima di Alembic, estratto da sqlite_master il 2026-11-02. Nessun dato.

CREATE TABLE concepts (
    seq INTEGER NOT NULL,
    project VARCHAR NOT NULL,
    round INTEGER NOT NULL,
    letter VARCHAR NOT NULL,
    lever VARCHAR NOT NULL,
    anon VARCHAR NOT NULL,
    card_json VARCHAR NOT NULL,
    idea_ticket VARCHAR NOT NULL,
    sketch_ticket VARCHAR NOT NULL,
    sketch_file VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE derivations (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    master VARCHAR NOT NULL,
    master_sha VARCHAR NOT NULL,
    export VARCHAR NOT NULL,
    export_sha VARCHAR NOT NULL,
    how VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE events (
    seq INTEGER NOT NULL,
    ticket_id VARCHAR NOT NULL,
    at VARCHAR NOT NULL,
    actor VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    note VARCHAR NOT NULL,
    prev_hash VARCHAR NOT NULL,
    hash VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE evidence (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    file VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    result VARCHAR NOT NULL,
    signer VARCHAR NOT NULL,
    ticket_id VARCHAR NOT NULL,
    proof VARCHAR NOT NULL,
    note VARCHAR NOT NULL,
    inputs_json VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE gates (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    gate VARCHAR NOT NULL,
    approved BOOLEAN NOT NULL,
    choice VARCHAR NOT NULL,
    text VARCHAR NOT NULL,
    files_json VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE operations (
    id VARCHAR NOT NULL,
    instance VARCHAR NOT NULL,
    tool VARCHAR NOT NULL,
    result_json VARCHAR NOT NULL,
    at VARCHAR NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE projects (
    name VARCHAR NOT NULL,
    budget_usd FLOAT NOT NULL,
    model VARCHAR NOT NULL,
    effort VARCHAR NOT NULL,
    PRIMARY KEY (name)
);

CREATE TABLE renders (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    source_sha VARCHAR NOT NULL,
    proof VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE TABLE tickets (
    id VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    spec_json VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    verdict VARCHAR,
    delivered_json VARCHAR NOT NULL,
    inputs_json VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE usage (
    seq INTEGER NOT NULL,
    at VARCHAR NOT NULL,
    project VARCHAR NOT NULL,
    ticket_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    instance VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_write_5m_tokens INTEGER NOT NULL,
    cache_write_1h_tokens INTEGER NOT NULL,
    cost_usd FLOAT NOT NULL,
    stop_reason VARCHAR NOT NULL,
    request_id VARCHAR NOT NULL,
    PRIMARY KEY (seq)
);

CREATE INDEX ix_concepts_project ON concepts (project);

CREATE INDEX ix_derivations_export ON derivations (export);

CREATE INDEX ix_derivations_project ON derivations (project);

CREATE INDEX ix_events_ticket_id ON events (ticket_id);

CREATE INDEX ix_evidence_check_name ON evidence (check_name);

CREATE INDEX ix_evidence_file ON evidence (file);

CREATE INDEX ix_evidence_project ON evidence (project);

CREATE INDEX ix_gates_project ON gates (project);

CREATE INDEX ix_operations_instance ON operations (instance);

CREATE INDEX ix_renders_project ON renders (project);

CREATE INDEX ix_renders_source ON renders (source);

CREATE INDEX ix_tickets_project ON tickets (project);

CREATE INDEX ix_tickets_status ON tickets (status);

CREATE INDEX ix_usage_project ON usage (project);

CREATE INDEX ix_usage_ticket_id ON usage (ticket_id);

CREATE TRIGGER derivations_no_delete BEFORE DELETE ON derivations BEGIN SELECT RAISE(ABORT, 'derivations è solo in aggiunta'); END;

CREATE TRIGGER derivations_no_update BEFORE UPDATE ON derivations BEGIN SELECT RAISE(ABORT, 'derivations è solo in aggiunta'); END;

CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events è solo in aggiunta'); END;

CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events è solo in aggiunta'); END;

CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence è solo in aggiunta'); END;

CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence è solo in aggiunta'); END;

CREATE TRIGGER gates_no_delete BEFORE DELETE ON gates BEGIN SELECT RAISE(ABORT, 'gates è solo in aggiunta'); END;

CREATE TRIGGER gates_no_update BEFORE UPDATE ON gates BEGIN SELECT RAISE(ABORT, 'gates è solo in aggiunta'); END;

CREATE TRIGGER renders_no_delete BEFORE DELETE ON renders BEGIN SELECT RAISE(ABORT, 'renders è solo in aggiunta'); END;

CREATE TRIGGER renders_no_update BEFORE UPDATE ON renders BEGIN SELECT RAISE(ABORT, 'renders è solo in aggiunta'); END;

CREATE TRIGGER usage_no_delete BEFORE DELETE ON usage BEGIN SELECT RAISE(ABORT, 'usage è solo in aggiunta'); END;

CREATE TRIGGER usage_no_update BEFORE UPDATE ON usage BEGIN SELECT RAISE(ABORT, 'usage è solo in aggiunta'); END;
