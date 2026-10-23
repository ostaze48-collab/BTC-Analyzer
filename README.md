# BTC AI Trader V1.24

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.24 أي حالة أو درجة تسمح تلقائيًا باستخدام أموال حقيقية.

## ما الجديد في V1.24؟

V1.24 تضيف **Unified Research Readiness**: حكم واحد يجمع الأدلة الموزعة عبر المنظومة بدل قراءة كل لوحة منفردة.

الحكم يقرأ أربع مجموعات رئيسية:

1. **Core Readiness**: Paper sample + genuine chronological OOS + Profit Factor / Avg R / Return + Drawdown + Brain×Regime robustness + Cycle holdout.
2. **Target Evidence**: Full Historical Target Walk-Forward + Frozen-entry Live Shadow عبر V1.23 Target Evidence Consensus Gate.
3. **Feature Research**: Feature Edge Lab + Incremental Feature Walk-Forward كدليل داعم مستقل.
4. **Execution Interlock**: يجب أن يبقى التنفيذ الحقيقي معطّلًا أثناء تقييم الجاهزية.

### لماذا Feature Edge دليل داعم وليس بوابة إجبارية؟

إذا جعلنا اكتشاف Feature جديد شرطًا للترقية، فقد ندفع النظام إلى data mining / overfitting فقط حتى يجد متغيرًا يمر. لذلك:

- Feature Edge يظهر بوضوح داخل الحكم الموحد.
- Chronological OOS وIncremental Walk-Forward يبيّنان إن كان هناك Edge إضافي قابل للقياس.
- لكنه لا يستطيع وحده ترقية المرحلة، ولا يُجبر النظام على تصنيع Edge جديد.
- لا يوجد Auto Promotion لأي Feature.

## حالات Unified Readiness

- `DATA_BUILDING`: البيانات والأدلة ما زالت غير ناضجة.
- `EVIDENCE_BUILDING`: بعض الطبقات واعدة لكن Hard Gates ما زالت مفتوحة.
- `SHADOW_VALIDATED`: Target Evidence متسقة لكن Core execution evidence لم يكتمل بعد.
- `STRICT_PAPER_REVIEW_CANDIDATE`: جميع Mandatory Research Gates اجتازت، والمرحلة التالية المسموحة فقط هي **مراجعة/اختبار Paper أكثر صرامة**.

حتى عند أعلى حالة:

- `paper_only = true`
- `strict_paper_review_allowed = true` فقط عند اجتياز Mandatory Gates.
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `guarantee = NONE`

`Research Score` معلوماتي فقط ولا يمكنه تجاوز Hard Gate فاشل.

## Target Evidence Consensus Gate V1.23

لا يسمح حتى بمرحلة البحث التالية لمنطق الأهداف إلا عند اجتماع:

- نجاح Full Historical Target Walk-Forward على عقلين على الأقل.
- Holdout موجب وعدم تضخم Drawdown فوق الحد.
- `LIVE_SHADOW_OUTPERFORMS` من دليل Frozen-entry.
- عدد كافٍ من المقارنات الحية المحسومة والـtarget overrides.
- Resolution Coverage كافية.

والنتيجة القصوى لهذه الطبقة تبقى `BOUNDED_SHADOW_EXPERIMENT_CANDIDATE` بوزن تنفيذ صفر.

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

## السوق والفريمات

النظام يقرأ 18 فريمًا من `1m` حتى `1Y` مع طبقات Micro / Intraday / Swing / Macro. التحليل يعتمد الشموع المغلقة للقرارات، ويحتفظ بفصل واضح بين البيانات المستخدمة في القرار والبيانات المستقبلية المستخدمة لاحقًا في التحقق.

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
- Unified Research Readiness مع Mandatory Gates + Supporting Evidence + أسباب الرفض.

## API

- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v34.js`.
- Unit tests لـUnified Readiness وTarget Evidence وNo-lookahead وFrozen-entry logic.
- تشغيل التطبيق و`/health`.
- مزامنة رقم النسخة والواجهة والقدرات.
- بقاء real execution معطّلًا.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Target Validation → Live Shadow → Target Evidence Gate → Unified Research Readiness → Strict PAPER Review`

الهدف ليس نسخة تدّعي الربح، بل منظومة تستطيع أن **تثبت** أين لديها Edge، ترفض الترقية عند ضعف الدليل، وتقول متى يجب عليها الامتناع عن التداول.
