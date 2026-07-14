from datetime import datetime

from flask import current_app

from src.db import get_db

STATUS_CONCLUIDA = 'Concluída'
STATUS_CANCELADA = 'Cancelada'


def _is_supabase():
    return current_app.config.get('DB_BACKEND') == 'supabase'


def _agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _agregar_por_campo(rows, campo):
    agregados = {}
    for r in rows:
        chave = r.get(campo)
        item = agregados.setdefault(chave, {campo: chave, 'total': 0, 'concluida': 0, 'andamento': 0})
        item['total'] += 1
        status = r.get('status')
        if status == STATUS_CONCLUIDA:
            item['concluida'] += 1
        elif status != STATUS_CANCELADA:
            item['andamento'] += 1
    return sorted(agregados.values(), key=lambda item: (item[campo] or ''))


# ---------------------------------------------------------------- usuários

def buscar_usuario_por_username(username):
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('users').select('*').eq('username', username).limit(1).execute()
        return resp.data[0] if resp.data else None
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row


def listar_usuarios():
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('users').select('id,username,role').order('username').execute()
        return resp.data or []
    rows = conn.execute('SELECT id, username, role FROM users ORDER BY username').fetchall()
    conn.close()
    return rows


def usuario_existe(username):
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('users').select('id').eq('username', username).limit(1).execute()
        return bool(resp.data)
    row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row is not None


def criar_usuario(username, password_hash, role):
    conn = get_db()
    if _is_supabase():
        conn.from_('users').insert({
            'username': username, 'password_hash': password_hash, 'role': role,
        }).execute()
        return
    conn.execute(
        'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
        (username, password_hash, role),
    )
    conn.commit()
    conn.close()


