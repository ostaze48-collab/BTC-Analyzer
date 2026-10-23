# BTC AI Trader V1.17

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward طويلة بما يكفي.

## ما تعمل عليه المنظومة الآن

- قراءة متعددة الفريمات من `1m` حتى `1Y` عبر 18 فريمًا.
- مؤشرات واتجاه وزخم وحجم وتقلب وVWAP وEMA/RSI/MACD/ATR ومئات Background Features.
- Support/Resistance، Swing High/Low، BOS، CHoCH، FVG، Order Blocks، Liquidity Sweeps، Trend Channels.
- Candlestick + Classical Patterns كعوامل تأكيد لا كإشارات منفردة.
- Cycle/Valuation Context: Power Law، HPR/Rainbow، Mayer، Pi Cycle، 4-Year SMA.
- Network Intelligence وDerivatives Intelligence في وضع `SHADOW_ONLY` حتى تثبت فائدتها خارج العينة.
- Feature Edge Lab: فصل زمني Train/Test لقياس فائدة الخصائص.
- Incremental Edge Walk-Forward: مقارنة Baseline مقابل Baseline+Feature filter عبر نوافذ لاحقة.
- Historical Setup Memory: يقارن الصفقة المرشحة بحالات شارت سابقة مشابهة ويقيس ما حدث بعدها بـR multiples وقاعدة STOP_FIRST المحافظة.
- Analog Edge Validation: تختبر هل بيانات السوابق نفسها تضيف Edge خارج العينة بدل اعتبار التشابه التاريخي دليلًا كافيًا بحد ذاته.
- **Long Historical Replay Memory**: توسع ذاكرة السوابق حسب العقل المرشح في الخلفية بدل الاكتفاء بـ500 شمعة حديثة.
- Learning Journal: يحفظ Features عند الدخول والخروج، MFE/MAE، Regime، العقل، والنتيجة.
- Replay/Backtesting لنفس منطق العقول وإدارة المخاطر.

## الذاكرة التاريخية الطويلة V1.17

لا تقوم المنظومة بتحميل سنوات من كل فريم عند الإقلاع. التحميل **Lazy** ويبدأ فقط عندما يظهر عقل مرشح:

- `SCALP`: تاريخ أعمق لـ5m و15m و1H و4H و1D، مع هدف يصل إلى نحو 45 يومًا على 5m وأربع سنوات على اليومي.
- `INTRADAY`: يمتد من 15m حتى 1W، مع أشهر للفريمات الصغيرة وسنوات للفريمات الكبيرة.
- `SWING`: يركز على 4H و1D و1W و1M، ويستهدف عدة سنوات من التاريخ حيث يتوفر.

الأرشيف:

- يُحمّل في الخلفية ولا يوقف تحليل السوق الحي.
- يُخزن في ذاكرة الخادم مؤقتًا مع TTL، ثم يُعاد تحميله عند الحاجة.
- يُدمج مع الشموع الحية بدون تكرار timestamps، وتُفضّل الشمعة الحالية عند التعارض.
- يوسع عينة Historical Analog فقط، ووزنه في MASTER يظل `0`.
- إذا فشل مصدر أو فريم، يستمر النظام بالحالة `PARTIAL` بدل تعطيل التداول التجريبي.

## إدارة الصفقة والمخاطرة

- رأس المال التجريبي الابتدائي: `$1,000`.
- صفقة واحدة فقط في أي لحظة.
- النظام يحدد `LONG/SHORT` وحجم المركز والرافعة Paper تلقائيًا.
- الرافعة الافتراضية القصوى في Paper: `5x`.
- المخاطرة عند Stop ديناميكية وبحد أقصى افتراضي يقارب `1.4%` للصفقة الأقوى، مع خفضها عند Drawdown.
- أهداف ديناميكية من `1R` حتى `5R` حسب قوة الفرصة والعقل وحالة السوق.
- توقف وقائي عن فتح صفقات جديدة قبل حد الخسارة الكلي.
- الحد الصلب للنموذج التجريبي: `25%` من رأس المال الابتدائي، مع التنبيه أن الانزلاق/gaps في السوق الحقيقي قد يتجاوز أي حد برمجي.

