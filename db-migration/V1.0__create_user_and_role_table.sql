CREATE TABLE IF NOT EXISTS roles (
  role_id VARCHAR(36) NOT NULL,
  name VARCHAR NOT NULL UNIQUE,
  description VARCHAR,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT roles_pkey PRIMARY KEY (role_id),
  CONSTRAINT roles_name_check CHECK (name IN ('admin', 'user', 'system'))
);

CREATE TABLE IF NOT EXISTS scopes (
  scope_id VARCHAR(36) NOT NULL,
  name VARCHAR NOT NULL UNIQUE,
  description VARCHAR,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT scopes_pkey PRIMARY KEY (scope_id),
  CONSTRAINT scopes_name_check CHECK (name IN (
    'challenge:read', 'challenge:write', 'room:read', 'room:write', 'progress:read', 'progress:write',
    'leaderboard:read', 'user:read', 'user:write', 'admin:read', 'admin:write', 'system:read', 'system:write'
  ))
);

CREATE TABLE IF NOT EXISTS role_scopes (
  role_id VARCHAR(36) NOT NULL,
  scope_id VARCHAR(36) NOT NULL,
  CONSTRAINT role_scopes_pkey PRIMARY KEY (role_id, scope_id),
  CONSTRAINT role_scopes_role_id_fkey FOREIGN KEY (role_id) REFERENCES roles(role_id),
  CONSTRAINT role_scopes_scope_id_fkey FOREIGN KEY (scope_id) REFERENCES scopes(scope_id)
);

CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(36) NOT NULL,
  email VARCHAR NOT NULL UNIQUE,
  username VARCHAR NOT NULL,
  xp INTEGER DEFAULT 0,
  streak INTEGER DEFAULT 0,
  challenges_completed INTEGER DEFAULT 0,
  perfect_scores INTEGER DEFAULT 0,
  last_activity_date date,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  role_id VARCHAR NOT NULL,
  CONSTRAINT users_pkey PRIMARY KEY (user_id),
  CONSTRAINT users_role_id_fkey FOREIGN KEY (role_id) REFERENCES roles(role_id)
);
