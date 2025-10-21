-- Enum for document visibility
DO $$ BEGIN
    CREATE TYPE doc_visibility AS ENUM ('public', 'internal', 'restricted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Role
CREATE TABLE IF NOT EXISTS role (
  role_id SERIAL PRIMARY KEY,
  name VARCHAR(15) NOT NULL UNIQUE
);

-- Department
CREATE TABLE IF NOT EXISTS department (
  department_id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,
  location VARCHAR(50) NOT NULL
);

-- app_user
CREATE TABLE IF NOT EXISTS app_user (
  user_id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  pass_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  role_id INT NOT NULL REFERENCES role(role_id),
  department_id INT NOT NULL REFERENCES department(department_id)
);

-- Document
CREATE TABLE IF NOT EXISTS document (
  doc_id SERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL UNIQUE,
  description TEXT NOT NULL,
  visibility doc_visibility NOT NULL DEFAULT 'internal',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Access (department-level)
CREATE TABLE IF NOT EXISTS doc_access (
  access_level SMALLINT NOT NULL CHECK (access_level BETWEEN 0 AND 10),
  department_id INT NOT NULL REFERENCES department(department_id) ON DELETE CASCADE,
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  PRIMARY KEY (department_id, doc_id)
);

-- Tag
CREATE TABLE IF NOT EXISTS tag (
  tag_id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE
);

-- Document_Tag
CREATE TABLE IF NOT EXISTS document_tag (
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  tag_id INT NOT NULL REFERENCES tag(tag_id) ON DELETE CASCADE,
  PRIMARY KEY (doc_id, tag_id)
);

-- Document_Version
CREATE TABLE IF NOT EXISTS document_version (
  doc_id INT NOT NULL REFERENCES document(doc_id) ON DELETE CASCADE,
  version_no INT NOT NULL,
  storage_key TEXT NOT NULL UNIQUE,
  file_size INT NOT NULL,
  is_latest BOOLEAN NOT NULL DEFAULT FALSE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  uploaded_by INT NOT NULL REFERENCES app_user(user_id),
  PRIMARY KEY (doc_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_document_version_latest ON document_version (doc_id) WHERE is_latest;

-- Action_Log
CREATE TABLE IF NOT EXISTS action_log (
  log_id BIGSERIAL PRIMARY KEY,
  action_type VARCHAR(30) NOT NULL,
  ip INET NOT NULL,
  time_stamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id INT NOT NULL REFERENCES app_user(user_id),
  doc_id INT NOT NULL,
  version_no INT NOT NULL,
  FOREIGN KEY (doc_id, version_no) REFERENCES document_version (doc_id, version_no)
);

-- Seed data
INSERT INTO role(name) VALUES ('admin') ON CONFLICT DO NOTHING;
INSERT INTO role(name) VALUES ('user') ON CONFLICT DO NOTHING;
INSERT INTO department(name, location) VALUES ('Engineering', 'HQ') ON CONFLICT DO NOTHING;
INSERT INTO department(name, location) VALUES ('Finance', 'HQ') ON CONFLICT DO NOTHING;
