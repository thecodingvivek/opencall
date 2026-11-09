CREATE TABLE IF NOT EXISTS opencall.farming_tasks (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES opencall.users(id) ON DELETE CASCADE,
  room_name text NOT NULL,
  task_key text NOT NULL CHECK (task_key ~ '^[A-Za-z0-9-]{1,40}$'),
  title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 100),
  status text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'in_progress', 'completed', 'blocked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, room_name, task_key)
);
CREATE INDEX IF NOT EXISTS farming_tasks_user_created_idx ON opencall.farming_tasks (user_id, created_at DESC, id DESC);
REVOKE ALL ON opencall.farming_tasks FROM PUBLIC, anon, authenticated;
ALTER TABLE opencall.farming_tasks ENABLE ROW LEVEL SECURITY;