def buscar_usuario(usuario_id):
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('users').select('id,username,role').eq('id', usuario_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    row = conn.execute('SELECT id, username, role FROM users WHERE id = ?', (usuario_id,)).fetchone()
    conn.close()
    return row


def buscar_username(usuario_id):
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('users').select('username').eq('id', usuario_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    row = conn.execute('SELECT username FROM users WHERE id = ?', (usuario_id,)).fetchone()
    conn.close()
    return row


def atualizar_usuario(usuario_id, role, password_hash=None):
    conn = get_db()
    if _is_supabase():
        payload = {'role': role}
        if password_hash:
            payload['password_hash'] = password_hash
        conn.from_('users').update(payload).eq('id', usuario_id).execute()
        return
    if password_hash:
        conn.execute('UPDATE users SET role = ?, password_hash = ? WHERE id = ?', (role, password_hash, usuario_id))
    else:
        conn.execute('UPDATE users SET role = ? WHERE id = ?', (role, usuario_id))
    conn.commit()
    conn.close()


def excluir_usuario(usuario_id):
    conn = get_db()
    if _is_supabase():
        conn.from_('users').delete().eq('id', usuario_id).execute()
        return
    conn.execute('DELETE FROM users WHERE id = ?', (usuario_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- ordens

def contar_ordens(responsavel=None, status_igual=None, status_excluidos=None):
    conn = get_db()
    if _is_supabase():
        q = conn.from_('ordens').select('id', count='exact')
        if responsavel:
            q = q.ilike('responsavel', responsavel)
        if status_igual:
            q = q.eq('status', status_igual)
        if status_excluidos:
            for status in status_excluidos:
                q = q.neq('status', status)
        resp = q.execute()
        return resp.count or 0

    query = 'SELECT COUNT(*) as total FROM ordens WHERE 1=1'
    params = []
    if responsavel:
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(responsavel)
    if status_igual:
        query += ' AND status = ?'
        params.append(status_igual)
    if status_excluidos:
        for status in status_excluidos:
            query += ' AND status != ?'
            params.append(status)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row['total']


def listar_ordens_recentes(responsavel=None, limite=5):
    conn = get_db()
    if _is_supabase():
        q = conn.from_('ordens').select('*')
        if responsavel:
            q = q.ilike('responsavel', responsavel)
        resp = q.order('created_at', desc=True).limit(limite).execute()
        return resp.data or []

    query = 'SELECT * FROM ordens WHERE 1=1'
    params = []
    if responsavel:
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(responsavel)
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limite)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def listar_ordens(responsavel=None, busca=None, status=None, prioridade=None,
                   responsavel_filtro=None, created_after=None):
    conn = get_db()
    if _is_supabase():
        q = conn.from_('ordens').select('*')
        if responsavel:
            q = q.ilike('responsavel', responsavel)
        if status:
            q = q.eq('status', status)
        if prioridade:
            q = q.eq('prioridade', prioridade)
        if responsavel_filtro:
            q = q.ilike('responsavel', responsavel_filtro)
        if created_after:
            q = q.gte('created_at', created_after)
        resp = q.order('created_at', desc=True).execute()
        rows = resp.data or []
        if busca:
            termo = busca.lower()
            rows = [
                r for r in rows
                if termo in str(r.get('titulo', '')).lower()
                or termo in str(r.get('descricao', '')).lower()
                or termo in str(r.get('cliente', '')).lower()
                or termo in str(r.get('responsavel', '')).lower()
            ]
        return rows

    query = 'SELECT * FROM ordens WHERE 1=1'
    params = []
    if responsavel:
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(responsavel)
    if busca:
        query += ' AND (titulo LIKE ? OR descricao LIKE ? OR cliente LIKE ? OR responsavel LIKE ?)'
        termo = f'%{busca}%'
        params.extend([termo, termo, termo, termo])
    if status:
        query += ' AND status = ?'
        params.append(status)
    if prioridade:
        query += ' AND prioridade = ?'
        params.append(prioridade)
    if responsavel_filtro:
        query += ' AND LOWER(responsavel) = LOWER(?)'
        params.append(responsavel_filtro)
    if created_after:
        query += ' AND created_at >= ?'
        params.append(created_after)
    query += ' ORDER BY created_at DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def resumo_por_responsavel():
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('ordens').select('responsavel,status').execute()
        return _agregar_por_campo(resp.data or [], 'responsavel')

    rows = conn.execute(
        "SELECT responsavel, COUNT(*) as total, "
        "SUM(CASE WHEN status = 'Concluída' THEN 1 ELSE 0 END) as concluida, "
        "SUM(CASE WHEN status != 'Concluída' AND status != 'Cancelada' THEN 1 ELSE 0 END) as andamento "
        "FROM ordens GROUP BY responsavel ORDER BY responsavel"
    ).fetchall()
    conn.close()
    return rows


def resumo_por_setor():
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('ordens').select('setor,status').execute()
        return _agregar_por_campo(resp.data or [], 'setor')

    rows = conn.execute(
        "SELECT setor, COUNT(*) as total, "
        "SUM(CASE WHEN status = 'Concluída' THEN 1 ELSE 0 END) as concluida, "
        "SUM(CASE WHEN status != 'Concluída' AND status != 'Cancelada' THEN 1 ELSE 0 END) as andamento "
        "FROM ordens GROUP BY setor ORDER BY setor"
    ).fetchall()
    conn.close()
    return rows


def listar_ordens_prioritarias(limite=5):
    conn = get_db()
    if _is_supabase():
        resp = (
            conn.from_('ordens')
            .select('*')
            .eq('prioridade', 'Alta')
            .neq('status', STATUS_CONCLUIDA)
            .neq('status', STATUS_CANCELADA)
            .order('created_at', desc=True)
            .limit(limite)
            .execute()
        )
        return resp.data or []

    rows = conn.execute(
        "SELECT * FROM ordens WHERE prioridade = 'Alta' AND status != 'Concluída' AND status != 'Cancelada' "
        "ORDER BY created_at DESC LIMIT ?",
        (limite,),
    ).fetchall()
    conn.close()
    return rows


def listar_ordens_atrasadas(limite=5):
    conn = get_db()
    if _is_supabase():
        resp = (
            conn.from_('ordens')
            .select('*')
            .in_('status', ['Em andamento', 'Aberta'])
            .order('created_at', desc=False)
            .limit(limite)
            .execute()
        )
        return resp.data or []

    rows = conn.execute(
        "SELECT * FROM ordens WHERE status = 'Em andamento' OR status = 'Aberta' "
        "ORDER BY created_at ASC LIMIT ?",
        (limite,),
    ).fetchall()
    conn.close()
    return rows


def criar_ordem(titulo, descricao, prioridade, setor, responsavel, status, cliente):
    conn = get_db()
    agora = _agora()
    if _is_supabase():
        resp = conn.from_('ordens').insert({
            'titulo': titulo, 'descricao': descricao, 'prioridade': prioridade,
            'setor': setor, 'responsavel': responsavel, 'status': status,
            'cliente': cliente, 'created_at': agora, 'updated_at': agora,
        }).execute()
        return resp.data[0]['id'] if resp.data else None

    cursor = conn.execute(
        'INSERT INTO ordens (titulo, descricao, prioridade, setor, responsavel, status, cliente, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (titulo, descricao, prioridade, setor, responsavel, status, cliente, agora, agora),
    )
    conn.commit()
    ordem_id = cursor.lastrowid
    conn.close()
    return ordem_id


def buscar_ordem(ordem_id):
    conn = get_db()
    if _is_supabase():
        resp = conn.from_('ordens').select('*').eq('id', ordem_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    row = conn.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,)).fetchone()
    conn.close()
    return row


def atualizar_ordem(ordem_id, titulo, descricao, prioridade, setor, responsavel, status, cliente):
    conn = get_db()
    agora = _agora()
    if _is_supabase():
        conn.from_('ordens').update({
            'titulo': titulo, 'descricao': descricao, 'prioridade': prioridade,
            'setor': setor, 'responsavel': responsavel, 'status': status,
            'cliente': cliente, 'updated_at': agora,
        }).eq('id', ordem_id).execute()
        return
    conn.execute(
        'UPDATE ordens SET titulo = ?, descricao = ?, prioridade = ?, setor = ?, responsavel = ?, status = ?, cliente = ?, updated_at = ? WHERE id = ?',
        (titulo, descricao, prioridade, setor, responsavel, status, cliente, agora, ordem_id),
    )
    conn.commit()
    conn.close()


def excluir_ordem(ordem_id):
    conn = get_db()
    if _is_supabase():
        conn.from_('ordens').delete().eq('id', ordem_id).execute()
        return
    conn.execute('DELETE FROM ordens WHERE id = ?', (ordem_id,))
    conn.commit()
    conn.close()


def listar_historico(ordem_id):
    conn = get_db()
    if _is_supabase():
        resp = (
            conn.from_('historico_ordens')
            .select('*')
            .eq('ordem_id', ordem_id)
            .order('created_at', desc=True)
            .execute()
        )
        return resp.data or []
    rows = conn.execute(
        'SELECT * FROM historico_ordens WHERE ordem_id = ? ORDER BY created_at DESC',
        (ordem_id,),
    ).fetchall()
    conn.close()
    return rows


def registrar_historico(ordem_id, usuario, acao, detalhes):
    conn = get_db()
    if _is_supabase():
        conn.from_('historico_ordens').insert({
            'ordem_id': ordem_id, 'usuario': usuario, 'acao': acao,
            'detalhes': detalhes, 'created_at': _agora(),
        }).execute()
        return
    conn.execute(
        'INSERT INTO historico_ordens (ordem_id, usuario, acao, detalhes, created_at) VALUES (?, ?, ?, ?, ?)',
        (ordem_id, usuario, acao, detalhes, _agora()),
    )
    conn.commit()
    conn.close()
