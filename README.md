# BTC AI Trader V1

نسخة بحث ومحاكاة (Paper Trading) لنظام BTCUSDT متعدد العقول.

## ما الذي تنفذه V1؟

- بيانات BTCUSDT حية من Binance public market-data endpoints، بدون API key.
- إعادة اتصال تلقائية + أكثر من endpoint رسمي احتياطي عند تعطل المصدر.
- 5 فريمات: `1m`, `5m`, `15m`, `1h`, `4h`.
- ثلاثة عقول مترابطة:
  - SCALP
  - INTRADAY
  - SWING
- Master Selector:
  - Safety Score
  - Profit Score
  - Expected Value (EV)
  - Risk/Reward
  - Consensus
  - Risk Gate
- صفقة واحدة فقط في أي لحظة.
- رأس مال افتراضي ابتدائي: `$1,000`.
- مخاطرة أولية: `0.75%` من رأس المال لكل صفقة.
- TP1 / TP2 / TP3.
- TP1 يغلق 30% وينقل SL إلى Break-even.
- TP2 يغلق 40% وينقل SL إلى TP1.
- TP3 يغلق الباقي.
- Early Exit عندما يظهر إجماع قوي من عقلين بعكس الصفقة المفتوحة.
- SQLite لتسجيل الصفقات والنتائج.
- واجهة عربية متجاوبة للهاتف والكمبيوتر.
- TradingView Lightweight Charts 5.2.1 لعرض الشموع والخطوط.

> **مهم:** هذه النسخة لا تتصل بحساب تداول ولا تنفذ أموالًا حقيقية.

---

## هيكل المشروع

```text
btc_ai_trader_v1/
├─ run.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ app/
│  ├─ config.py
│  ├─ db.py
│  ├─ indicators.py
│  ├─ market.py
│  ├─ brains.py
│  ├─ master.py
│  ├─ trade_manager.py
│  ├─ engine.py
│  ├─ main.py
│  └─ static/
│     ├─ index.html
│     ├─ app.js
│     └─ styles.css
└─ tests/
   └─ test_master.py
```

## التشغيل على Windows / macOS / Linux

### 1) ثبّت Python 3.11 أو أحدث

### 2) افتح Terminal داخل المجلد

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 3) ثبّت المكتبات

```bash
pip install -r requirements.txt
```

### 4) شغّل النظام

```bash
python run.py
```

ثم افتح:

```text
http://127.0.0.1:8000
```

ولفتحه من هاتف على نفس شبكة Wi‑Fi، استخدم IP الكمبيوتر مثل:

```text
http://192.168.1.10:8000
```

قد تحتاج السماح لـPython عبر Windows Firewall.

---

## منطق الاختيار

كل عقل يصنع Trade Proposal. ثم يقوم Master بما يلي:

1. حساب Safety Score.
2. حساب Profit Score.
3. التحقق من EV > 0.
4. التحقق من R:R.
5. التحقق من مسافة SL.
6. إدخال توافق العقول في التقييم.
7. استبعاد أي صفقة لا تجتاز Risk Gate.
8. اختيار أعلى Risk-adjusted opportunity.
9. فتح صفقة واحدة فقط.
10. قفل أي Entries جديدة حتى إغلاق الصفقة.

## إعدادات مهمة

يمكن تعديل القيم كـEnvironment Variables:

```text
PAPER_START_CAPITAL=1000
RISK_PER_TRADE=0.0075
PAPER_FEE_RATE=0.001
MIN_CONFIDENCE=65
MIN_SAFETY_SCORE=68
MIN_RR=1.5
MAX_STOP_PCT=2.5
```

## حدود V1

هذه النسخة الأولى **لا** تحتوي بعد على:

- ML/FreqAI training.
- Order Blocks / FVG الكامل.
- رسم Trendlines تفاعلية آلية.
- Backtester تاريخي مستقل.
- تنفيذ حقيقي في Exchange.
- أخبار / Sentiment / Order Book.

الهدف من V1 هو أولًا التأكد من أن:
`Market Data → 3 Brains → Master → One Trade → Trade Management → Journal`
تعمل كنظام واحد بثبات.

## الخطوة المقترحة لـ V1.1

- Backtesting لبيانات تاريخية.
- تسجيل MFE / MAE.
- مقارنة أداء SCALP / INTRADAY / SWING.
- تحسين أوزان Master من نتائج فعلية.
- إضافة FVG / BOS / CHoCH بشكل أعمق.
- إضافة Replay Mode سريع لاختبار آلاف الصفقات.
