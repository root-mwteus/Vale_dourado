from pathlib import Path

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

app = Flask(__name__, root_path=PROJECT_ROOT)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address)
