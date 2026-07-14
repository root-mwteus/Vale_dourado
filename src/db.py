import sqlite3

from flask import current_app
from werkzeug.security import generate_password_hash

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency for local runs
    create_client = None


def get_db():
    if current_app.config.get('DB_BACKEND') == 'supabase':
        if create_client is None:
            raise RuntimeError('supabase package must be installed to use Supabase.')
        return create_client(current_app.config['SUPABASE_URL'], current_app.config['SUPABASE_KEY'])

    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()

    if current_app.config.get('DB_BACKEND') == 'supabase':
        for username, password, role in (
            ('mateus', '1234', 'funcionario'),
            ('Deivisson', '4321', 'admin'),
        ):
            try:
                conn.from_('users').insert({
                    'username': username,
                    'password_hash': generate_password_hash(password),
                    'role': role,
                }).execute()
            except Exception:
                pass
        return

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            prioridade TEXT NOT NULL,
            setor TEXT NOT NULL,
            responsavel TEXT NOT NULL,
            status TEXT NOT NULL,
            cliente TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS historico_ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_id INTEGER NOT NULL,
            usuario TEXT NOT NULL,
            acao TEXT NOT NULL,
            detalhes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ordem_id) REFERENCES ordens(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ('mateus', generate_password_hash('1234'), 'funcionario'),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ('Deivisson', generate_password_hash('4321'), 'admin'),
    )

    conn.commit()
    conn.close()
