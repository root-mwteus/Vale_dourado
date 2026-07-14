import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency for local runs
    create_client = None

app = Flask(__name__)


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


def load_environment_config():
    dotenv_path = Path(app.root_path) / '.env'
    if dotenv_path.exists():
        for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    secret_key = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
    app.config['SECRET_KEY'] = secret_key
    app.secret_key = secret_key

    supabase_url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
    database_path = os.environ.get('DATABASE_PATH') or os.environ.get('DATABASE')

    if supabase_url and supabase_key:
        app.config['DB_BACKEND'] = 'supabase'
        app.config['SUPABASE_URL'] = supabase_url
        app.config['SUPABASE_KEY'] = supabase_key
    elif database_path and database_path.startswith('https://'):
        app.config['DB_BACKEND'] = 'supabase'
        app.config['SUPABASE_URL'] = database_path
        app.config['SUPABASE_KEY'] = supabase_key or ''
    elif database_path:
        if database_path.startswith('sqlite:///'):
            resolved_path = database_path[len('sqlite:///'):]
        else:
            resolved_path = database_path

        if os.path.isabs(resolved_path):
            app.config['DATABASE'] = resolved_path
        else:
            app.config['DATABASE'] = os.path.abspath(os.path.join(app.root_path, resolved_path))
        app.config['DB_BACKEND'] = 'sqlite'
    else:
        app.config['DB_BACKEND'] = 'sqlite'
        app.config['DATABASE'] = os.path.join(app.root_path, 'orders.db')

    return app.config


load_environment_config()


def get_db():
    if app.config.get('DB_BACKEND') == 'supabase':
        if create_client is None:
            raise RuntimeError('supabase package must be installed to use Supabase.')
        client = create_client(app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
        return SupabaseConnection(client)

    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()

    if app.config.get('DB_BACKEND') == 'supabase':
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


init_db()


def login_required(route_function):
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('home'))
        return route_function(*args, **kwargs)

    wrapper.__name__ = route_function.__name__
    return wrapper


