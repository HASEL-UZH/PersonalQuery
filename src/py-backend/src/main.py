import signal
import logging
import asyncio
import sys

from uvicorn import Config, Server
from server_rest import app

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logging.debug("Starting main script import...")

server = None


def handle_exit(signum, frame):
    logging.info(f"Received exit signal ({signum})")
    if server:
        # Graceful shutdown
        server.should_exit = True
    loop = asyncio.get_event_loop()
    loop.stop()


async def main():
    global server
    config = Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        loop="asyncio",
        lifespan="on",
        log_level="info",
    )
    server = Server(config)

    # Start server. This coroutine completes when server.should_exit becomes True
    await server.serve()

    logging.info("Server shutdown complete. Exiting process.")
    sys.exit(0)


if __name__ == "__main__":
    # Register signals
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    logging.info("Uvicorn starting...")
    # Run asyncio event loop
    asyncio.run(main())
