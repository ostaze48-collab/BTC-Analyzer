# BTC AI Trader V1.27

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.27 أي حالة أو Trend أو Stability result تسمح تلقائيًا باستخدام أموال حقيقية أو تغيير الأهداف الفعلية.

## ما الجديد في V1.27؟

V1.27 تضيف **Evidence Stability Window** فوق Research Evidence History. الهدف هو منع Snapshot ناجحة أو تكرار نفس الحالة بلا صفقات جديدة من أن يبدو كأنه دليل مستقر.

### شروط نافذة الثبات

للوصول إلى:

`STABILITY_WINDOW_PASSED`

يجب أن تتحقق جميع الشروط التالية:

- Research History يغطي **24 ساعة فعلية على الأقل**.
- يوجد **8 Snapshots على الأقل** داخل نافذة المراقبة الأخيرة.
- حدثت **20 صفقة Paper مغلقة جديدة على الأقل** خلال نافذة المراقبة.
- إجمالي صفقات Paper وصل إلى **120 صفقة على الأقل**.
- Unified Readiness الحالية = `STRICT_PAPER_REVIEW_CANDIDATE`.
- Strict Paper Review الحالية = `STRICT_PAPER_REVIEW_PASSED`.
- Strict Paper يمر في **75% على الأقل** من Snapshots الحديثة.
- جميع Mandatory Unified Gates تكون ناجحة معًا في **75% على الأقل** من Snapshots الحديثة.
- لا يوجد Unified-stage downgrade أو Strict Paper `PASS → BLOCKED` داخل نافذة المراقبة.
- `real_execution_eligibility` يبقى false في كل Snapshot داخل النافذة.

### لماذا الوقت + الصفقات معًا؟

مرور 24 ساعة وحده لا يكفي. لو ظلت المنظومة تعرض نفس الحالة بدون صفقات جديدة، لا تعتبر V1.27 ذلك ثباتًا جديدًا. لذلك Gate `new_paper_trades` يفرض وجود بيانات تداول Paper جديدة فعلًا داخل الفترة.

إذا فشل أي شرط:

`STABILITY_WINDOW_BLOCKED`

والمرحلة التالية:

`CONTINUE_PAPER_STABILITY_COLLECTION`

إذا نجحت جميع الشروط:

`STABILITY_WINDOW_PASSED`

والمرحلة التالية الوحيدة:

`EXTENDED_PAPER_STABILITY_OBSERVATION`

حتى عند النجاح:

- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `score_is_authorization = false`
- `guarantee = NONE`

## V1.26 Research Evidence History

V1.26 تحفظ Snapshots زمنية مختصرة لـUnified Readiness + Strict Paper Review، وتعرض:

- `INSUFFICIENT_HISTORY`
- `IMPROVING`
- `STABLE`
- `REGRESSING`

وتعتبر Strict Paper `PASS → BLOCKED` تراجعًا حتى لو بقي Research Score مرتفعًا.

Trend هنا للأدلة البحثية فقط، وليس إشارة BUY/SELL.

## V1.25 Strict Paper Review

يبقى بروتوكول 30/60/100 صفقة كما هو:

- 30 صفقة: Mean R ≥ 0.05، PF ≥ 1.10، Max DD ≤ 5R.
- 60 صفقة: Mean R ≥ 0.07، PF ≥ 1.15، Max DD ≤ 7R.
- 100 صفقة: Mean R ≥ 0.08، PF ≥ 1.20، Max DD ≤ 10R.
- Recent Decay Gate يمنع آخر 30 صفقة من الانهيار مقارنة بآخر 100.

النوافذ متداخلة وتشخيصية وليست OOS مستقلة.

## طبقات الإثبات الحالية

1. Feature Edge Lab.
2. Incremental Feature Walk-Forward.
3. Historical Setup Memory.
4. Analog Edge Validation.
5. Historical Target Advisor `1R→5R`.
6. Journal Target Policy Validation.
7. Full Historical Target Walk-Forward.
8. Frozen-entry Live Shadow Target.
9. Target Evidence Consensus Gate.
10. Core Readiness Gate.
11. Unified Research Readiness V1.24.
12. Strict Paper Review V1.25.
13. Research Evidence History V1.26.
14. **Evidence Stability Window V1.27**.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- Paper leverage القصوى الافتراضية: `5x`.
- Dynamic risk/stop/targets بين `1R` و`5R`.
- Soft Pause + hard model drawdown limit.
- لا توجد طبقة بحثية تملك Auto Apply على التنفيذ.

## واجهة الهاتف

- `v35.js`: Strict Paper Review.
- `v36.js`: Research Evidence History.
- `v37.js`: Evidence Stability Window مع الوقت، Snapshots، صفقات Paper الجديدة، Strict pass rate، regressions وكل أسباب المنع.

## API

- `GET /api/evidence-stability?limit=1000`
- `GET /api/research-history?limit=240`
- `GET /api/strict-paper-review`
- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript حتى `v37.js`.
- منع مرور نافذة 24 ساعة بدون صفقات جديدة.
- منع أي PASS→BLOCKED حديث من المرور.
- منع أي real-execution flag داخل النافذة.
- استمرار اختبارات Strict Paper / Evidence History / Unified Readiness / No-lookahead.
- Startup + `/health`.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Validation → Live Shadow → Unified Readiness → Strict Paper Review → Evidence History → 24H Stability Window → Extended Paper Stability Observation`

الهدف هو أن لا تترقى المنظومة بسبب **لقطة جيدة واحدة**؛ يجب أن يبقى الدليل قويًا عبر الزمن ومع بيانات Paper جديدة فعلًا.