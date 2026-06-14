PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS aho_schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS aho_students (
    student_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS aho_student_progress (
    student_id TEXT PRIMARY KEY REFERENCES aho_students(student_id) ON DELETE CASCADE,
    current_module INTEGER NOT NULL DEFAULT 0 CHECK (current_module BETWEEN 0 AND 16),
    current_competency TEXT,
    independence_level TEXT NOT NULL DEFAULT 'observer'
        CHECK (independence_level IN ('observer', 'guided', 'independent', 'transfer')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed')),
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS aho_module_progress (
    student_id TEXT NOT NULL REFERENCES aho_students(student_id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL CHECK (module_id BETWEEN 0 AND 16),
    status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started', 'in_progress', 'mastered')),
    mastery_score REAL NOT NULL DEFAULT 0 CHECK (mastery_score BETWEEN 0 AND 1),
    checkpoint_attempts INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    last_feedback_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (student_id, module_id)
);

CREATE TABLE IF NOT EXISTS aho_competency_progress (
    student_id TEXT NOT NULL REFERENCES aho_students(student_id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL CHECK (module_id BETWEEN 0 AND 16),
    competency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'learning'
        CHECK (status IN ('learning', 'practicing', 'mastered', 'needs_review')),
    evidence_count INTEGER NOT NULL DEFAULT 0,
    independent_successes INTEGER NOT NULL DEFAULT 0,
    hinted_successes INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    mastery_score REAL NOT NULL DEFAULT 0 CHECK (mastery_score BETWEEN 0 AND 1),
    last_attempt_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (student_id, module_id, competency_key)
);

CREATE TABLE IF NOT EXISTS aho_exercise_attempts (
    attempt_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES aho_students(student_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    module_id INTEGER NOT NULL CHECK (module_id BETWEEN 0 AND 16),
    competency_key TEXT NOT NULL,
    evidence_kind TEXT,
    result TEXT NOT NULL CHECK (result IN (
        'correct', 'correct_with_hint', 'incorrect', 'incomplete', 'not_evaluated'
    )),
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
    used_hint INTEGER NOT NULL DEFAULT 0 CHECK (used_hint IN (0, 1)),
    prompt_hash TEXT,
    evaluation_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS aho_module_evidence (
    student_id TEXT NOT NULL REFERENCES aho_students(student_id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL CHECK (module_id BETWEEN 0 AND 16),
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN (
        'direct_application', 'independent_application', 'integration',
        'diagnosis', 'explanation_transfer'
    )),
    best_score REAL NOT NULL DEFAULT 0 CHECK (best_score BETWEEN 0 AND 1),
    satisfied INTEGER NOT NULL DEFAULT 0 CHECK (satisfied IN (0, 1)),
    source_attempt_id TEXT REFERENCES aho_exercise_attempts(attempt_id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (student_id, module_id, evidence_kind)
);

CREATE TABLE IF NOT EXISTS aho_learning_events (
    event_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES aho_students(student_id) ON DELETE CASCADE,
    session_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_aho_attempts_student_module
    ON aho_exercise_attempts(student_id, module_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aho_events_student_created
    ON aho_learning_events(student_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aho_competency_student_module
    ON aho_competency_progress(student_id, module_id);
