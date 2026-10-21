# BTC Analyzer V1

محلل BTC متعدد الفريمات — تحليل وإشارات ومحاكاة فقط.

## الوظائف
- بيانات عامة من Binance Spot/Futures بدون API Key.
- فريمات من 1Y إلى 1m، بما فيها 12D و2W و3M و6M.
- Market Structure + BOS.
- Wave Engine: Direction / Impulse-Correction / Wave State.
- Trend + Momentum + Volume + Volatility.
- Timeframe hierarchy.
- Independent confirmation families.
- Veto Engine.
- LONG / SHORT / WAIT.
- Paper Tracker برصيد افتراضي.
- Dashboard عربي للهاتف والكمبيوتر.

## تشغيل
pip install -r requirements.txt
python app.py

## Render
Web Service عبر Dockerfile
Health path: /health

V1 Research/Paper only. لا توجد أوامر تداول حقيقية أو مفاتيح Binance.
