-- Least-privilege database role for the HintSpark web app.
--
-- WHY: the app only ever INSERTs rows into public.learning_events. If
-- DATABASE_URL leaks (e.g. via a sandbox escape), an attacker holding this
-- role can add junk rows - but cannot read, change or delete learner data,
-- and cannot touch any other table. The default `postgres` user can do all
-- of that and more.
--
-- HOW (run by a human, in the Supabase dashboard -> SQL Editor):
--   1. Generate a long random password in your password manager.
--      Do NOT paste it into chat, code, commits or tickets.
--   2. Replace <GENERATED_PASSWORD> below, run this script, then clear the editor.
--   3. Build the new DATABASE_URL from the dashboard's "Connect" panel, using
--      this role's name instead of `postgres` (check the dashboard for the
--      exact username format the connection pooler expects).
--   4. Store it ONLY in Render's environment settings (or Secret Manager),
--      redeploy, and confirm new rows still arrive.
--   5. Rotate the `postgres` password (Settings -> Database) so any old
--      DATABASE_URL that may have leaked stops working.
--
-- Verify each step against the current Supabase docs before running.

CREATE ROLE hintspark_writer LOGIN PASSWORD '<GENERATED_PASSWORD>';

-- Nothing by default...
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM hintspark_writer;

-- ...except the one thing the app needs.
GRANT USAGE ON SCHEMA public TO hintspark_writer;
GRANT INSERT ON public.learning_events TO hintspark_writer;

-- If learning_events has a serial/identity id column, the role also needs:
-- GRANT USAGE ON SEQUENCE public.learning_events_id_seq TO hintspark_writer;

-- If Row Level Security is enabled on the table (recommended), allow inserts only:
-- CREATE POLICY hintspark_writer_insert ON public.learning_events
--   FOR INSERT TO hintspark_writer WITH CHECK (true);
