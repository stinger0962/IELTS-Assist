"""Opt-in full psql wrapper smoke test, isolated to the disposable CI database.

Without explicit local-test environment this test skips, never falls back.
"""
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from urllib.parse import urlsplit
from uuid import uuid4


@unittest.skipUnless(os.getenv('IELTS_TEST_POSTGRES_URL'), 'disposable PostgreSQL URL not provided')
class PostgresWrapperTest(unittest.TestCase):
    def test_complete_psql_script_against_synthetic_schema(self):
        self.assertEqual(os.getenv('IELTS_TEST_POSTGRES_ALLOW_DISPOSABLE'), '1')
        target = urlsplit(os.environ['IELTS_TEST_POSTGRES_URL'])
        self.assertIn(target.scheme, ('postgresql', 'postgresql+psycopg2'))
        self.assertIn(target.hostname, ('localhost', '127.0.0.1'))
        self.assertEqual(target.username, 'test_user')
        self.assertEqual(target.path, '/test_db')
        self.assertIn(target.port, (None, 5432, 5433))
        self.assertFalse(target.query or target.fragment)
        psql = shutil.which('psql')
        self.assertIsNotNone(psql, 'configured Postgres lane requires psql; no silent skip')
        import psycopg2
        connection = psycopg2.connect(host=target.hostname, port=target.port or 5432,
                                     user='test_user', password=target.password,
                                     dbname='test_db', connect_timeout=3)
        connection.autocommit = True
        schema = 'ielts_report_qa_' + uuid4().hex
        created = False
        try:
            with connection.cursor() as cur:
                cur.execute('SELECT current_user, current_database()')
                self.assertEqual(cur.fetchone(), ('test_user', 'test_db'))
                cur.execute(f'CREATE SCHEMA {schema}')
                created = True
                cur.execute(f'SET search_path TO {schema}')
                cur.execute('''
                    CREATE TABLE users (id bigint PRIMARY KEY, created_at timestamp);
                    CREATE TABLE generated_practices (id bigint PRIMARY KEY, skill text, generated_date timestamp);
                    CREATE TABLE user_practices (user_id bigint, practice_id bigint, submitted_at timestamp);
                    INSERT INTO users VALUES (1, '2026-11-01'), (2, '2026-11-01'), (99, '2026-11-01');
                    INSERT INTO generated_practices VALUES
                        (1, 'WRITING', '2026-11-01'), (2, 'speaking', '2026-11-01'),
                        (3, 'writing', '2026-11-01'), (4, 'reading', '2026-11-01');
                    INSERT INTO user_practices VALUES
                        (1, 1, '2026-11-01'), (1, 2, '2026-11-02'),
                        (2, 1, '2026-11-01'), (2, 3, '2026-11-02'),
                        (99, 1, '2026-11-01'), (99, 3, '2026-11-02');
                ''')
            # Strip inherited PG* settings so neither service nor hostaddr can
            # redirect the explicitly validated disposable connection.
            env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
            env.update(PGHOST=target.hostname, PGPORT=str(target.port or 5432),
                       PGUSER='test_user', PGDATABASE='test_db',
                       PGPASSWORD=target.password or '', PGPASSFILE='/dev/null',
                       PGCONNECT_TIMEOUT='3', PGOPTIONS=f'-csearch_path={schema}')
            script = Path(__file__).resolve().parents[1] / 'learner_activity_30d.sql'
            result = subprocess.run([psql, '-X', '-q', '--csv',
                '-v', 'report_as_of_utc=2026-11-15T00:00:00Z',
                '-v', 'exclude_user_ids=99', '-f', str(script)],
                env=env, capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = list(csv.DictReader(io.StringIO(result.stdout)))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            for key, expected in {
                'signups': 2, 'active_learners_with_completion': 2,
                'completed_practices': 4, 'writing_completions': 3,
                'writing_learners': 2, 'returning_learners_two_utc_dates': 2,
                'returning_learners_with_writing': 2,
                'returning_writing_learners_two_utc_dates': 1,
                'content_pool_rows_created_not_learner_activity': 4,
            }.items():
                self.assertEqual(int(row[key]), expected, key)
            self.assertNotIn('user_id', row)
        finally:
            try:
                if created:
                    with connection.cursor() as cur:
                        cur.execute(f'DROP SCHEMA {schema} CASCADE')
            finally:
                connection.close()
