import sys
from loguru import logger

# diagnose=False: loguru's default prints the value of every local variable in
# a traceback. In a medical app those values can include document text, so
# tracebacks show code and line numbers only.


def setup_logger():
    logger.remove()

    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=False,
    )

    logger.add(
        "logs/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        backtrace=True,
        diagnose=False,
    )

    return logger