from flask import render_template

from src.core import app


@app.errorhandler(404)
def pagina_nao_encontrada(erro):
    return render_template(
        'erro.html',
        titulo='Página não encontrada',
        mensagem='O endereço que você tentou acessar não existe ou foi movido.',
    ), 404


@app.errorhandler(500)
def erro_interno(erro):
    app.logger.exception('Erro interno não tratado')
    return render_template(
        'erro.html',
        titulo='Algo deu errado',
        mensagem='Ocorreu um erro inesperado. Tente novamente em instantes.',
    ), 500


@app.errorhandler(429)
def limite_de_tentativas(erro):
    return render_template(
        'erro.html',
        titulo='Muitas tentativas',
        mensagem='Você tentou entrar várias vezes seguidas. Aguarde um minuto e tente novamente.',
    ), 429
