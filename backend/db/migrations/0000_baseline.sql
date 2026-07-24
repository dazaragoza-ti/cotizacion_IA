-- PLACEHOLDER: no fabricar el esquema a mano.
-- Generar con pg_dump desde Supabase (ver README.md y backend/DEPLOY.md):
--
--   pg_dump --schema-only --no-owner --no-privileges \
--     "$DATABASE_URL" > backend/db/migrations/0000_baseline.sql
--
-- Este archivo existe para documentar la convención de numeración;
-- reemplázalo con el dump real cuando tengas la connection string.
SELECT '0000_baseline pendiente de pg_dump' AS nota;
