# BTC AI Trader V1.22

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward وLive Shadow مستقرة بما يكفي.

## ما الجديد في V1.22؟

V1.22 تضيف **Frozen-entry Live Shadow Target**: بدلاً من إعادة تقييم الصفقة لاحقًا بمعلومات أحدث، تستخدم المنظومة `historical_analogs` و`adaptive_risk_plan` المحفوظين في Learning Vector عند **لحظة ENTRY نفسها**، ثم تعيد بناء الهدف الذي كان Historical Target Advisor سيختاره وقت الدخول.

هذا يعني أن المقارنة بين الهدف الفعلي والهدف التاريخي لا تستفيد من معلومات وصلت بعد فتح الصفقة.

### ما الذي يُقاس؟

- Baseline target الذي نفذه Risk Engine فعليًا.
- Shadow target المعاد بناؤه من دليل ENTRY المجمد.
- عدد الصفقات المؤهلة.
- عدد المرات التي غيّر فيها Advisor الهدف.
- Resolution Coverage.
- Mean R / Win Rate / Profit Factor / Max Drawdown R.
- Holdout زمني أخير.
- الأداء حسب SCALP / INTRADAY / SWING.

إذا أغلق النظام الصفقة قبل أن نعرف هل Shadow target أعلى كان سيُضرب لاحقًا، تصبح المقارنة `UNRESOLVED` وتُستبعد بدل اختراع نتيجة.

حتى لو ظهر `LIVE_SHADOW_OUTPERFORMS` تبقى:

- `auto_apply = false`
- `weight_in_risk_engine = 0`
- التنفيذ الحقيقي معطّل.

لا يُفكر في أي تأثير فعلي على الهدف قبل اتفاق دليلين منفصلين:

1. V1.21 Full Historical Target Walk-Forward.
2. V1.22 Frozen-entry Live Shadow.

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
- Frozen-entry Live Shadow Target V1.22.
- Adaptive paper risk/leverage، صفقة واحدة فقط، وحد حماية رأسمال تجريبي.
- Learning Journal + Backtesting + Readiness Gate.

## Full Historical Walk-Forward V1.21

- يعيد تشغيل العقول الثلاثة + MASTER عند نقاط تاريخية.
- لا يستخدم إلا الشموع المغلقة حتى النقطة الجارية.
- يختار Local Historical Target من السجلات السابقة فقط.
- يقرأ Future Window بعد تجميد القرار.
- يقارن Baseline vs Advisor على مسار شموع كامل.
- يعرض Holdout وRegime breakdown.
- `STOP_FIRST_CONSERVATIVE` يبقى مطبقًا.

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

واجهة Phone-First وتعرض كل طبقات النظام، ومنها:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk / Leverage / Targets.
- Cycle / Network / Derivatives.
- Edge Lab + Incremental Walk-Forward.
- Historical Memory + Analog Validation + Signature Cache.
- Historical Target Advisor.
- Journal Target Policy Validation.
- Full Historical Target Walk-Forward.
- Live Shadow Target: Baseline vs Frozen-entry Shadow + Coverage + Holdout + Brain breakdown.

## API

- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

يفحص GitHub Actions:

- Python compile.
- JavaScript syntax حتى `v32.js`.
- Unit tests، بما فيها No-Lookahead وFrozen-entry Shadow وSTOP_FIRST.
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

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → Analog Evidence → Target Advisor → Full Historical Walk-Forward → Frozen-entry Live Shadow → Readiness Gate`

الهدف ليس كثرة المؤشرات بحد ذاتها، بل استخدام Pool واسع ثم الاحتفاظ فقط بما يثبت Edge إضافيًا ومستقرًا خارج العينة والسوق الحي التجريبي.
