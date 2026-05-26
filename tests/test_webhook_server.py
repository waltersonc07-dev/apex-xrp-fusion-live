from src.webhook_server import validate_secret


def test_webhook_secret_validation(monkeypatch):
    monkeypatch.setenv("TRADINGVIEW_WEBHOOK_SECRET", "secret")
    config = {"execution": {"webhook_secret_env": "TRADINGVIEW_WEBHOOK_SECRET"}}
    assert validate_secret("secret", config)
    assert not validate_secret("bad", config)

