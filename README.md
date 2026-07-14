# Vale Dourado — Sistema de Ordens de Serviço

Projeto de portfólio: um sistema web para digitalizar o controle de ordens de serviço de uma empresa de laticínios, substituindo um processo hoje feito em papel.

> **Nota:** este é um projeto pessoal de portfólio, sem nenhum vínculo real com uma empresa chamada "Vale Dourado". A ideia nasceu de um problema real descrito por um amigo que trabalha numa empresa de laticínios — a desorganização e a dependência de papel no controle de ordens de serviço — mas o sistema, os dados e a "empresa" aqui são fictícios.

## Funcionalidades

- Login com dois papéis: **administrador** (gestão completa) e **funcionário** (só enxerga e edita as próprias ordens)
- Cadastro, edição, listagem e exclusão de ordens de serviço, com histórico de alterações
- Filtros combináveis (status, prioridade, responsável, período, busca por texto)
- Dashboard com contadores e um resumo agregado por responsável/setor (visão do administrador)
- Cadastro e gestão de usuários (administrador)

## Stack

- **Backend:** Python 3.12 + Flask
- **Banco de dados:** Supabase (Postgres) em produção, com fallback automático para SQLite em desenvolvimento local
- **Segurança:** CSRF (Flask-WTF), rate limiting no login (Flask-Limiter), senhas com hash (Werkzeug/scrypt), Row Level Security no Supabase
- **Deploy:** Vercel (função Python serverless)
- **Testes:** `unittest`, suite isolada rodando contra SQLite

## Arquitetura

```
app.py              # ponto de entrada — bootstrap (carrega config, inicializa banco, registra rotas)
src/
  core.py            # instância do Flask, CSRFProtect, Limiter
  config.py          # carregamento de .env / variáveis de ambiente
  db.py              # conexão com o banco (sqlite3 ou cliente Supabase)
  queries.py         # uma função por operação de dado, tratando sqlite e supabase explicitamente
  helpers.py         # login_required, registro de histórico de alterações
  errors.py          # páginas de erro (404, 429, 500)
  routes_auth.py      # login / logout
  routes_dashboard.py # dashboard
  routes_ordens.py    # CRUD de ordens de serviço
  routes_usuarios.py  # CRUD de usuários
templates/           # HTML (Jinja2 + Bootstrap)
static/              # CSS e imagens
tests/               # suite de testes automatizados
```

## Como rodar localmente

```bash
git clone <este-repositorio>
cd Vale_dourado
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edite o `.env` com seus próprios valores (veja a seção abaixo) e rode:

```bash
python app.py
```

A aplicação sobe em `http://localhost:5000`. Sem nenhuma variável de banco configurada, ela usa SQLite automaticamente (`orders.db`, criado na primeira execução) e já vem com dois usuários de teste: `mateus` / `1234` (funcionário) e `Deivisson` / `4321` (administrador).

## Variáveis de ambiente

Veja `.env.example` para a lista completa e comentada. As mais importantes:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | Fora do ambiente local, sim | Assina sessão e tokens CSRF. Sem `.env` local e sem essa variável, a aplicação recusa iniciar. |
| `SUPABASE_URL` / `SUPABASE_KEY` | Não | Se definidas, o app usa Supabase como banco. Se ausentes, cai para SQLite local. |
| `RATELIMIT_STORAGE_URI` | Não | String de conexão Redis (ex: Upstash) para o limite de tentativas de login funcionar de forma confiável em produção serverless. Sem essa variável, usa memória local (funciona bem em dev, best-effort em produção). |
| `FLASK_DEBUG` | Não | `1` liga o modo debug ao rodar `python app.py` localmente. Não tem efeito no deploy via Vercel. |

## Testes

```bash
python -m unittest tests.test_app -v
```

A suite roda inteiramente contra SQLite (isolada do backend real), cobrindo autenticação, controle de acesso por papel, CRUD de ordens, CSRF, rate limiting e configuração de sessão.

## Deploy

O projeto está configurado para deploy na [Vercel](https://vercel.com) (`vercel.json`), usando Supabase como banco de produção. Nesse cenário, configure `SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY` e (opcionalmente) `RATELIMIT_STORAGE_URI` como variáveis de ambiente no painel do projeto.
