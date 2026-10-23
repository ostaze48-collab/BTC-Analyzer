# BTC AI Trader V1.19

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
- Historical Signature Cache لتسريع مقارنة مئات السوابق.
- **Historical Target Advisor V1.19** لاختيار 1R→5R تاريخيًا بشكل محافظ.
- Adaptive paper risk/leverage، صفقة واحدة فقط، وحد حماية رأسمال تجريبي.
- Learning Journal + Backtesting + Readiness Gate.

## Historical Target Advisor V1.19

عندما توجد صفقة مرشحة، تقرأ المنظومة الحالات التاريخية الأقرب لنفس السياق ثم تقارن أهداف `1R` إلى `5R`:

- تستخدم Hit Rate المحسوب من كامل مجموعة الحالات المتشابهة.
- تطبق Laplace smoothing لتقليل الثقة الزائدة في العينات الصغيرة.
- في وضع Summary المحافظ تعتبر **كل حالة لم تصل للهدف = -1R** بدل افتراض أنها خرجت بتعادل أو ربح.
- تعرض Conservative EV لكل هدف.
- تختار أفضل هدف فقط إذا كان EV المحافظ موجبًا بما يكفي.
- تعرض عدد الحالات، Evidence Strength، MFE/MAE، والهدف التاريخي المقترح.
- تبقى `SHADOW_ONLY` و`weight_in_risk_engine = 0`؛ لا تغيّر TP الفعلي بعد.

المرحلة التالية لاختبار هذه الطبقة هي Target Policy Walk-Forward: مقارنة هدف محلي مبني على الحالات المشابهة مقابل أفضل هدف ثابت تعلمناه من الماضي، على نقاط مستقبلية لم تدخل التدريب.

## Historical Signature Cache

- حتى نحو `720` بصمة تاريخية موزعة على الذاكرة المتاحة.
- لا يبدأ Cache العميق قبل توفر `700` شمعة على فريم العقل.
- أثناء البناء يستخدم النظام fallback أصغر ولا يوقف التحليل الحي.
- لا تُستخدم نقطة تاريخية إذا لم توجد بعدها Future Window كاملة.
- قاعدة المسار تبقى `STOP_FIRST_CONSERVATIVE`.
- Historical Memory وSignature Cache وTarget Advisor كلها Shadow research layers حتى اجتياز OOS.

## الذاكرة التاريخية الطويلة

- `SCALP`: أيام/أشهر إضافية للفريمات الصغيرة والمتوسطة.
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
- أهداف فعلية حالية من `1R` حتى `5R` حسب Risk Engine الحالي.
- Target Advisor لا يغيرها بعد؛ يقارنها فقط تاريخيًا.
- توقف وقائي قبل حد الخسارة الكلي.
- حد النموذج التجريبي الكلي `25%`، وليس ضمانًا للسوق الحقيقي بسبب gaps/slippage.

## كيف نقرر أن البيانات السابقة مفيدة؟

1. Historical Analog يعرض التشابه والنتائج السابقة.
2. Analog metrics تدخل Edge Lab كـShadow Features.
3. Chronological Train/Test يمنع خلط الماضي بالمستقبل.
4. Incremental Walk-Forward يقارن Baseline مقابل Baseline+Feature.
5. Target Advisor يختار هدفًا تاريخيًا لكنه يبقى بوزن صفر.
6. Target Policy Walk-Forward سيختبر هل اتباعه يحسن R/DD/PF فعليًا.
7. ثم Full-engine OOS replay.
8. ثم Paper/Shadow performance وReadiness Gate.

## واجهة الهاتف

الواجهة Phone-First وتعرض:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk/Leverage/Targets.
- Cycle/Network/Derivatives.
- Feature Edge وIncremental Walk-Forward.
- Historical Setup Memory وAnalog Validation.
- Long Historical Memory وSignature Cache.
- Historical Target Advisor: جدول 1R→5R مع Hit Rate وConservative EV والهدف المرشح.

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
- JavaScript syntax حتى `v29.js`.
- Unit tests، بما فيها No-lookahead وHistorical Target Advisor.
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

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Long Historical Memory → Signature Cache → Analog Evidence → Target Advisor → OOS Validation → Journal → Readiness Gate`

الهدف ليس زيادة عدد المؤشرات فقط، بل بناء Pool واسع، اختبار فائدته، وإبقاء أي عنصر جديد خارج القرار الحقيقي حتى يثبت Edge إضافيًا ومستقرًا خارج العينة.
