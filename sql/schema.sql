-- ============================================================================
-- Extensions (for fast ILIKE on document.title)
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Enum for document visibility
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE doc_visibility AS ENUM ('public', 'internal', 'restricted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================================
-- Roles / Departments
-- ============================================================================
CREATE TABLE IF NOT EXISTS role (
  role_id SERIAL PRIMARY KEY,
  name VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS department (
  department_id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,
  location VARCHAR(50) NOT NULL
);

-- Department <-> Role mapping (allowed roles per department; optional policy)
CREATE TABLE IF NOT EXISTS department_role (
  department_id INT NOT NULL REFERENCES department(department_id) ON DELETE CASCADE,
  role_id       INT NOT NULL REFERENCES role(role_id) ON DELETE CASCADE,
  PRIMARY KEY (department_id, role_id)
);

-- Helpful lookups
CREATE INDEX IF NOT EXISTS idx_department_name ON department(name);
CREATE INDEX IF NOT EXISTS idx_role_name       ON role(name);
CREATE INDEX IF NOT EXISTS idx_dept_role_role  ON department_role(role_id);

-- ============================================================================
-- Users
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_user (
  user_id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  pass_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  role_id INT NOT NULL REFERENCES role(role_id),
  department_id INT NOT NULL REFERENCES department(department_id)
);

CREATE INDEX IF NOT EXISTS idx_user_created_at ON app_user(created_at);

-- ============================================================================
-- Documents & ACL
-- ============================================================================
CREATE TABLE IF NOT EXISTS document (
  doc_id SERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL UNIQUE,
  description TEXT NOT NULL,
  visibility doc_visibility NOT NULL DEFAULT 'internal',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Department-level Access Control
-- access_level: SMALLINT CHECK 0..10
-- (lower number = more privilege; e.g., <=2 owner, <5 edit)
CREATE TABLE IF NOT EXISTS doc_access (
  access_level SMALLINT NOT NULL CHECK (access_level BETWEEN 0 AND 10),
  department_id INT NOT NULL REFERENCES department(department_id) ON DELETE CASCADE,
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  PRIMARY KEY (department_id, doc_id)
);

-- Helpful indexes for typical queries
CREATE INDEX IF NOT EXISTS idx_document_visibility   ON document(visibility);
CREATE INDEX IF NOT EXISTS idx_document_updated_at   ON document(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_title_trgm   ON document USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_doc_access_dept_doc   ON doc_access(department_id, doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_access_doc        ON doc_access(doc_id);

-- ============================================================================
-- Tags
-- ============================================================================
CREATE TABLE IF NOT EXISTS tag (
  tag_id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,
  tag_deleted BOOLEAN DEFAULT false
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_name_ci ON tag (lower(name));

CREATE TABLE IF NOT EXISTS document_tag (
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  tag_id INT NOT NULL REFERENCES tag(tag_id) ON DELETE CASCADE,
  PRIMARY KEY (doc_id, tag_id)
);

-- Speed filters by tag, and joins from tag -> documents
CREATE INDEX IF NOT EXISTS idx_document_tag_tag ON document_tag(tag_id);
CREATE INDEX IF NOT EXISTS idx_document_tag_doc ON document_tag(doc_id);
-- ============================================================================
-- Versions
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_version (
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  version_no INT NOT NULL,
  storage_key TEXT NOT NULL UNIQUE,
  file_size INT NOT NULL CHECK (file_size >= 0),
  is_latest BOOLEAN NOT NULL DEFAULT FALSE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  uploaded_by INT NOT NULL REFERENCES app_user(user_id),
  PRIMARY KEY (doc_id, version_no)
);

-- Fast "latest" lookups, uploader filter on latest
CREATE INDEX IF NOT EXISTS idx_document_version_latest
  ON document_version (doc_id)
  WHERE is_latest;

CREATE INDEX IF NOT EXISTS idx_docver_latest_uploader
  ON document_version (uploaded_by)
  WHERE is_latest;

-- Good for version history ordering
CREATE INDEX IF NOT EXISTS idx_docver_doc_version
  ON document_version (doc_id, version_no DESC);

-- ============================================================================
-- Audit Log
-- ============================================================================
CREATE TABLE IF NOT EXISTS action_log (
  log_id BIGSERIAL PRIMARY KEY,
  action_type VARCHAR(30) NOT NULL,
  ip INET NOT NULL,
  time_stamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id INT NOT NULL REFERENCES app_user(user_id),
  doc_id INT NOT NULL,
  version_no INT NOT NULL,
  CONSTRAINT fk_actionlog_docver
    FOREIGN KEY (doc_id, version_no)
    REFERENCES document_version (doc_id, version_no)
    ON DELETE CASCADE
);

-- Helpful audit indexes
CREATE INDEX IF NOT EXISTS idx_action_log_time     ON action_log(time_stamp DESC);
CREATE INDEX IF NOT EXISTS idx_action_log_user     ON action_log(user_id);
CREATE INDEX IF NOT EXISTS idx_action_log_docver   ON action_log(doc_id, version_no);

-- ============================================================================
-- Seed data
-- ============================================================================
INSERT INTO role(name) VALUES ('admin') ON CONFLICT DO NOTHING;
INSERT INTO role(name) VALUES ('user')  ON CONFLICT DO NOTHING;

INSERT INTO department(name, location) VALUES ('Engineering', 'HQ') ON CONFLICT DO NOTHING;
INSERT INTO department(name, location) VALUES ('Finance',     'HQ') ON CONFLICT DO NOTHING;
