# Stress Test Report

## normal
- net_profit: -2144.851788070417
- profit_factor: 0.8594724811442033
- max_drawdown_pct: 24.103996033769164
- total_trades: 916

## doubled_fees
- net_profit: -4047.5387363259424
- profit_factor: 0.712221563603954
- max_drawdown_pct: 41.419166728176364
- total_trades: 852

## slippage_2x
- net_profit: -2573.1962454768295
- profit_factor: 0.8203328828798577
- max_drawdown_pct: 27.23110866125032
- total_trades: 852

## slippage_3x
- net_profit: -2633.1794471039725
- profit_factor: 0.7987265203077198
- max_drawdown_pct: 27.86340206304876
- total_trades: 775

## delayed_entry_1
- net_profit: -2144.851788070417
- profit_factor: 0.8594724811442033
- max_drawdown_pct: 24.103996033769164
- total_trades: 916

## delayed_entry_2
- net_profit: -837.7826119370526
- profit_factor: 0.9599171491158847
- max_drawdown_pct: 21.222571375586146
- total_trades: 1095

## Parameter Tests
- supertrend_multiplier=2.8: net_profit=-2333.5166628852244, profit_factor=0.8449715995269758
- supertrend_multiplier=3.0: net_profit=-2144.851788070417, profit_factor=0.8594724811442033
- supertrend_multiplier=3.2: net_profit=-2160.297863909149, profit_factor=0.856949722436625
- stop_atr_mult=1.3: net_profit=-2325.2238751172004, profit_factor=0.7997810700751574
- stop_atr_mult=1.5: net_profit=-2144.851788070417, profit_factor=0.8594724811442033
- stop_atr_mult=1.7: net_profit=0.0, profit_factor=0.0
- ema_pair=8/21: net_profit=-2047.8366763641043, profit_factor=0.8671560947535201
- ema_pair=9/21: net_profit=-2144.851788070417, profit_factor=0.8594724811442033
- ema_pair=10/24: net_profit=-2293.5989942496003, profit_factor=0.8493783679269661