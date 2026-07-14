import os
import re
import tempfile
import unittest

from flask import Flask

import app as app_module


class AppTests(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        os.close(self.db_fd)
        app_module.app.config.update(
            TESTING=True, DATABASE=self.db_path, DB_BACKEND='sqlite',
            WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False,
        )
        # RATELIMIT_ENABLED so e lido por Flask-Limiter no momento do init_app()
        # (ja executado na importacao do app), entao precisa ser desligado aqui tambem.
        app_module.limiter.enabled = False
        with app_module.app.app_context():
            app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_login_and_create_order(self):
        response = self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Painel de Ordens', response.data)

        create_response = self.client.post(
            '/ordens/nova',
            data={
                'titulo': 'Troca de filtro',
                'descricao': 'Filtro da linha de produção precisa ser substituído.',
                'prioridade': 'Alta',
                'setor': 'Produção',
                'responsavel': 'Mateus',
                'status': 'Aberta',
                'cliente': 'Laticínios Vale Dourado',
            },
            follow_redirects=True,
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertIn(b'Troca de filtro', create_response.data)

    def test_employee_only_sees_assigned_orders(self):
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute(
                'INSERT INTO ordens (titulo, descricao, prioridade, setor, responsavel, status, cliente, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                ('Ordem do mateus', 'Descrição do mateus', 'Alta', 'Produção', 'mateus', 'Aberta', 'Cliente A', '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
            )
            conn.execute(
                'INSERT INTO ordens (titulo, descricao, prioridade, setor, responsavel, status, cliente, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                ('Ordem do joao', 'Descrição do joao', 'Média', 'Manutenção', 'joao', 'Aberta', 'Cliente B', '2024-01-02 00:00:00', '2024-01-02 00:00:00'),
            )
            conn.commit()
            conn.close()

        response = self.client.post(
            '/login',
            data={'username': 'mateus', 'password': '1234', 'modulo': 'funcionario'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Ordem do mateus', response.data)
        self.assertNotIn(b'Ordem do joao', response.data)

    def test_edit_order_records_detailed_history(self):
        with app_module.app.app_context():
            conn = app_module.get_db()
            cursor = conn.execute(
                'INSERT INTO ordens (titulo, descricao, prioridade, setor, responsavel, status, cliente, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                ('Ordem inicial', 'Descrição inicial', 'Alta', 'Produção', 'mateus', 'Aberta', 'Cliente X', '2024-01-01 00:00:00', '2024-01-01 00:00:00'),
            )
            ordem_id = cursor.lastrowid
            conn.commit()
            conn.close()

        self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin'},
            follow_redirects=True,
        )

        edit_response = self.client.post(
            f'/ordens/{ordem_id}/editar',
            data={
                'titulo': 'Ordem inicial',
                'descricao': 'Descrição inicial',
                'prioridade': 'Baixa',
                'setor': 'Produção',
                'responsavel': 'joao',
                'status': 'Concluída',
                'cliente': 'Cliente X',
            },
            follow_redirects=True,
        )
        self.assertEqual(edit_response.status_code, 200)

        with app_module.app.app_context():
            conn = app_module.get_db()
            historico = conn.execute(
                'SELECT detalhes FROM historico_ordens WHERE ordem_id = ? ORDER BY created_at DESC',
                (ordem_id,),
            ).fetchall()
            conn.close()

        detalhes_texto = '\n'.join(item['detalhes'] for item in historico)
        self.assertIn('Prioridade', detalhes_texto)
        self.assertIn('Baixa', detalhes_texto)
        self.assertIn('Responsável', detalhes_texto)

    def test_admin_can_create_new_employee(self):
        self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin'},
            follow_redirects=True,
        )

        response = self.client.post(
            '/usuarios/novo',
            data={
                'username': 'novo_funcionario',
                'password': 'senha123',
                'confirm_password': 'senha123',
                'role': 'funcionario',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)

        with app_module.app.app_context():
            conn = app_module.get_db()
            usuario = conn.execute(
                'SELECT * FROM users WHERE username = ?', ('novo_funcionario',)
            ).fetchone()
            conn.close()

        self.assertIsNotNone(usuario)
        self.assertEqual(usuario['role'], 'funcionario')

    def test_login_rate_limit_blocks_after_repeated_attempts(self):
        app_module.limiter.enabled = True
        try:
            for _ in range(5):
                response = self.client.post(
                    '/login',
                    data={'username': 'Deivisson', 'password': 'senha-errada', 'modulo': 'admin'},
                )
                self.assertNotEqual(response.status_code, 429)

            blocked_response = self.client.post(
                '/login',
                data={'username': 'Deivisson', 'password': 'senha-errada', 'modulo': 'admin'},
            )
            self.assertEqual(blocked_response.status_code, 429)
        finally:
            app_module.limiter.enabled = False

    def test_csrf_protection_blocks_missing_token(self):
        app_module.app.config.update(WTF_CSRF_ENABLED=True)

        response = self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin'},
        )
        self.assertEqual(response.status_code, 400)

    def test_csrf_protection_allows_valid_token(self):
        app_module.app.config.update(WTF_CSRF_ENABLED=True)

        login_page = self.client.get('/')
        match = re.search(rb'name="csrf_token" value="([^"]+)"', login_page.data)
        self.assertIsNotNone(match)
        token = match.group(1).decode('utf-8')

        response = self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin', 'csrf_token': token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Painel de Ordens', response.data)

    def test_secret_key_required_without_local_dotenv(self):
        original_secret_key = os.environ.pop('SECRET_KEY', None)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                fake_app = Flask('fake_app_for_test', root_path=tmp_dir)
                with self.assertRaises(RuntimeError):
                    app_module.load_environment_config(fake_app)
        finally:
            if original_secret_key is not None:
                os.environ['SECRET_KEY'] = original_secret_key

    def test_session_cookie_security_config(self):
        self.assertFalse(app_module.app.config['SESSION_COOKIE_SECURE'])
        self.assertEqual(app_module.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')
        self.assertTrue(app_module.app.config['SESSION_COOKIE_HTTPONLY'])

        original_secret_key = os.environ.pop('SECRET_KEY', None)
        try:
            os.environ['SECRET_KEY'] = 'chave-simulada-de-producao'
            with tempfile.TemporaryDirectory() as tmp_dir:
                fake_app = Flask('fake_app_for_test', root_path=tmp_dir)
                app_module.load_environment_config(fake_app)
                self.assertTrue(fake_app.config['SESSION_COOKIE_SECURE'])
        finally:
            os.environ.pop('SECRET_KEY', None)
            if original_secret_key is not None:
                os.environ['SECRET_KEY'] = original_secret_key

    def test_login_sets_permanent_session_cookie(self):
        response = self.client.post(
            '/login',
            data={'username': 'Deivisson', 'password': '4321', 'modulo': 'admin'},
        )
        set_cookie = response.headers.get('Set-Cookie', '')
        self.assertIn('HttpOnly', set_cookie)
        self.assertIn('SameSite=Lax', set_cookie)
        self.assertTrue('Expires' in set_cookie or 'Max-Age' in set_cookie)

    def test_environment_configuration_is_loaded(self):
        os.environ['DATABASE_PATH'] = self.db_path
        os.environ['SECRET_KEY'] = 'ambiente-teste'

        app_module.load_environment_config(app_module.app)

        self.assertEqual(app_module.app.config['DATABASE'], self.db_path)
        self.assertEqual(app_module.app.config['SECRET_KEY'], 'ambiente-teste')


if __name__ == '__main__':
    unittest.main()
