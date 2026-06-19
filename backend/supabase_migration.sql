-- Run this in Supabase Dashboard → SQL Editor

-- 1. Grant service_role access to existing cache tables
GRANT ALL ON analysis_cache TO service_role;
GRANT ALL ON verification_cache TO service_role;

-- 2. Create user_analyses table for per-user history
CREATE TABLE IF NOT EXISTS user_analyses (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  url text NOT NULL,
  spoken_claim text,
  written_claim text,
  core_news_claim text,
  evidence_findings jsonb,
  reasoning text,
  truth_score double precision,
  verdict text,
  thumbnail text,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE user_analyses ENABLE ROW LEVEL SECURITY;

-- 3. RLS policies: users can only see/insert/delete their own analyses
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'user_analyses' AND policyname = 'Users can read own analyses'
  ) THEN
    CREATE POLICY "Users can read own analyses"
      ON user_analyses FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'user_analyses' AND policyname = 'Users can insert own analyses'
  ) THEN
    CREATE POLICY "Users can insert own analyses"
      ON user_analyses FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'user_analyses' AND policyname = 'Users can delete own analyses'
  ) THEN
    CREATE POLICY "Users can delete own analyses"
      ON user_analyses FOR DELETE
      USING (auth.uid() = user_id);
  END IF;
END
$$;

GRANT ALL ON user_analyses TO service_role;
GRANT SELECT, INSERT, DELETE ON user_analyses TO authenticated;
