# BTC AI Trader V1.18

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward طويلة بما يكفي.

## المكونات الحالية

- 18 فريمًا من `1m` حتى `1Y`.
- مؤشرات فنية + Market Structure + Liquidity + Patterns + مئات Background Features.
- Cycle/Valuation Models.
- Network وDerivatives في `SHADOW_ONLY`.
- Feature Edge Lab + Incremental Walk-Forward.
- Historical Setup Memory + Analog Edge Validation.
- Long Historical Replay Memory حسب العقل.
- **Historical Signature Cache V1.18** لتسريع مقارنة مئات السوابق التاريخية.
- Adaptive paper risk/leverage، صفقة واحدة فقط، وحد حماية رأسمال تجريبي.
- Learning Journal + Backtesting + Readiness Gate.

## Historical Signature Cache V1.18

بدل إعادة حساب كل المؤشرات عند كل نقطة تاريخية مع كل تحديث، تبني المنظومة بصمات سوق مضغوطة في الخلفية:

- الهدف حتى نحو `720` حالة تاريخية موزعة على كامل الذاكرة المتاحة.
- لا يبدأ Cache العميق قبل توفر `700` شمعة على الأقل في فريم العقل، حتى لا يعاد بناؤه على نافذة 500 شمعة متحركة.
- Revision الأرشيف مستقرة: تعتمد على يوم/حجم تاريخي تقريبي بدل التغير مع كل شمعة دقيقة.
- أثناء بناء Cache يستخدم النظام fallback أصغر (~180 حالة) ولا يتوقف التحليل الحي.
- بعد اكتمال Cache تتم مقارنة الصفقة الحالية بكل البصمات بسرعة، ثم يُقيّم المسار التفصيلي فقط لأقرب الحالات.
- لا تُنشأ بصمة قرب نهاية التاريخ ما لم توجد بعدها Future Window كاملة؛ لمنع Lookahead.
- قاعدة تقييم المسار تبقى `STOP_FIRST_CONSERVATIVE`.
- Signature Cache وHistorical Analog يظلان `SHADOW_ONLY` ووزنهما في MASTER = `0` حتى اجتياز تحقق OOS إضافي.

## الذاكرة التاريخية الطويلة

- `SCALP`: تاريخ أعمق للفريمات الصغيرة والمتوسطة.
- `INTRADAY`: أشهر/سنوات حسب الفريم.
- `SWING`: عدة سنوات على 4H/1D/1W/1M حيث يتوفر.
- التحميل Lazy في الخلفية ولا يوقف startup.
- الفشل الجزئي لا يوقف النظام.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- LONG/SHORT وحجم المركز والرافعة Paper تُحدد تلقائيًا.
- الرافعة الافتراضية القصوى: `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%` للفرص الأقوى.
- أهداف من `1R` حتى `5R`.
- توقف وقائي قبل حد الخسارة الكلي.
- حد النموذج التجريبي الكلي `25%`، وليس ضمانًا للسوق الحقيقي بسبب gaps/slippage.

## كيف نقرر أن البيانات السابقة مفيدة؟

1. Historical Analog يعرض التشابه والنتائج السابقة.
2. Analog metrics تدخل Edge Lab كـShadow Features.
3. Chronological Train/Test يمنع خلط الماضي بالمستقبل.
4. Incremental Walk-Forward يقارن Baseline مقابل Baseline+Feature.
5. حتى عند ظهور Edge يبقى الوزن صفرًا إلى Full-engine OOS replay.
6. ثم Paper/Shadow performance وReadiness Gate.

## واجهة الهاتف

الواجهة Phone-First وتعرض كل طبقات المنظومة، ومنها:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk/Leverage/Targets.
- Cycle/Network/Derivatives.
- Feature Edge وIncremental Walk-Forward.
- Historical Setup Memory وAnalog Validation.
- Long Historical Memory.
- Signature Cache: حالته، عدد البصمات، وقت البناء، وهل يتم استخدام Cache أو Fallback.

## التشغيل

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

افتح:

```text
http://127.0.0.1:8000
```

## CI

يفحص GitHub Actions:

- Python compile.
- JavaScript syntax حتى `v28.js`.
- Unit tests، بما فيها No-lookahead وcache revision stability.
- تشغيل التطبيق و`/health`.
- مزامنة النسخة والواجهة مع قدرات النظام.

## متغيرات البيئة الأساسية

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

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Long Historical Memory → Signature Cache → Analog Evidence → OOS Validation → Journal → Readiness Gate`

الهدف ليس أكبر عدد مؤشرات، بل أكبر Pool مفيد ثم استبعاد الضوضاء والاحتفاظ فقط بما يثبت Edge مستقرًا خارج العينة.
