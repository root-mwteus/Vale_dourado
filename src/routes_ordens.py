from datetime import datetime, timedelta

from flask import redirect, render_template, request, session, url_for

from src.core import app
from src import queries
from src.helpers import login_required, registrar_historico_alteracao


@app.route('/ordens')
@login_required
def ordens():
    busca = request.args.get('busca', '').strip()
    status_filtro = request.args.get('status', '')
    prioridade_filtro = request.args.get('prioridade', '')
    responsavel_filtro = request.args.get('responsavel', '')
    periodo_filtro = request.args.get('periodo', '')

    role = session.get('role')
    responsavel_sessao = session.get('usuario') if role == 'funcionario' else None

    limite_periodo = None
    if periodo_filtro:
        hoje = datetime.now()
        if periodo_filtro == '7dias':
            limite_periodo = (hoje - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        elif periodo_filtro == '30dias':
            limite_periodo = (hoje - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        elif periodo_filtro == '90dias':
            limite_periodo = (hoje - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')

    lista = queries.listar_ordens(
        responsavel=responsavel_sessao,
        busca=busca or None,
        status=status_filtro or None,
        prioridade=prioridade_filtro or None,
        responsavel_filtro=responsavel_filtro or None,
        created_after=limite_periodo,
    )

    if role == 'admin':
        resumo_por_responsavel = queries.resumo_por_responsavel()
        resumo_por_setor = queries.resumo_por_setor()
        ordens_prioritarias = queries.listar_ordens_prioritarias(limite=5)
        ordens_atrasadas = queries.listar_ordens_atrasadas(limite=5)
    else:
        resumo_por_responsavel = []
        resumo_por_setor = []
        ordens_prioritarias = []
        ordens_atrasadas = []

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

        ordem_id = queries.criar_ordem(titulo, descricao, prioridade, setor, responsavel, status, cliente)
        queries.registrar_historico(ordem_id, session.get('usuario', 'Sistema'), 'Criada', f"Ordem criada com status {status}.")
        return redirect(url_for('ordens'))

    return render_template('nova_ordem.html')


@app.route('/ordens/<int:ordem_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_ordem(ordem_id):
    ordem = queries.buscar_ordem(ordem_id)

    if not ordem:
        return redirect(url_for('ordens'))

    if session.get('role') == 'funcionario' and str(ordem['responsavel']).lower() != str(session.get('usuario', '')).lower():
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
            return render_template('nova_ordem.html', ordem=ordem, mensagem_erro='Preencha todos os campos para atualizar a ordem.')

        dados_novos = {
            'titulo': titulo,
            'descricao': descricao,
            'prioridade': prioridade,
            'setor': setor,
            'responsavel': responsavel,
            'status': status,
            'cliente': cliente,
        }
        queries.atualizar_ordem(ordem_id, titulo, descricao, prioridade, setor, responsavel, status, cliente)
        registrar_historico_alteracao(ordem_id, session.get('usuario', 'Sistema'), dict(ordem), dados_novos)
        return redirect(url_for('ordens'))

    return render_template('nova_ordem.html', ordem=ordem)


@app.route('/ordens/<int:ordem_id>')
@login_required
def detalhe_ordem(ordem_id):
    ordem = queries.buscar_ordem(ordem_id)

    if not ordem:
        return redirect(url_for('ordens'))

    historico = queries.listar_historico(ordem_id)
    return render_template('detalhe_ordem.html', ordem=ordem, historico=historico)


@app.route('/ordens/<int:ordem_id>/excluir', methods=['POST'])
@login_required
def excluir_ordem(ordem_id):
    ordem = queries.buscar_ordem(ordem_id)
    if session.get('role') == 'funcionario' and str(ordem['responsavel']).lower() != str(session.get('usuario', '')).lower():
        return redirect(url_for('ordens'))

    queries.excluir_ordem(ordem_id)
    return redirect(url_for('ordens'))
