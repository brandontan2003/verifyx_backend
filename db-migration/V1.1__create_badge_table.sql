CREATE TABLE IF NOT EXISTS badges (
  badge_id VARCHAR(36) NOT NULL,
  name VARCHAR NOT NULL,
  description VARCHAR NOT NULL,
  badge_type VARCHAR NOT NULL,
  threshold INTEGER NOT NULL,
  CONSTRAINT badges_pkey PRIMARY KEY (badge_id),
  CONSTRAINT badges_badge_type_check CHECK (badge_type IN ('streak', 'completion', 'xp'))
);

CREATE TABLE IF NOT EXISTS user_badges (
  user_id VARCHAR(36) NOT NULL,
  badge_id VARCHAR(36) NOT NULL,
  earned_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT user_badges_pkey PRIMARY KEY (user_id, badge_id),
  CONSTRAINT user_badges_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES badges(badge_id),
  CONSTRAINT user_badges_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);
