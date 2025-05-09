import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

METRICS_FILE = Path.home() / ".sens" / "metrics.json"


class MetricsStore:
    """Persistent store for system-wide CLI metrics."""

    _lock = Lock()

    def __init__(self, path: Optional[Path] = None):
        """Initialize the MetricsStore.

        Args:
            path: Optional custom path for metrics storage. If not provided,
                 defaults to ~/.sens/metrics.json
        """
        self.path = path or METRICS_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "created_at": datetime.utcnow().isoformat(),
                    "commands": {},
                    "errors": 0,
                    "last_updated": None,
                }
            )

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {}
            with self.path.open("r") as f:
                return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            with self.path.open("w") as f:
                json.dump(data, f, indent=2)

    def record_command(self, command: str) -> None:
        data = self._read()
        commands = data.setdefault("commands", {})
        commands[command] = commands.get(command, 0) + 1
        data["last_updated"] = datetime.utcnow().isoformat()
        self._write(data)

    def record_error(self) -> None:
        data = self._read()
        data["errors"] = data.get("errors", 0) + 1
        data["last_updated"] = datetime.utcnow().isoformat()
        self._write(data)

    def get_summary(self) -> Dict[str, Any]:
        data = self._read()
        return {
            "created_at": data.get("created_at"),
            "last_updated": data.get("last_updated"),
            "total_commands": sum(data.get("commands", {}).values()),
            "errors": data.get("errors", 0),
            "commands": data.get("commands", {}),
        }

    def get_details(self) -> Dict[str, Any]:
        return self._read()
