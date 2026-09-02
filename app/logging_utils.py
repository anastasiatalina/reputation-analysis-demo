import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get a module logger with a simple, consistent configuration.
    """
    logger = logging.getLogger(name)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    return logger

