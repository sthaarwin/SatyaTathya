import { createClient } from '@supabase/supabase-js';

// ── Browser (public) client ───────────────────────────────────────────────────
// Safe to use in React components and client-side code.
// Only has access to what RLS (Row Level Security) allows for the current user.

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// ── Type helpers ──────────────────────────────────────────────────────────────

export type AuthUser = {
  id: string;
  email: string | undefined;
  full_name: string | null;
};
