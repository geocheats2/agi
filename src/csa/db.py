"""SQLite storage: the single source of truth for agents, tasks, and events.

SQLite in WAL mode gives us transactional durability with zero operations.
A repository-like abstraction keeps Postgres a drop-in later (D-05 revisit
trigger). Events are append-only: this module exposes no delete of events.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  agent_id           TEXT PRIMARY KEY,
  role               TEXT NOT NULL,
  model_name         TEXT NOT NULL,
  config_version     TEXT NOT NULL DEFAULT 'v0',
  constitution_version TEXT NOT NULL DEFAULT 'v0.1.0',
  state_json         TEXT NOT NULL DEFAULT '{}',
  state_version      INTEGER NOT NULL DEFAULT 1,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id            TEXT PRIMARY KEY,
  parent_task_id     TEXT REFERENCES tasks(task_id),
  owner_agent_id     TEXT NOT NULL REFERENCES agents(agent_id),
  type               TEXT NOT NULL DEFAULT 'generic',
  objective          TEXT NOT NULL,
  acceptance_json    TEXT,
  status             TEXT NOT NULL CHECK (status IN
                 ('queued','active','blocked','completed','failed','cancelled','timed_out')),
  step               TEXT,
  result_ref         TEXT,
  max_tokens         INTEGER NOT NULL,
  max_cost_usd       REAL NOT NULL,
  tokens_used        INTEGER NOT NULL DEFAULT 0,
  cost_usd           REAL NOT NULL DEFAULT 0,
  created_at         TEXT NOT NULL,
  activated_at       TEXT,
  finished_at        TEXT,
  error              TEXT,
  parent_index       INTEGER NOT NULL DEFAULT 0,
  blocked_reason     TEXT
);

CREATE TABLE IF NOT EXISTS events (
  event_id        INTEGER PRIMARY KEY,
  ts              TEXT NOT NULL,
  type            TEXT NOT NULL,
  actor           TEXT NOT NULL,
  task_id         TEXT,
  agent_id        TEXT,
  prior_state_version  INTEGER,
  resulting_state_version INTEGER,
  severity        TEXT NOT NULL DEFAULT 'info',
  authorization   TEXT,
  summary         TEXT NOT NULL DEFAULT '',
  payload_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
