from flask import render_template, session

from src.core import app
from src import queries
from src.helpers import login_required


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    responsavel = session.get('usuario') if role == 'funcionario' else None

    total_ordens = queries.contar_ordens(responsavel=responsavel)
    abertas = queries.contar_ordens(
        responsavel=responsavel,
        status_excluidos=[queries.STATUS_CONCLUIDA, queries.STATUS_CANCELADA],
    )
    concluídas = queries.contar_ordens(responsavel=responsavel, status_igual=queries.STATUS_CONCLUIDA)
    recentes = queries.listar_ordens_recentes(responsavel=responsavel, limite=5)

    return render_template(
        'dashboard.html',
        total_ordens=total_ordens,
        abertas=abertas,
        concluídas=concluídas,
        recentes=recentes,
    )
