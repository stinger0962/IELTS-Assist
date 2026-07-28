#!/bin/bash
# Nightly Postgres backup with 7-day rotation.
#
# The droplet ran with NO backups of any kind until 2026-07-27: a disk failure
# would have permanently destroyed every account, essay, grade and saved word.
# The database is ~15 MB, so this costs essentially nothing.
#
# Installed to /usr/local/bin/ielts-backup.sh by the deploy workflow and run
# from /etc/cron.d/ielts-backup at 02:00 UTC. Lives in the repo so it is
# reviewed and version-controlled rather than hand-written on the server.
set -euo pipefail

ENV_FILE=${ENV_FILE:-/root/IELTS-Assist/backend/.env}
DEST=${DEST:-/root/backups}
KEEP=${KEEP:-7}
STAMP=$(date -u +%Y%m%d-%H%M%S)

DB_URL=$(grep -m1 '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- || true)
if [ -z "$DB_URL" ]; then
  echo "FATAL: no DATABASE_URL in $ENV_FILE" >&2
  exit 1
fi

umask 077
install -d -m 700 "$DEST"
TMP="$DEST/ielts-$STAMP.sql.gz.tmp"
OUT="$DEST/ielts-$STAMP.sql.gz"

pg_dump "$DB_URL" | gzip > "$TMP"

# A corrupt dump is worse than no dump, because it looks like protection.
# Verify before it is allowed to count as a backup.
gzip -t "$TMP"
SIZE=$(stat -c%s "$TMP")
if [ "$SIZE" -lt 1024 ]; then
  echo "FATAL: dump is only ${SIZE} bytes — refusing to keep it" >&2
  rm -f "$TMP"
  exit 1
fi
# Confirm it actually contains schema, not just a valid-but-empty gzip.
if ! zcat "$TMP" | head -200 | grep -q "CREATE TABLE"; then
  echo "FATAL: dump contains no CREATE TABLE — refusing to keep it" >&2
  rm -f "$TMP"
  exit 1
fi

mv "$TMP" "$OUT"

# Rotate: keep the newest $KEEP, delete the rest.
ls -1t "$DEST"/ielts-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "backup ok: $OUT (${SIZE} bytes), $(ls -1 "$DEST"/ielts-*.sql.gz | wc -l) kept"
