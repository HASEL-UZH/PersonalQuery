import os
import sys
from dotenv import load_dotenv


def load_env():
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

    required_vars = [
        "OPENAI_API_KEY",
        "MY_OPENAI_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_PROJECT",
        "LANGSMITH_TRACING"
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
