from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from src.core import app
from src import queries


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

    usuario = queries.buscar_usuario_por_username(usuario_digitado)

    if not usuario or not check_password_hash(usuario['password_hash'], senha_digitada):
        return render_template('login.html', mensagem_erro='Erro: Usuário ou Senha incorretos!')

    if usuario['role'] == 'funcionario' and modulo_selecionado != 'funcionario':
        return render_template('login.html', mensagem_erro="Erro: O usuário não tem acesso ao módulo Gestão!")

    if usuario['role'] == 'admin' and modulo_selecionado != 'admin':
        return render_template('login.html', mensagem_erro='Erro: Login administrativo')

    session['usuario'] = usuario['username']
    session['role'] = usuario['role']
    return redirect(url_for('dashboard'))


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('usuario', None)
    session.pop('role', None)
    return redirect(url_for('home'))
