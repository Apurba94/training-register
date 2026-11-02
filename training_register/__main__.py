"""Start the app: python -m training_register [data.db] [--port 8038]"""
import sys

from .fieldkit import main_cli
from .web import create_app

sys.exit(main_cli(create_app, "training.db", 8038, sys.argv))
