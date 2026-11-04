########################################
# LOGGING UTILITIES
########################################

#---------------------------------------
# Import dependencies
#---------------------------------------

# Python Standard Library
import os
import sys
import logging
import shutil

import datetime as dt
from pathlib import Path

#---------------------------------------
# CUSTOM LEVELS
#---------------------------------------

# Define new levels in a dictionary
CUSTOM_LEVELS = {
    "DUPE": 34,
    "MIA": 35
}

# Register the level names globally
for level_name, level_num in CUSTOM_LEVELS.items():
    logging.addLevelName(level_num, level_name)

#---------------------------------------
# TIMESTAMP
#---------------------------------------


def ts(zone: str = None):
    if zone == "utc":
        timestamp = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None
                                                            ).isoformat() + 'Z'
    else:
        timestamp = dt.datetime.now().astimezone().isoformat()

    return timestamp


#---------------------------------------
# FORMATTING
#---------------------------------------


class ap_fmt(logging.Formatter):

    def __init__(self, zone: str = None):
        log_layout = "%(asctime)s | %(levelname)s | %(system)s | %(message)s"
        super().__init__(fmt=log_layout)
        self.zone = zone

    def formatTime(self, record, datefmt=None):
        return ts(self.zone)

    def format(self, record):
        # Fallback default changed to "SCRIPT" for external third-party logs
        if not hasattr(record, "system"):
            record.system = "SCRIPT"

        # 1. Dynamically calculate the prefix layout length for THIS specific log line
        asctime = self.formatTime(record)
        levelname = record.levelname
        system = record.system
        prefix_length = len(f"{asctime} | {levelname} | {system} | ")

        # 2. Automatically replace '\t' with the exact number of matching alignment spaces
        if isinstance(record.msg, str) and "\t" in record.msg:
            padding = " " * prefix_length
            record.msg = record.msg.replace("\t", padding)

        return super().format(record)


#---------------------------------------
# GET LOGGER (DEFINE LOGGER)
#---------------------------------------


def get_logger(filepath: str = None, zone: str = None, level: str = "INFO"):
    if isinstance(level, str):
        level_upper = level.upper()
        if level_upper in CUSTOM_LEVELS:
            numeric_level = CUSTOM_LEVELS[level_upper]
        else:
            numeric_level = getattr(logging, level_upper, logging.INFO)
    else:
        numeric_level = level

    if os.name == 'nt':
        current_time = dt.datetime.now().replace(microsecond=0
                                                ).isoformat().replace(":", ".")
    else:
        # This runs on Mac/Linux (removes microseconds, uses raw colons)
        current_time = dt.datetime.now().replace(microsecond=0).isoformat()

    if not filepath:
        if sys.argv and sys.argv[0]:
            script_name = Path(sys.argv[0]).stem
        else:
            script_name = "ipython_session"

        # Default to a structured logs directory
        filepath = f"logs/{script_name}"

    log_name = f"{filepath}_{current_time}.log"

    # Grab the logger instance
    logger_instance = logging.getLogger("ap_logger")
    logger_instance.setLevel(numeric_level)

    # Baseline default state tracker
    logger_instance.current_system = "SCRIPT"

    # Attach custom levels with auto-injecting system context
    for level_name, level_num in CUSTOM_LEVELS.items():

        def make_log_func(log_obj, num):
            return lambda message, *args, **kws: (
                log_obj._log(
                    num, message, args, extra={
                        "system": log_obj.current_system
                    }, **kws
                ) if log_obj.isEnabledFor(num) else None
            )

        setattr(
            logger_instance,
            level_name.lower(),
            make_log_func(logger_instance, level_num)
        )

    # Intercept standard log functions to automatically inject system context
    orig_log = logger_instance._log

    def custom_log(
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1
    ):
        if extra is None:
            extra = {}
        if "system" not in extra:
            extra["system"] = logger_instance.current_system
        orig_log(level, msg, args, exc_info, extra, stack_info, stacklevel)

    # Apply the interceptor override
    logger_instance._log = custom_log

    # Handle folder creation
    dirname = os.path.dirname(log_name)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    # Setup file handlers safely
    if not logger_instance.handlers:
        file_handler = logging.FileHandler(log_name)
        file_handler.setFormatter(ap_fmt(zone=zone))
        logger_instance.addHandler(file_handler)

        # Handle symbolic link creation for latest.log
        try:
            base_dir = Path(dirname) if dirname else Path(".")
            latest_link = base_dir / "latest.log"
            actual_file = Path(log_name)

            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()

            if os.name == 'nt':
                try:
                    latest_link.symlink_to(actual_file.name)
                except OSError:
                    shutil.copy(log_name, latest_link)
            else:
                latest_link.symlink_to(actual_file.name)
        except Exception as e:
            print(
                f"Warning: Could not create latest.log link: {e}",
                file=sys.stderr
            )

    setup_exception_logging(logger_instance)

    return logger_instance


#---------------------------------------
# GLOBAL EXCEPTION HOOK HANDLER
#---------------------------------------


def setup_exception_logging(logger_instance):

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger_instance.critical(
            "System: CRITICAL UNCAUGHT EXCEPTION",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception
