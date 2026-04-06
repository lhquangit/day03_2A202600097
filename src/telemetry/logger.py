import logging
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, TextIO


class _TeeStream:
    """Write console output to both terminal and a file."""

    def __init__(self, original_stream: TextIO, file_stream: TextIO):
        self.original_stream = original_stream
        self.file_stream = file_stream

    def write(self, data: str) -> int:
        self.original_stream.write(data)
        self.file_stream.write(data)
        return len(data)

    def flush(self) -> None:
        self.original_stream.flush()
        self.file_stream.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.original_stream, "isatty", lambda: False)())

class IndustryLogger:
    """
    Structured logger that simulates industry practices.
    Logs to both console and a file in JSON format.
    """
    def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.log_dir = log_dir
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        if not self.logger.handlers:
            # File Handler (JSON)
            log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
            file_handler = logging.FileHandler(log_file)
            
            # Console Handler
            console_handler = logging.StreamHandler()
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Logs an event with a timestamp and type."""
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            "data": data
        }
        self.logger.info(json.dumps(payload))

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str, exc_info=True):
        self.logger.error(msg, exc_info=exc_info)

    def create_run_log_path(self, prefix: str = "run", extension: str = "txt") -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return os.path.join(self.log_dir, f"{prefix}_{timestamp}.{extension}")

    def write_json_artifact(
        self,
        payload: Dict[str, Any],
        *,
        path: str | None = None,
        prefix: str = "artifact",
    ) -> str:
        target_path = path or self.create_run_log_path(prefix=prefix, extension="json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file_stream:
            json.dump(payload, file_stream, ensure_ascii=False, indent=2)
        return target_path

    def write_text_artifact(
        self,
        text: str,
        *,
        path: str | None = None,
        prefix: str = "artifact",
    ) -> str:
        target_path = path or self.create_run_log_path(prefix=prefix, extension="txt")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file_stream:
            file_stream.write(text)
        return target_path

    @contextmanager
    def capture_console(self, log_path: str | None = None) -> Iterator[str]:
        """
        Mirror stdout and stderr to a plain-text log file for a single run.
        """
        target_log_path = log_path or self.create_run_log_path()
        os.makedirs(os.path.dirname(target_log_path), exist_ok=True)

        original_stdout = sys.stdout
        original_stderr = sys.stderr
        with open(target_log_path, "a", encoding="utf-8") as file_stream:
            sys.stdout = _TeeStream(original_stdout, file_stream)
            sys.stderr = _TeeStream(original_stderr, file_stream)
            self.log_event("RUN_LOG_START", {"log_path": target_log_path})
            try:
                yield target_log_path
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                self.log_event("RUN_LOG_END", {"log_path": target_log_path})

# Global logger instance
logger = IndustryLogger()
