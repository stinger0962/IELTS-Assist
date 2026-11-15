"""Synthetic SQLite fixture tests of the unchanged portable aggregate core.

Postgres/psql parameter binding and transaction commands require a separate
Postgres smoke test; these tests do not import the app or connect to any service.
"""
import pathlib
import sqlite3
import unittest

SQL = (pathlib.Path(__file__).resolve().parents[1] / 'learner_activity_30d.sql').read_text()
CORE = SQL.split('-- BEGIN PORTABLE AGGREGATE CORE (fixture-tested without production access)\n', 1)[1].split('\nROLLBACK;', 1)[0]


class LearnerActivityTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE users (id INTEGER, created_at TEXT);
            CREATE TABLE generated_practices (id INTEGER, skill TEXT, generated_date TEXT);
            CREATE TABLE user_practices (user_id INTEGER, practice_id INTEGER, submitted_at TEXT);
        ''')

    def tearDown(self):
        self.db.close()

    def report(self, exclude=()):
        # Only the Postgres-specific parameter/exclusion CTE is substituted.
        placeholders = ','.join('(?)' for _ in exclude)
        exclusions = f'VALUES {placeholders}' if exclude else 'SELECT NULL WHERE 0'
        query = '''WITH params AS (SELECT ? AS window_start, ? AS window_end),
                    excluded(user_id) AS (''' + exclusions + '),\n' + CORE
        return dict(self.db.execute(query, ('2026-10-16 00:00:00', '2026-11-15 00:00:00', *exclude)).fetchone())

    def test_empty_database_returns_zero_counts(self):
        row = self.report()
        self.assertTrue(all(v == 0 for k, v in row.items() if not k.startswith('window_')))

    def test_boundaries_exclusions_returns_and_automated_pool(self):
        self.db.executemany('INSERT INTO users VALUES (?,?)', [
            (1, '2026-10-01 00:00:00'), (2, '2026-10-16 00:00:00'),
            (3, '2026-11-15 00:00:00'), (4, '2026-11-01 00:00:00'),
            (99, '2026-11-01 00:00:00'),
        ])
        self.db.executemany('INSERT INTO generated_practices VALUES (?,?,?)', [
            (1, 'WRITING', '2026-10-16 00:00:00'),
            (2, 'speaking', '2026-11-01 00:00:00'),
            (3, 'reading', '2026-10-01 00:00:00'),
            (4, 'listening', '2026-11-15 00:00:00'),
            (5, 'grammar', '2026-11-02 00:00:00'),
            (6, 'writing', '2026-11-02 00:00:00'),  # untouched pool content
        ])
        self.db.executemany('INSERT INTO user_practices VALUES (?,?,?)', [
            (1, 1, '2026-10-16 00:00:00'),  # inclusive start
            (1, 2, '2026-11-01 10:00:00'),  # returning learner
            (1, 3, '2026-11-01 11:00:00'),
            (2, 1, '2026-11-02 10:00:00'),
            (2, 5, '2026-11-02 11:00:00'),  # same day != returning
            (3, 4, '2026-11-15 00:00:00'),  # exclusive end
            (4, 1, None),  # dealt card != completion
            (4, 2, '2026-10-15 23:59:59'),
            (99, 1, '2026-11-01 00:00:00'),  # operator excluded
            (99, 2, '2026-11-02 00:00:00'),
        ])
        row = self.report(exclude=(99,))
        expected = dict(signups=2, active_learners_with_completion=2,
                        returning_learners_two_utc_dates=1, completed_practices=5,
                        writing_completions=2, writing_learners=2,
                        returning_learners_with_writing=1,
                        returning_writing_learners_two_utc_dates=0,
                        speaking_completions=1, speaking_learners=1,
                        reading_completions=1, listening_completions=0,
                        grammar_completions=1,
                        content_pool_rows_created_not_learner_activity=4)
        for key, value in expected.items():
            self.assertEqual(row[key], value, key)
        self.assertEqual(self.report()['completed_practices'], 7)
        self.assertEqual(self.report(exclude=(1, 2, 99))['active_learners_with_completion'], 0)

    def test_returning_writing_cohorts_are_distinct_and_not_additive(self):
        self.db.executemany('INSERT INTO users VALUES (?,?)', [
            (i, '2026-10-01 00:00:00') for i in (1, 2, 3, 4, 99)
        ])
        self.db.executemany('INSERT INTO generated_practices VALUES (?,?,?)', [
            (1, 'writing', '2026-10-01 00:00:00'),
            (2, 'speaking', '2026-10-01 00:00:00'),
            (3, 'reading', '2026-10-01 00:00:00'),
        ])
        self.db.executemany('INSERT INTO user_practices VALUES (?,?,?)', [
            (1, 1, '2026-11-01 10:00:00'),
            (1, 2, '2026-11-02 10:00:00'),  # returning writer, not repeat writing dates
            (2, 1, '2026-11-01 10:00:00'),
            (2, 1, '2026-11-02 10:00:00'),  # both cohorts
            (3, 1, '2026-11-01 10:00:00'),
            (3, 1, '2026-11-01 11:00:00'),  # same date, neither returning cohort
            (4, 3, '2026-11-01 10:00:00'),
            (4, 3, '2026-11-02 10:00:00'),  # returning non-writer
            (99, 1, '2026-11-01 10:00:00'),
            (99, 1, '2026-11-02 10:00:00'),  # excluded operator
            (3, 1, '2026-11-15 00:00:00'),  # outside window does not create retention
        ])
        row = self.report(exclude=(99,))
        self.assertEqual(row['writing_learners'], 3)
        self.assertEqual(row['returning_learners_two_utc_dates'], 3)
        self.assertEqual(row['returning_learners_with_writing'], 2)
        self.assertEqual(row['returning_writing_learners_two_utc_dates'], 1)
        included = self.report()
        self.assertEqual(included['returning_learners_with_writing'], 3)
        self.assertEqual(included['returning_writing_learners_two_utc_dates'], 2)

    def test_read_only_and_aggregate_output_contract(self):
        self.assertIn('BEGIN TRANSACTION READ ONLY;', SQL)
        self.assertIn("SET LOCAL statement_timeout = '30s';", SQL)
        self.assertIn("SET LOCAL lock_timeout = '3s';", SQL)
        self.assertTrue(SQL.rstrip().endswith('ROLLBACK;'))
        for forbidden in ('email', 'username', 'user_answers', 'hashed_password', 'content', 'token', 'ip_address'):
            # content_pool_rows... is an aggregate label, not selected content.
            self.assertNotIn(forbidden, CORE.replace('content_pool_rows_created_not_learner_activity', 'pool_rows'))
        self.assertNotIn('user_id', self.report())


if __name__ == '__main__':
    unittest.main()
