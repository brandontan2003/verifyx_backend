CREATE TABLE IF NOT EXISTS room_participants (
  room_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  username VARCHAR NOT NULL,
  challenge_id VARCHAR(36),
  is_correct boolean,
  xp_earned INTEGER,
  time_taken_seconds INTEGER,
  finished_at TIMESTAMP WITH TIME ZONE,
  joined_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT room_participants_pkey PRIMARY KEY (room_id, user_id),
  CONSTRAINT room_participants_challenge_id_fkey FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
  CONSTRAINT room_participants_room_id_fkey FOREIGN KEY (room_id) REFERENCES rooms(room_id),
  CONSTRAINT room_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);
