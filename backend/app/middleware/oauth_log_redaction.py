import logging


CALLBACK_PATH = "/integrations/google-drive/callback"


class OAuthCallbackAccessLogFilter(logging.Filter):
    """Redact OAuth callback query strings from standard Uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args
        if isinstance(arguments, tuple) and len(arguments) >= 3:
            request_path = arguments[2]
            if isinstance(request_path, str) and CALLBACK_PATH in request_path:
                sanitized = list(arguments)
                sanitized[2] = request_path.split("?", 1)[0] + "?<redacted>"
                record.args = tuple(sanitized)
        return True
