# BTC AI Trader V1.23

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد أدلة Out-of-Sample / Walk-Forward / Live Shadow قوية ومتسقة، ثم قرار منفصل لاحقًا.

## ما الجديد في V1.23؟

V1.23 تضيف **Target Evidence Consensus Gate**. هذه الطبقة لا تبحث عن صفقة ولا تغيّر TP؛ وظيفتها منع الترقية المبكرة لأي منطق أهداف تعلمناه تاريخيًا.

حتى يمر Gate يجب أن تجتمع أدلة مستقلة:

- نجاح Full Historical Target Walk-Forward على **عقلين على الأقل**.
- لكل عقل ناجح: عينة Walk-Forward كافية + Holdout موجب + عدم تضخم Drawdown بأكثر من الحد المحدد.
- `LIVE_SHADOW_OUTPERFORMS` في Frozen-entry Live Shadow.
- عدد كافٍ من المقارنات الحية المحسومة.
- عدد كافٍ من الحالات التي غيّر فيها Advisor الهدف فعلًا.
- Resolution Coverage كافية.
- Holdout حي موجب بدون تضخم غير مقبول في Drawdown.

إذا فشلت أي بوابة تكون النتيجة:

`NOT_READY_FOR_TARGET_INFLUENCE`

وإذا اجتمعت جميعها تصبح فقط:

`BOUNDED_SHADOW_EXPERIMENT_CANDIDATE`

حتى في هذه الحالة:

- `auto_apply = false`
- `target_execution_weight = 0`
- `master_weight = 0`
- `real_execution_enabled = false`

أي أن النجاح يسمح فقط بتصميم **مرحلة بحثية محدودة لاحقة**، وليس بتغيير التنفيذ تلقائيًا.

## طبقات الإثبات الحالية

1. Feature Edge Lab.
2. Incremental Feature Walk-Forward.
3. Historical Setup Memory.
4. Analog Edge Validation.
5. Historical Target Advisor `1R→5R`.
6. Journal Target Policy Validation.
7. Full Historical Target Walk-Forward لكل عقل.
8. Frozen-entry Live Shadow Target.
9. Target Evidence Consensus Gate.
10. Readiness Gate للنظام كاملًا.

## السوق والفريمات

النظام يقرأ 18 فريمًا من `1m` حتى `1Y`، مع طبقات Micro / Intraday / Swing / Macro. الفريمات الأكبر تدخل في السياق والاتجاه البنيوي، والفريمات الصغيرة تدخل في التوقيت والتنفيذ.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط في أي لحظة.
- LONG/SHORT وحجم المركز والرافعة Paper تُحدد تلقائيًا.
- الرافعة الافتراضية القصوى: `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%`.
- الأهداف الحالية من `1R` حتى `5R` حسب Risk Engine الحالي.
- Soft Pause قبل حد الخسارة الكلي.
- Hard model drawdown limit = `25%` من رأس المال الابتدائي.
- الأدلة التاريخية/Shadow لا تغيّر التنفيذ حتى اجتياز مراحل التحقق اللاحقة.

## واجهة الهاتف

واجهة Phone-First تعرض:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk / Leverage / Targets.
- Cycle / Network / Derivatives.
- Edge Lab + Incremental Walk-Forward.
- Historical Memory + Analog Validation + Signature Cache.
- Historical Target Advisor.
- Full Historical Target Walk-Forward.
- Live Shadow Target.
- Target Evidence Consensus Gate مع كل Gate على شكل ✅ / ⛔ وسبب الشرط.

## API

- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v33.js`.
- Unit tests لكل بوابات Target Evidence.
- No-lookahead / STOP_FIRST / Frozen-entry evidence.
- تشغيل التطبيق و`/health`.
- مزامنة رقم النسخة والواجهة مع قدرات الـbackend.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Target Validation → Live Shadow → Evidence Consensus Gate → Unified Readiness`

الهدف ليس الوصول إلى نسخة تقول إنها تربح، بل نسخة تستطيع أن **تثبت** أين لديها Edge، ومتى يختفي، ومتى يجب عليها الامتناع عن التداول.
