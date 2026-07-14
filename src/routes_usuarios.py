from flask import redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from src.core import app
from src import queries
from src.helpers import login_required


@app.route('/usuarios')
@login_required
def listar_usuarios():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    usuarios = queries.listar_usuarios()
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

        if queries.usuario_existe(username):
            return render_template('novo_usuario.html', mensagem_erro='Este nome de usuário já existe.')

        queries.criar_usuario(username, generate_password_hash(password), role)
        return redirect(url_for('listar_usuarios'))

    return render_template('novo_usuario.html')


@app.route('/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_usuario(usuario_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    usuario = queries.buscar_usuario(usuario_id)
    if not usuario:
        return redirect(url_for('listar_usuarios'))

    if request.method == 'POST':
        novo_role = request.form.get('role', '').strip()
        nova_senha = request.form.get('password', '')
        confirm_nova_senha = request.form.get('confirm_password', '')

        if novo_role not in {'funcionario', 'admin'}:
            return render_template('editar_usuario.html', usuario=usuario, mensagem_erro='Perfil inválido.')

        if nova_senha or confirm_nova_senha:
            if nova_senha != confirm_nova_senha:
                return render_template('editar_usuario.html', usuario=usuario, mensagem_erro='As senhas não coincidem.')
            queries.atualizar_usuario(usuario_id, novo_role, generate_password_hash(nova_senha))
        else:
            queries.atualizar_usuario(usuario_id, novo_role)

        return redirect(url_for('listar_usuarios'))

    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/usuarios/<int:usuario_id>/excluir', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    usuario = queries.buscar_username(usuario_id)
    if not usuario:
        return redirect(url_for('listar_usuarios'))

    if usuario['username'] == session.get('usuario'):
        return redirect(url_for('listar_usuarios'))

    queries.excluir_usuario(usuario_id)
    return redirect(url_for('listar_usuarios'))
