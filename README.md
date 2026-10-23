# BTC AI Trader V1.25

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.25 أي حالة أو Trend أو Research Score تسمح تلقائيًا باستخدام أموال حقيقية.

## ما الجديد في V1.25؟

V1.25 تضيف **Research Evidence History**: سجل زمني دائم لقوة الأدلة البحثية بدل الاعتماد على Snapshot لحظية واحدة من Unified Research Readiness.

كل Snapshot تحفظ بصورة مختصرة:

- نسخة التطبيق.
- Research Stage.
- Research Score.
- عدد Mandatory Gates الناجحة والفاشلة.
- Core Readiness status/score.
- Target Evidence status/pass.
- وجود Incremental Feature OOS evidence.
- عدد صفقات Paper.
- Paper Profit Factor وMax Drawdown.
- `paper_only` و`real_execution_eligibility`.

### متى يُحفظ Snapshot؟

السجل لا يكتب نسخة جديدة كل دقيقة بلا فائدة:

- إذا حدث **تغيّر مادي** في Stage / Score / Gates / Target / Feature evidence / Paper trades، تُحفظ Snapshot فورًا.
- إذا لم يتغير شيء جوهريًا، يُستخدم حد زمني افتراضي يقارب 15 دقيقة لمنع التكرار.
- يحتفظ المخزن بحد أقصى يقارب 5000 Snapshot.
- عند `Reset` للمحاكاة يُمسح Research Evidence History أيضًا، حتى لا تختلط حقبتان بحثيتان مختلفتان.

## Evidence Trend

V1.25 تصنف اتجاه قوة الأدلة إلى:

- `INSUFFICIENT_HISTORY`: أقل من 3 Snapshots؛ لا تدّعي وجود Trend.
- `IMPROVING`: تحسن واضح في Stage أو Mandatory Gates أو Research Score عبر التاريخ.
- `STABLE`: الأدلة مستقرة دون تحسن/تراجع مادي.
- `REGRESSING`: آخر خطوة تراجعت في Stage أو Gates أو هبط Score بشكل مادي.

**هذا Trend للأدلة البحثية فقط، وليس إشارة BUY/SELL ولا توقعًا للسعر.**

وتعرض الطبقة أيضًا:

- Current Stage وBest Stage.
- Stage transitions وStage regressions.
- Research Score الحالي/الأول/المتوسط/الأفضل/الأسوأ.
- Delta من أول Snapshot ومن السابقة.
- Mandatory Gates الحالية وتغيرها من البداية.
- Target pass rate عبر السجل.
- Incremental Feature support rate.
- عدد صفقات Paper الحالية.
- طول الفترة الزمنية التي يغطيها السجل.

## Unified Research Readiness V1.24

تبقى V1.24 هي طبقة الحكم الموحّد الأساسية:

1. **Core Readiness**: Paper sample + genuine chronological OOS + Profit Factor / Avg R / Return + Drawdown + Brain×Regime robustness + Cycle holdout.
2. **Target Evidence**: Full Historical Target Walk-Forward + Frozen-entry Live Shadow عبر Target Evidence Consensus Gate.
3. **Feature Research**: Feature Edge Lab + Incremental Feature Walk-Forward كدليل داعم مستقل.
4. **Execution Interlock**: يجب أن يبقى التنفيذ الحقيقي معطّلًا أثناء تقييم الجاهزية.

أعلى حالاتها ما زالت:

`STRICT_PAPER_REVIEW_CANDIDATE`

وهي لا تسمح إلا بمراجعة/اختبار Paper أكثر صرامة. حتى عند أعلى حالة:

- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `guarantee = NONE`

## Target Evidence Consensus

لا يسمح حتى بمرحلة البحث التالية لمنطق الأهداف إلا عند اجتماع أدلة مستقلة:

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
11. Unified Research Readiness.
12. **Research Evidence History V1.25**.

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
- Target Advisor / Feature research / Historical Analog / Research History لا تغيّر التنفيذ تلقائيًا.

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
- **Research Evidence History**: Trend + Score delta + Gates + Timeline لآخر Snapshots.

## API

- `GET /api/research-history?limit=240`
- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v35.js`.
- Unit tests لـResearch Evidence History وUnified Readiness وTarget Evidence وNo-lookahead وFrozen-entry logic.
- منع ادعاء Trend ناضج بعينتين فقط.
- منع تكرار Snapshot غير المتغير داخل نافذة throttle.
- حفظ التغير المادي فورًا.
- تشغيل التطبيق و`/health`.
- مزامنة رقم النسخة والواجهة والقدرات.
- بقاء real execution معطّلًا.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Target Validation → Live Shadow → Target Evidence Gate → Unified Research Readiness → Research Evidence History → Strict PAPER Review`

الهدف ليس نسخة تدّعي الربح، بل منظومة تستطيع أن **تثبت** أين لديها Edge، تراقب هل الدليل يتحسن أو يتراجع مع الزمن، وترفض الترقية عندما تكون الأدلة غير مستقرة.