## طبقات التحقق

لا يتم اعتبار أي Feature أو مصدر جديد مفيدًا لمجرد أنه يبدو جيدًا تاريخيًا:

1. Feature Pool واسع.
2. Chronological Edge Lab.
3. Incremental Walk-Forward.
4. Shadow Trial بوزن صفر.
5. Full-engine OOS replay.
6. Paper/Shadow performance.
7. Readiness Gate.
8. فقط بعد ذلك يمكن بحث الانتقال الحقيقي يدويًا.

Historical Analog وLong Historical Memory وNetwork وDerivatives لا يغيرون MASTER حاليًا (`weight = 0`). حتى إذا ظهرت Historical Analog كمرشح مفيد في Walk-Forward، تبقى بوزن صفر إلى أن تجتاز Full-engine OOS replay لاحقًا.

## كيف تُقرأ الصفقة على الشارت السابق

عندما توجد صفقة مرشحة، Historical Setup Memory تبحث عن حالات سابقة مشابهة من حيث اتجاه الفريمات، Regime، الاتجاه والبنية، RSI، EMA/VWAP distance، الحجم، التقلب، وطبقات Micro/Intraday/Swing/Macro. ثم تتابع ما حدث بعد كل حالة سابقة وتعرض:

- عدد الحالات المشابهة.
- متوسط التشابه.
- نسبة ضرب Stop قبل 1R.
- متوسط MFE/MAE بوحدة R.
- نسبة وصول الحالات إلى 1R و2R و3R و4R و5R.
- أمثلة زمنية من الحالات السابقة.

V1.16 تختبر هل هذه المعلومات مفيدة فعلاً عبر Edge Lab وIncremental Walk-Forward، وV1.17 توسع عمق التاريخ الذي تُبنى عليه هذه المقارنات.

## واجهة الهاتف

الواجهة Phone-First وتعرض:

- قرار MASTER والعقول الثلاثة.
- جميع الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- الصفقة النشطة وحجمها والرافعة والمخاطرة والأهداف.
- Market Regime وCycle Models.
- Network/Derivatives Shadow data.
- Feature Edge Lab وIncremental Walk-Forward.
- Historical Setup Memory ونتائج الحالات السابقة المشابهة.
- Analog Edge Validation: هل السوابق أثبتت قيمة إضافية أم لا.
- Long Historical Replay Memory: حالة التحميل وعمق كل فريم وعدد الشموع لكل عقل.
- Backtest وLearning Journal وسجل الصفقات.

## التشغيل محليًا

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

ثم:

```bash
pip install -r requirements.txt
python run.py
```

وافتح:

```text
http://127.0.0.1:8000
```

## CI والنشر

GitHub Actions يتحقق من:

- Python compile.
- Syntax لكل ملفات JavaScript الحالية حتى `v27.js`.
- Unit Tests.
- تشغيل التطبيق و`/health`.
- مزامنة رقم الإصدار وواجهات الهاتف مع ملفات التطوير الحديثة.

خدمة Render المرتبطة بفرع `main` تنشر تلقائيًا بعد نجاح checks حسب إعداد الخدمة.

## Environment Variables الأساسية

```text
BTC_SYMBOL=BTCUSDT
PAPER_START_CAPITAL=1000
PAPER_FEE_RATE=0.001
MIN_CONFIDENCE=65
MIN_SAFETY_SCORE=68
MIN_RR=1.5
MAX_STOP_PCT=2.5
MAX_PAPER_LEVERAGE=5
MAX_RISK_PER_TRADE=0.014
MAX_TOTAL_DRAWDOWN=0.25
SOFT_PAUSE_DRAWDOWN=0.23
```

## مبدأ المشروع

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → One Trade → Long Historical Evidence → Analog Validation → Journal → Walk-Forward Learning → Readiness Gate`

الهدف ليس زيادة عدد المؤشرات، بل استخدام Pool واسع ثم الاحتفاظ فقط بما يثبت Edge إضافيًا ومستقرًا خارج العينة.
