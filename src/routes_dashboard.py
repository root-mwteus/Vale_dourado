from flask import render_template, session

from src.core import app
from src.db import get_db
from src.helpers import login_required


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
