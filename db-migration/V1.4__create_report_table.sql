CREATE TYPE report_status_enum AS ENUM ('pending', 'under_review', 'approved', 'rejected');

CREATE TABLE IF NOT EXISTS reports (
  report_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  content_type VARCHAR NOT NULL,
  content text NOT NULL,
  context text,
  harm_type VARCHAR NOT NULL,
  status report_status_enum NOT NULL DEFAULT 'pending',
  admin_notes text,
  resolved_by VARCHAR(36),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT reports_pkey PRIMARY KEY (report_id),
  CONSTRAINT reports_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES users(user_id),
  CONSTRAINT reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id),
  CONSTRAINT reports_content_type_check CHECK (content_type IN ('url', 'message', 'image', 'video', 'other')),
  CONSTRAINT reports_harm_type_check CHECK (harm_type IN (
    'misinformation', 'scam', 'phishing', 'deepfake', 'cyberbullying', 'other'
  ))
);
