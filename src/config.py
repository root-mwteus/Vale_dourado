import os
from pathlib import Path


def load_environment_config(app):
    dotenv_path = Path(app.root_path) / '.env'
    if dotenv_path.exists():
        for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    secret_key = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
    app.config['SECRET_KEY'] = secret_key
    app.secret_key = secret_key

    supabase_url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
    database_path = os.environ.get('DATABASE_PATH') or os.environ.get('DATABASE')

    if supabase_url and supabase_key:
        app.config['DB_BACKEND'] = 'supabase'
        app.config['SUPABASE_URL'] = supabase_url
        app.config['SUPABASE_KEY'] = supabase_key
    elif database_path and database_path.startswith('https://'):
        app.config['DB_BACKEND'] = 'supabase'
        app.config['SUPABASE_URL'] = database_path
        app.config['SUPABASE_KEY'] = supabase_key or ''
    elif database_path:
        if database_path.startswith('sqlite:///'):
            resolved_path = database_path[len('sqlite:///'):]
        else:
            resolved_path = database_path

        if os.path.isabs(resolved_path):
            app.config['DATABASE'] = resolved_path
        else:
            app.config['DATABASE'] = os.path.abspath(os.path.join(app.root_path, resolved_path))
        app.config['DB_BACKEND'] = 'sqlite'
    else:
        app.config['DB_BACKEND'] = 'sqlite'
        app.config['DATABASE'] = os.path.join(app.root_path, 'orders.db')

    return app.config
