CREATE TABLE IF NOT EXISTS news_posts (
  news_id VARCHAR(36) NOT NULL,
  report_id VARCHAR(36) NOT NULL,
  title VARCHAR NOT NULL,
  harm_type VARCHAR NOT NULL,
  content text NOT NULL,
  context text,
  upvotes INTEGER NOT NULL DEFAULT 0,
  downvotes INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT news_posts_pkey PRIMARY KEY (news_id),
  CONSTRAINT news_posts_report_id_fkey FOREIGN KEY (report_id) REFERENCES reports(report_id)
);

CREATE TABLE IF NOT EXISTS comments (
  comment_id VARCHAR(36) NOT NULL,
  news_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  parent_id VARCHAR(36),
  depth INTEGER NOT NULL DEFAULT 0,
  body text NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT comments_pkey PRIMARY KEY (comment_id),
  CONSTRAINT comments_news_id_fkey FOREIGN KEY (news_id) REFERENCES news_posts(news_id),
  CONSTRAINT comments_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES comments(comment_id),
  CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TYPE reaction_type_enum AS ENUM ('up_vote', 'down_vote');

CREATE TABLE IF NOT EXISTS news_reactions (
  reaction_id VARCHAR(36) NOT NULL,
  news_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  reaction_type reaction_type_enum NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT news_reactions_pkey PRIMARY KEY (reaction_id),
  CONSTRAINT news_reactions_news_id_fkey FOREIGN KEY (news_id) REFERENCES news_posts(news_id),
  CONSTRAINT news_reactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id),
  CONSTRAINT uq_news_reaction_user UNIQUE (news_id, user_id)
);

