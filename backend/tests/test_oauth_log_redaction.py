import logging

from app.middleware.oauth_log_redaction import OAuthCallbackAccessLogFilter


def test_oauth_callback_access_log_redacts_query_string() -> None:
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1", "GET", "/api/v1/integrations/google-drive/callback?code=secret-code&state=secret-state", "1.1", 302),
        None,
    )

    assert OAuthCallbackAccessLogFilter().filter(record)
    rendered = record.getMessage()
    assert "secret-code" not in rendered
    assert "secret-state" not in rendered
    assert "?<redacted>" in rendered


def test_oauth_filter_leaves_other_access_logs_unchanged() -> None:
    path = "/api/v1/public/albums/test"
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "%s", (path,), None)
    OAuthCallbackAccessLogFilter().filter(record)
    assert record.args == (path,)
