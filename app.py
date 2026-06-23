from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)

app.secret_key = 'deivinhonovais'

# Rota pra carregar o HTML
@app.route('/')
def home():
        if 'usuario' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

# Nova rota para verificar o dados digitados no form
@app.route('/login', methods = ['POST'])
def login(): 
    # Pegando o que foi digitado e colocando em uma variável
    usuario_digitado = request.form.get('username')
    senha_digitada = request.form.get('password')

    if usuario_digitado == "mateus" and senha_digitada == "1234" or usuario_digitado == 'Deivisson' and senha_digitada == "4321"  :
        # O usuario é guardado na sessão
        session['usuario'] = usuario_digitado
        return redirect(url_for('dashboard'))

    else: 
        return render_template('login.html', mensagem_erro="Erro: Usuário ou Senha incorretos!")

# Rota para o DASHBOARD
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return "Acesso Negado! Você precisa fazer login primeiro!"
     
    # Se usuario logado:
    usuario_logado = session['usuario']
    return render_template('dashboard.html')

# Rota de logout
@app.route('/logout', methods=['post'])
def logout():
    session.pop('usuario', None) # Apaga o usuario da dessão
    return redirect(url_for('home'))
if __name__ == '__main__':
        app.run(debug=True)