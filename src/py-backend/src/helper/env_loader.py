import os
import sys
from dotenv import load_dotenv


def load_env():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    dotenv_path = os.path.join(base_path, '.env')

    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        print("WARNING: .env file not found at runtime")

