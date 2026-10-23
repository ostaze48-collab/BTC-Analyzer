# BTC AI Trader V1.25

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.25 أي حالة أو درجة تسمح تلقائيًا باستخدام أموال حقيقية أو تغيير الأهداف الفعلية.

## ما الجديد في V1.25؟

V1.25 تضيف **Strict Paper Review Protocol** بعد V1.24 Unified Research Readiness. الهدف هو اكتشاف ما إذا كان أداء Paper يبدو مستقرًا الآن، أو أن آخر الصفقات بدأت تتدهور رغم أن المتوسط الطويل ما زال جيدًا.

### النوافذ التشخيصية

يتم فحص آخر:

- `30` صفقة Paper: Mean R ≥ `0.05`، Profit Factor ≥ `1.10`، Max Drawdown ≤ `5R`، Net R > 0.
- `60` صفقة Paper: Mean R ≥ `0.07`، Profit Factor ≥ `1.15`، Max Drawdown ≤ `7R`، Net R > 0.
- `100` صفقة Paper: Mean R ≥ `0.08`، Profit Factor ≥ `1.20`، Max Drawdown ≤ `10R`، Net R > 0.

كل النتائج تُقاس بوحدة `R` باستخدام `realized_pnl / risk_budget` من الصفقات المغلقة.

**مهم:** نوافذ 30/60/100 متداخلة، لذلك هي **تشخيص للاستقرار والتدهور وليست عينات OOS مستقلة**. لا يجوز اعتبار نجاحها ثلاثة اختبارات مستقلة.

### Recent Decay Gate

حتى لا يخفي التاريخ الطويل تدهورًا حديثًا، يجب أن يكون:

- Mean R لآخر 30 صفقة موجبًا.
- Mean R لآخر 100 صفقة موجبًا.
- Mean R لآخر 30 صفقة لا يقل عن `50%` من Mean R لآخر 100 صفقة.

إذا تدهورت آخر 30 صفقة بشدة، يمنع V1.25 المرور حتى لو كانت نافذة 100 صفقة ما زالت تبدو جيدة.

### شروط الدخول إلى Strict Paper Review

لا يكفي وجود 100 صفقة فقط. يجب أيضًا أن تكون V1.24 أعادت:

`STRICT_PAPER_REVIEW_CANDIDATE`

مع:

- `strict_paper_review_allowed = true`
- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`

أي إشارة تشغيل حقيقي تكسر `paper_only_interlock` وتمنع المرور.

## نتيجة V1.25

إذا فشل أي Gate:

`STRICT_PAPER_REVIEW_BLOCKED`

والمرحلة التالية:

`CONTINUE_PAPER_COLLECTION`

إذا نجحت جميع الـGates:

`STRICT_PAPER_REVIEW_PASSED`

والمرحلة التالية الوحيدة:

`EXTENDED_PAPER_OBSERVATION`

حتى عند النجاح:

- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `guarantee = NONE`

أي أن V1.25 لا تفتح التداول الحقيقي؛ بل تسمح فقط بمراقبة Paper أطول وأكثر صرامة.

## Unified Research Readiness V1.24

V1.24 تجمع الأدلة الرئيسية في حكم واحد:

1. Core Readiness: Paper sample + genuine chronological OOS + PF/Avg R/Return + Drawdown + Brain×Regime robustness + Cycle holdout.
2. Target Evidence: Full Historical Target Walk-Forward + Frozen-entry Live Shadow.
3. Feature Research: Feature Edge Lab + Incremental Feature Walk-Forward كدليل داعم، وليس شرطًا يجبر النظام على overfitting.
4. Execution Interlock: real execution يجب أن يبقى OFF.

`Research Score` معلوماتي فقط ولا يمكنه تجاوز Hard Gate فاشل.

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
10. Core Readiness Gate.
11. Unified Research Readiness V1.24.
12. Strict Paper Review Protocol V1.25.

## السوق والفريمات

النظام يقرأ 18 فريمًا من `1m` حتى `1Y` مع طبقات Micro / Intraday / Swing / Macro. التحليل يعتمد الشموع المغلقة للقرارات، مع فصل واضح بين البيانات المتاحة وقت القرار والبيانات المستقبلية المستخدمة لاحقًا في التحقق.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط في أي لحظة.
- LONG/SHORT وحجم المركز والرافعة Paper تُحدد تلقائيًا.
- الرافعة الافتراضية القصوى: `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%`.
- أهداف Risk Engine الحالية من `1R` حتى `5R`.
- Soft Pause قبل حد الخسارة الكلي.
- Hard model drawdown limit = `25%` من رأس المال الابتدائي.
- Target Advisor / Feature research / Historical Analog layers لا تغيّر التنفيذ تلقائيًا.

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
- Frozen-entry Live Shadow Target.
- Target Evidence Consensus Gate.
- Unified Research Readiness.
- Strict Paper Review مع نوافذ 30/60/100، Recent Decay، Brain/Regime concentration، وكل أسباب المنع.

## API

- `GET /api/strict-paper-review`
- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v35.js`.
- Unit tests لـStrict Paper Review وUnified Readiness وTarget Evidence.
- كشف recent degradation حتى إذا كان التاريخ الطويل جيدًا.
- منع نقص العينة من المرور.
- منع أي real-execution flag من تجاوز Paper interlock.
- No-lookahead / STOP_FIRST / Frozen-entry logic.
- تشغيل التطبيق و`/health`.
- مزامنة رقم النسخة والواجهة والقدرات.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Target Validation → Live Shadow → Target Evidence Gate → Unified Research Readiness → Strict Paper Review → Extended Paper Observation`

الهدف ليس نسخة تدّعي الربح، بل منظومة تستطيع أن **تثبت أين لديها Edge، تكتشف تدهورها مبكرًا، وترفض الانتقال إلى مرحلة أخطر عندما يكون الدليل غير كافٍ**.