def registrar_historico(ordem_id, usuario, acao, detalhes):
    conn = get_db()
    conn.execute(
        'INSERT INTO historico_ordens (ordem_id, usuario, acao, detalhes, created_at) VALUES (?, ?, ?, ?, ?)',
        (ordem_id, usuario, acao, detalhes, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()


def registrar_historico_alteracao(ordem_id, usuario, ordem_anterior, dados_novos):
    alteracoes = []
    campos = ['titulo', 'descricao', 'prioridade', 'setor', 'responsavel', 'status', 'cliente']
    labels = {
        'titulo': 'Título',
        'descricao': 'Descrição',
        'prioridade': 'Prioridade',
        'setor': 'Setor',
        'responsavel': 'Responsável',
        'status': 'Status',
        'cliente': 'Cliente',
    }

    for campo in campos:
        antigo = str(ordem_anterior.get(campo, '') or '')
        novo = str(dados_novos.get(campo, '') or '')
        if antigo != novo:
            alteracoes.append(f"{labels[campo]}: '{antigo}' -> '{novo}'")

    if alteracoes:
        detalhes = 'Alterações: ' + '; '.join(alteracoes)
    else:
        detalhes = 'Ordem atualizada sem alterações relevantes.'

    registrar_historico(ordem_id, usuario, 'Atualizada', detalhes)


@app.route('/')
def home():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    usuario_digitado = request.form.get('username', '').strip()
    senha_digitada = request.form.get('password', '')
    modulo_selecionado = request.form.get('modulo', '')

    conn = get_db()
    usuario = conn.execute(
        'SELECT * FROM users WHERE username = ?', (usuario_digitado,)
    ).fetchone()
    conn.close()

    if not usuario or not check_password_hash(usuario['password_hash'], senha_digitada):
        return render_template('login.html', mensagem_erro='Erro: Usuário ou Senha incorretos!')

    if usuario['role'] == 'funcionario' and modulo_selecionado != 'funcionario':
        return render_template('login.html', mensagem_erro="Erro: O usuário não tem acesso ao módulo Gestão!")

    if usuario['role'] == 'admin' and modulo_selecionado != 'admin':
        return render_template('login.html', mensagem_erro='Erro: Login administrativo')

    session['usuario'] = usuario['username']
    session['role'] = usuario['role']
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    if session.get('role') == 'funcionario':
        query = "SELECT COUNT(*) as total FROM ordens WHERE LOWER(responsavel) = LOWER(?)"
        params = [session.get('usuario')]
        total_ordens = conn.execute(query, params).fetchone()['total']
        abertas = conn.execute("SELECT COUNT(*) as total FROM ordens WHERE LOWER(responsavel) = LOWER(?) AND status != 'Concluída' AND status != 'Cancelada'", params).fetchone()['total']
        concluídas = conn.execute("SELECT COUNT(*) as total FROM ordens WHERE LOWER(responsavel) = LOWER(?) AND status = 'Concluída'", params).fetchone()['total']
        recentes = conn.execute('SELECT * FROM ordens WHERE LOWER(responsavel) = LOWER(?) ORDER BY created_at DESC LIMIT 5', params).fetchall()
    else:
        total_ordens = conn.execute('SELECT COUNT(*) as total FROM ordens').fetchone()['total']
        abertas = conn.execute("SELECT COUNT(*) as total FROM ordens WHERE status != 'Concluída' AND status != 'Cancelada'").fetchone()['total']
        concluídas = conn.execute("SELECT COUNT(*) as total FROM ordens WHERE status = 'Concluída'").fetchone()['total']
        recentes = conn.execute(
            'SELECT * FROM ordens ORDER BY created_at DESC LIMIT 5'
        ).fetchall()
    conn.close()

    return render_template(
        'dashboard.html',
        total_ordens=total_ordens,
        abertas=abertas,
        concluídas=concluídas,
        recentes=recentes,
    )


@app.route('/ordens')
@login_required
def ordens():
    busca = request.args.get('busca', '').strip()
    status_filtro = request.args.get('status', '')
    prioridade_filtro = request.args.get('prioridade', '')
    responsavel_filtro = request.args.get('responsavel', '')
    periodo_filtro = request.args.get('periodo', '')

    query = 'SELECT * FROM ordens WHERE 1=1'
    params = []

    if session.get('role') == 'funcionario':
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(session.get('usuario'))

    if busca:
        query += ' AND (titulo LIKE ? OR descricao LIKE ? OR cliente LIKE ? OR responsavel LIKE ?)' 
        termo = f'%{busca}%'
        params.extend([termo, termo, termo, termo])

    if status_filtro:
        query += ' AND status = ?'
        params.append(status_filtro)

    if prioridade_filtro:
        query += ' AND prioridade = ?'
        params.append(prioridade_filtro)

    if responsavel_filtro:
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(responsavel_filtro)

    if periodo_filtro:
        hoje = datetime.now()
        if periodo_filtro == '7dias':
            limite = (hoje - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        elif periodo_filtro == '30dias':
            limite = (hoje - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        elif periodo_filtro == '90dias':
            limite = (hoje - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            limite = None

        if limite:
            query += ' AND created_at >= ?'
            params.append(limite)

    query += ' ORDER BY created_at DESC'

    conn = get_db()
    lista = conn.execute(query, params).fetchall()

    if session.get('role') == 'admin':
        resumo_por_responsavel = conn.execute(
            "SELECT responsavel, COUNT(*) as total, SUM(CASE WHEN status = 'Concluída' THEN 1 ELSE 0 END) as concluida, SUM(CASE WHEN status != 'Concluída' AND status != 'Cancelada' THEN 1 ELSE 0 END) as andamento FROM ordens GROUP BY responsavel ORDER BY responsavel"
        ).fetchall()
        resumo_por_setor = conn.execute(
            "SELECT setor, COUNT(*) as total, SUM(CASE WHEN status = 'Concluída' THEN 1 ELSE 0 END) as concluida, SUM(CASE WHEN status != 'Concluída' AND status != 'Cancelada' THEN 1 ELSE 0 END) as andamento FROM ordens GROUP BY setor ORDER BY setor"
        ).fetchall()
        ordens_prioritarias = conn.execute(
            "SELECT * FROM ordens WHERE prioridade = 'Alta' AND status != 'Concluída' AND status != 'Cancelada' ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        ordens_atrasadas = conn.execute(
            "SELECT * FROM ordens WHERE status = 'Em andamento' OR status = 'Aberta' ORDER BY created_at ASC LIMIT 5"
        ).fetchall()
    else:
        resumo_por_responsavel = []
        resumo_por_setor = []
        ordens_prioritarias = []
        ordens_atrasadas = []

    conn.close()
    return render_template(
        'ordens.html',
        ordens=lista,
        busca=busca,
        status_filtro=status_filtro,
        prioridade_filtro=prioridade_filtro,
        responsavel_filtro=responsavel_filtro,
        periodo_filtro=periodo_filtro,
        resumo_por_responsavel=resumo_por_responsavel,
        resumo_por_setor=resumo_por_setor,
        ordens_prioritarias=ordens_prioritarias,
        ordens_atrasadas=ordens_atrasadas,
    )


@app.route('/ordens/nova', methods=['GET', 'POST'])
@login_required
def nova_ordem():
    if session.get('role') == 'funcionario':
        return redirect(url_for('ordens'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        prioridade = request.form.get('prioridade', '').strip()
        setor = request.form.get('setor', '').strip()
        responsavel = request.form.get('responsavel', '').strip()
        status = request.form.get('status', '').strip()
        cliente = request.form.get('cliente', '').strip()

        if not all([titulo, descricao, prioridade, setor, responsavel, status, cliente]):
            return render_template('nova_ordem.html', mensagem_erro='Preencha todos os campos para salvar a ordem.')

        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        result = conn.execute(
            'INSERT INTO ordens (titulo, descricao, prioridade, setor, responsavel, status, cliente, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id',
            (titulo, descricao, prioridade, setor, responsavel, status, cliente, agora, agora),
        ).fetchone()
        conn.commit()
        ordem_id = result['id'] if result and isinstance(result, dict) else (result[0] if result else None)
        conn.close()
        registrar_historico(ordem_id, session.get('usuario', 'Sistema'), 'Criada', f"Ordem criada com status {status}.")
        return redirect(url_for('ordens'))

    return render_template('nova_ordem.html')


@app.route('/ordens/<int:ordem_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_ordem(ordem_id):
    conn = get_db()
    ordem = conn.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,)).fetchone()

    if not ordem:
        conn.close()
        return redirect(url_for('ordens'))

    if session.get('role') == 'funcionario' and str(ordem['responsavel']).lower() != str(session.get('usuario', '')).lower():
        conn.close()
        return redirect(url_for('ordens'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        prioridade = request.form.get('prioridade', '').strip()
        setor = request.form.get('setor', '').strip()
        responsavel = request.form.get('responsavel', '').strip()
        status = request.form.get('status', '').strip()
        cliente = request.form.get('cliente', '').strip()

        if not all([titulo, descricao, prioridade, setor, responsavel, status, cliente]):
            conn.close()
            return render_template('nova_ordem.html', ordem=ordem, mensagem_erro='Preencha todos os campos para atualizar a ordem.')

        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dados_novos = {
            'titulo': titulo,
            'descricao': descricao,
            'prioridade': prioridade,
            'setor': setor,
            'responsavel': responsavel,
            'status': status,
            'cliente': cliente,
        }
        conn.execute(
            'UPDATE ordens SET titulo = ?, descricao = ?, prioridade = ?, setor = ?, responsavel = ?, status = ?, cliente = ?, updated_at = ? WHERE id = ?',
            (titulo, descricao, prioridade, setor, responsavel, status, cliente, agora, ordem_id),
        )
        conn.commit()
        conn.close()
        registrar_historico_alteracao(ordem_id, session.get('usuario', 'Sistema'), dict(ordem), dados_novos)
        return redirect(url_for('ordens'))

    conn.close()
    return render_template('nova_ordem.html', ordem=ordem)


@app.route('/ordens/<int:ordem_id>')
@login_required
def detalhe_ordem(ordem_id):
    conn = get_db()
    ordem = conn.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,)).fetchone()
    historico = conn.execute(
        'SELECT * FROM historico_ordens WHERE ordem_id = ? ORDER BY created_at DESC',
        (ordem_id,),
    ).fetchall()
    conn.close()

    if not ordem:
        return redirect(url_for('ordens'))

    return render_template('detalhe_ordem.html', ordem=ordem, historico=historico)


@app.route('/ordens/<int:ordem_id>/excluir', methods=['POST'])
@login_required
def excluir_ordem(ordem_id):
    conn = get_db()
    ordem = conn.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,)).fetchone()
    if session.get('role') == 'funcionario' and str(ordem['responsavel']).lower() != str(session.get('usuario', '')).lower():
        conn.close()
        return redirect(url_for('ordens'))

    conn.execute('DELETE FROM ordens WHERE id = ?', (ordem_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('ordens'))


@app.route('/usuarios')
@login_required
def listar_usuarios():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    conn = get_db()
    usuarios = conn.execute('SELECT id, username, role FROM users ORDER BY username').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=usuarios)


@app.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def novo_usuario():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'funcionario').strip()

        if not username or not password or not confirm_password:
            return render_template('novo_usuario.html', mensagem_erro='Preencha todos os campos para cadastrar o usuário.')

        if password != confirm_password:
            return render_template('novo_usuario.html', mensagem_erro='As senhas não coincidem.')

        if role not in {'funcionario', 'admin'}:
            return render_template('novo_usuario.html', mensagem_erro='Perfil inválido.')

        conn = get_db()
        usuario_existente = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if usuario_existente:
            conn.close()
            return render_template('novo_usuario.html', mensagem_erro='Este nome de usuário já existe.')

        conn.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), role),
        )
        conn.commit()
        conn.close()
        return redirect(url_for('listar_usuarios'))

    return render_template('novo_usuario.html')


