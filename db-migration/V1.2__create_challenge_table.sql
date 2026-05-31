CREATE TYPE room_status_enum AS ENUM ('waiting', 'active', 'finished');

CREATE TABLE IF NOT EXISTS rooms (
  room_id VARCHAR(36) NOT NULL,
  code VARCHAR(6) NOT NULL UNIQUE,
  host_user_id VARCHAR(36) NOT NULL,
  theme VARCHAR NOT NULL,
  max_players INTEGER NOT NULL,
  time_limit_seconds INTEGER NOT NULL,
  status room_status_enum NOT NULL DEFAULT 'waiting',
  scenario json,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  started_at TIMESTAMP WITH TIME ZONE,
  finished_at TIMESTAMP WITH TIME ZONE,
  CONSTRAINT rooms_pkey PRIMARY KEY (room_id),
  CONSTRAINT rooms_host_user_id_fkey FOREIGN KEY (host_user_id) REFERENCES users(user_id)
);

CREATE TYPE question_type_enum AS ENUM ('mcq', 'true_false');
CREATE TYPE challenge_status_enum AS ENUM ('pending', 'completed');

CREATE TABLE IF NOT EXISTS challenges (
  challenge_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  room_id VARCHAR(36),
  theme VARCHAR NOT NULL,
  difficulty INTEGER NOT NULL,
  question_type question_type_enum NOT NULL,
  title VARCHAR NOT NULL,
  content text NOT NULL,
  question VARCHAR NOT NULL,
  options json NOT NULL,
  correct_option_id VARCHAR NOT NULL,
  tags json,
  status challenge_status_enum NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT challenges_pkey PRIMARY KEY (challenge_id),
  CONSTRAINT challenges_room_id_fkey FOREIGN KEY (room_id) REFERENCES rooms(room_id),
  CONSTRAINT challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS challenge_attempts (
  attempt_id VARCHAR(36) NOT NULL,
  challenge_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  attempt_number INTEGER NOT NULL,
  user_answer text NOT NULL,
  is_correct boolean NOT NULL,
  confidence_score INTEGER NOT NULL DEFAULT 0,
  reasoning text,
  time_taken_seconds INTEGER NOT NULL,
  time_limit_seconds INTEGER NOT NULL,
  xp_earned INTEGER NOT NULL,
  debrief json,
  submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT challenge_attempts_pkey PRIMARY KEY (attempt_id),
  CONSTRAINT challenge_attempts_challenge_id_fkey FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
  CONSTRAINT challenge_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);
