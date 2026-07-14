from pathlib import Path

from flask import Flask

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

app = Flask(__name__, root_path=PROJECT_ROOT)
