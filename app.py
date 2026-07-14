import os

from src.config import load_environment_config
from src.core import app, limiter
from src.db import get_db, init_db  # noqa: F401 (re-exportados para compatibilidade)

load_environment_config(app)
limiter.init_app(app)

with app.app_context():
    init_db()

import src.errors  # noqa: E402,F401
import src.routes_auth  # noqa: E402,F401
import src.routes_dashboard  # noqa: E402,F401
import src.routes_ordens  # noqa: E402,F401
import src.routes_usuarios  # noqa: E402,F401


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