@app.route('/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_usuario(usuario_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    conn = get_db()
    usuario = conn.execute('SELECT id, username, role FROM users WHERE id = ?', (usuario_id,)).fetchone()
    if not usuario:
        conn.close()
        return redirect(url_for('listar_usuarios'))

    if request.method == 'POST':
        novo_role = request.form.get('role', '').strip()
        nova_senha = request.form.get('password', '')
        confirm_nova_senha = request.form.get('confirm_password', '')

        if novo_role not in {'funcionario', 'admin'}:
            conn.close()
            return render_template('editar_usuario.html', usuario=usuario, mensagem_erro='Perfil inválido.')

        if nova_senha or confirm_nova_senha:
            if nova_senha != confirm_nova_senha:
                conn.close()
                return render_template('editar_usuario.html', usuario=usuario, mensagem_erro='As senhas não coincidem.')
            conn.execute('UPDATE users SET role = ?, password_hash = ? WHERE id = ?', (novo_role, generate_password_hash(nova_senha), usuario_id))
        else:
            conn.execute('UPDATE users SET role = ? WHERE id = ?', (novo_role, usuario_id))

        conn.commit()
        conn.close()
        return redirect(url_for('listar_usuarios'))

    conn.close()
    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/usuarios/<int:usuario_id>/excluir', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    conn = get_db()
    usuario = conn.execute('SELECT username FROM users WHERE id = ?', (usuario_id,)).fetchone()
    if not usuario:
        conn.close()
        return redirect(url_for('listar_usuarios'))

    if usuario['username'] == session.get('usuario'):
        conn.close()
        return redirect(url_for('listar_usuarios'))

    conn.execute('DELETE FROM users WHERE id = ?', (usuario_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('listar_usuarios'))


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('usuario', None)
    session.pop('role', None)
    return redirect(url_for('home'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)