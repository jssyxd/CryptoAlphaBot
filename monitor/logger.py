import logging
from pathlib import Path
from config.config import config


def setup_logger(name: str = "cryptoalphabot", level=logging.INFO) -> logging.Logger:
    """Configure root logger with console + file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
