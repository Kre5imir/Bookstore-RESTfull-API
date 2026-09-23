import json
import logging
from datetime import datetime, timezone

_STRUCTURED_FIELDS = (
    "request_id",
    "method",
    "path",
    "route",
    "status",
    "duration_ms",
    "remote_addr",
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line so log shippers can index request fields."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
