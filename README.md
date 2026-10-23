# BTC AI Trader V1.21

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward طويلة بما يكفي.

## ما الجديد في V1.21؟

V1.21 تضيف **Full Historical Target Walk-Forward** لاختبار ما إذا كان اختيار الهدف من الحالات التاريخية المشابهة يضيف Edge حقيقيًا مقارنة بهدف Risk Engine الحالي.

الاختبار يعمل لكل عقل بشكل مستقل:

- `SCALP` على Anchor `5m`.
- `INTRADAY` على Anchor `30m`.
- `SWING` على Anchor `4h`.

وتمت إضافة تاريخ عميق صريح لفريم `30m` الخاص بـINTRADAY، حتى لا يكون هذا العقل محدودًا بتاريخ قصير أثناء المقارنة.

### كيف يمنع Lookahead؟

عند كل نقطة تاريخية:

1. تُبنى Snapshots من الشموع التي أغلقت **حتى تلك اللحظة فقط**.
2. يعاد تشغيل العقول الثلاثة + `MASTER`.
3. لا تدخل النقطة للاختبار إلا إذا كان العقل الجاري اختباره هو الفائز فعلًا.
4. يتم اختيار Local Historical Target من **السجلات السابقة فقط** ذات الاتجاه نفسه والأقرب في البصمة السوقية.
5. بعد تجميد الهدف، فقط عندها تُقرأ Future Window لقياس النتيجة.
6. المقارنة تستخدم نفس بنية الخروج 30% / 40% / 30%.
7. عند لمس Stop والهدف داخل الشمعة نفسها، يبقى `STOP_FIRST_CONSERVATIVE`.
8. إذا انتهى Horizon بدون Stop أو Target كامل، تُغلق الكمية المتبقية على آخر Close بدل ترك المسار غير محسوم.

### ما الذي تتم مقارنته؟

- Baseline Target من Risk Engine الحالي.
- Local Historical Target من أقرب السوابق السابقة فقط.
- Mean R.
- Win Rate.
- Profit Factor.
- Max Drawdown R.
- Final Holdout.
- الأداء حسب Market Regime.
- نسبة المرات التي غيّر فيها Advisor الهدف فعلًا.

حتى لو ظهر `FULL_WALKFORWARD_OUTPERFORMS` تبقى:

- `auto_apply = false`
- `weight_in_risk_engine = 0`

المرحلة التالية هي Live Shadow Target Policy قبل أي تأثير فعلي على التنفيذ.

## المكونات الحالية

- 18 فريمًا من `1m` حتى `1Y`.
- مؤشرات فنية + Market Structure + Liquidity + Patterns + مئات Background Features.
- Cycle/Valuation Models.
- Network وDerivatives في `SHADOW_ONLY`.
- Feature Edge Lab + Incremental Walk-Forward.
- Historical Setup Memory + Analog Edge Validation.
- Long Historical Replay Memory + Historical Signature Cache.
- Historical Target Advisor `1R→5R`.
- Journal Target Policy Validation V1.20.
- Full Historical Target Walk-Forward V1.21.
- Adaptive paper risk/leverage، صفقة واحدة فقط، وحد حماية رأسمال تجريبي.
- Learning Journal + Backtesting + Readiness Gate.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- LONG/SHORT وحجم المركز والرافعة Paper تُحدد تلقائيًا.
- الرافعة الافتراضية القصوى: `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%`.
- الأهداف الحالية من `1R` حتى `5R`.
- Soft Pause قبل حد الخسارة الكلي.
- Hard model drawdown limit = `25%` من رأس المال الابتدائي.

## واجهة الهاتف

واجهة Phone-First وتعرض:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk / Leverage / Targets.
- Cycle / Network / Derivatives.
- Edge Lab + Incremental Walk-Forward.
- Historical Memory + Analog Validation + Signature Cache.
- Historical Target Advisor.
- Journal Target Policy Validation.
- Full Historical Target Walk-Forward مع اختيار SCALP / INTRADAY / SWING وعرض Holdout وRegime breakdown.

## API الجديدة

- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

إذا كان الأرشيف العميق غير جاهز، يقوم POST ببدء تحميله ويعيد `ARCHIVE_LOADING` بدل تشغيل اختبار ناقص.

## CI

يفحص GitHub Actions:

- Python compile.
- JavaScript syntax حتى `v31.js`.
- Unit tests، بما فيها No-Lookahead وSTOP_FIRST وفريمات Anchor العميقة.
- تشغيل التطبيق و`/health`.
- مزامنة النسخة والواجهة.

## التشغيل

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

ثم افتح `http://127.0.0.1:8000`.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → Analog Evidence → Target Advisor → Journal Validation → Full Historical Walk-Forward → Shadow Live Validation → Readiness Gate`

الهدف ليس كثرة المؤشرات بحد ذاتها، بل استخدام Pool واسع ثم الاحتفاظ فقط بما يثبت Edge إضافيًا ومستقرًا خارج العينة.
