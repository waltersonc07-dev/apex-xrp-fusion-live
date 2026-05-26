from src.fundamental_gate import live_allowed, trade_mode


CONFIG = {
    "fundamental_gate": {
        "full_allowed_score": 26,
        "reduced_allowed_score": 22,
        "micro_only_score": 17,
        "block_below_score": 17,
    }
}


def test_score_modes():
    assert trade_mode(26, CONFIG) == "FULL_ALLOWED"
    assert trade_mode(22, CONFIG) == "REDUCED_ALLOWED"
    assert trade_mode(17, CONFIG) == "MICRO_ONLY"
    assert trade_mode(16, CONFIG) == "BLOCK_LIVE"


def test_live_allowed_rules():
    assert live_allowed(17, "MICRO_LIVE", CONFIG)
    assert not live_allowed(17, "FULL_LIVE", CONFIG)
    assert not live_allowed(16, "MICRO_LIVE", CONFIG)

