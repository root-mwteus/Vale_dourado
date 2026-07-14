from datetime import datetime, timedelta

from flask import redirect, render_template, request, session, url_for

from src.core import app
from src.db import get_db
from src.helpers import login_required, registrar_historico, registrar_historico_alteracao


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
