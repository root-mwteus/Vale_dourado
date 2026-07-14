from datetime import datetime

from flask import redirect, session, url_for

from db import get_db


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
