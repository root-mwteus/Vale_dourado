import re
import sqlite3

from flask import current_app
from werkzeug.security import generate_password_hash

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency for local runs
    create_client = None


class SupabaseCursor:
    def __init__(self, rows):
        self._rows = list(rows or [])
        self._index = 0

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        rows = list(self._rows)
        self._index = len(self._rows)
        return rows

    @property
    def lastrowid(self):
        if not self._rows:
            return None
        return self._rows[0].get('id')


class SupabaseConnection:
    def __init__(self, client):
        self.client = client

    def execute(self, query, params=None):
        params = [] if params is None else list(params)
        query_upper = query.strip().upper()

        if query_upper.startswith('SELECT'):
            return self._execute_select(query, params)
        if query_upper.startswith('INSERT'):
            return self._execute_insert(query, params)
        if query_upper.startswith('UPDATE'):
            return self._execute_update(query, params)
        if query_upper.startswith('DELETE'):
            return self._execute_delete(query, params)

        return SupabaseCursor([])

    def _execute_select(self, query, params):
        table_name = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
        if not table_name:
            return SupabaseCursor([])

        table = self.client.from_(table_name.group(1))
        select_query = table.select('*')

        if 'COUNT(*)' in query.upper():
            select_query = table.select('id', count='exact')
        elif 'SELECT DETALHES' in query.upper():
            select_query = table.select('detalhes')
        elif 'SELECT USERNAME' in query.upper():
            select_query = table.select('username')
        elif 'SELECT ID, USERNAME, ROLE' in query.upper():
            select_query = table.select('id,username,role')

        normalized = query.replace('\n', ' ').strip().upper()
        if 'WHERE USERNAME = ?' in normalized:
            select_query = select_query.eq('username', params[0])
        elif 'WHERE ID = ?' in normalized:
            select_query = select_query.eq('id', params[0])
        elif 'LOWER(RESPONSAVEL) = LOWER(?)' in normalized:
            select_query = select_query.ilike('responsavel', params[0])
        elif 'WHERE 1=1' in normalized and 'ORDER BY CREATED_AT DESC' in normalized:
            select_query = select_query.order('created_at', desc=True)
        elif 'ORDER BY CREATED_AT DESC' in normalized:
            select_query = select_query.order('created_at', desc=True)
        elif 'ORDER BY USERNAME' in normalized:
            select_query = select_query.order('username', desc=False)

        if 'LIMIT 5' in normalized:
            select_query = select_query.limit(5)
        if 'LIMIT 10' in normalized:
            select_query = select_query.limit(10)

        if 'WHERE ORDEM_ID = ?' in normalized:
            select_query = select_query.eq('ordem_id', params[0])

        if 'WHERE 1=1' in normalized and 'STATUS = ?' in normalized:
            select_query = select_query.eq('status', params[0])
        if 'WHERE 1=1' in normalized and 'PRIORIDADE = ?' in normalized:
            select_query = select_query.eq('prioridade', params[0])
        if 'WHERE 1=1' in normalized and 'LOWER(RESPONSAVEL)' in normalized:
            select_query = select_query.ilike('responsavel', params[0])
        if 'CREATED_AT >= ?' in normalized:
            select_query = select_query.gte('created_at', params[0])

        response = select_query.execute()
        rows = list(response.data or [])
        if 'COUNT(*)' in query.upper():
            count_value = getattr(response, 'count', None)
            if count_value is None:
                count_value = len(rows)
            rows = [{'total': count_value}]
        return SupabaseCursor(rows)

    def _execute_insert(self, query, params):
        match = re.search(r'INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)', query, re.IGNORECASE | re.DOTALL)
        if not match:
            return SupabaseCursor([])

        table_name = match.group(1)
        columns = [col.strip() for col in match.group(2).split(',')]
        values = list(params)
        payload = dict(zip(columns, values))

        response = self.client.from_(table_name).insert(payload).execute()
        rows = list(response.data or [])
        return SupabaseCursor(rows)

    def _execute_update(self, query, params):
        match = re.search(r'UPDATE\s+(\w+)\s+SET\s+(.*?)\s+WHERE\s+(.*)', query, re.IGNORECASE | re.DOTALL)
        if not match:
            return SupabaseCursor([])

        table_name = match.group(1)
        assignments = [item.strip() for item in match.group(2).split(',')]
        payload = {}
        for assignment in assignments:
            column, value = assignment.split('=', 1)
            payload[column.strip()] = params.pop(0)

        where_field, where_value = match.group(3).split('=', 1)
        self.client.from_(table_name).update(payload).eq(where_field.strip(), params.pop(0)).execute()
        return SupabaseCursor([])

    def _execute_delete(self, query, params):
        match = re.search(r'DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.*)', query, re.IGNORECASE | re.DOTALL)
        if not match:
            return SupabaseCursor([])

        table_name = match.group(1)
        condition = match.group(2).strip()
        field, value = condition.split('=', 1)
        self.client.from_(table_name).delete().eq(field.strip(), params[0]).execute()
        return SupabaseCursor([])

    def commit(self):
        return None

    def close(self):
        return None

    def rollback(self):
        return None


def get_db():
    if current_app.config.get('DB_BACKEND') == 'supabase':
        if create_client is None:
            raise RuntimeError('supabase package must be installed to use Supabase.')
        client = create_client(current_app.config['SUPABASE_URL'], current_app.config['SUPABASE_KEY'])
        return SupabaseConnection(client)

    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()

    if current_app.config.get('DB_BACKEND') == 'supabase':
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('mateus', generate_password_hash('1234'), 'funcionario'),
            )
        except Exception:
            pass
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('Deivisson', generate_password_hash('4321'), 'admin'),
            )
        except Exception:
            pass
        try:
            conn.commit()
        except Exception:
            pass
        try:
            conn.close()
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
