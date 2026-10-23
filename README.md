# BTC AI Trader V1.26

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.26 أي حالة أو Trend أو Research Score تسمح تلقائيًا باستخدام أموال حقيقية أو تغيير الأهداف الفعلية.

## ما الجديد في V1.26؟

V1.26 تضيف **Research Evidence History** فوق V1.25 Strict Paper Review. بدل الاعتماد على لقطة واحدة من Unified Readiness أو نتيجة لحظية من Strict Paper Review، تحفظ المنظومة تاريخًا زمنيًا مضغوطًا يوضح هل قوة الأدلة تتحسن، تستقر، أم تتراجع.

كل Snapshot تحفظ:

- نسخة التطبيق.
- Unified Research Stage وResearch Score.
- عدد Mandatory Gates الناجحة والفاشلة.
- Core Readiness status/score.
- Target Evidence status/pass.
- Incremental Feature OOS support.
- Strict Paper Review status/pass وعدد Gates الناجحة.
- عدد صفقات Paper وProfit Factor وMax Drawdown.
- Paper-only / real-execution eligibility flags.

### متى تُحفظ Snapshot؟

- أي تغير مادي في Stage / Score / Gates / Target / Feature / Strict Paper / عدد الصفقات يُحفظ فورًا.
- إذا لم يتغير شيء مهم، يمنع throttle الافتراضي تكرار نفس Snapshot خلال نحو 15 دقيقة.
- يحتفظ المخزن بحد أقصى يقارب 5000 Snapshot.
- `Reset` يمسح Research Evidence History أيضًا حتى تبدأ حقبة بحثية جديدة ولا تختلط نتائج قبل التصفير بما بعده.

## Evidence Trend

V1.26 تصنف اتجاه الأدلة إلى:

- `INSUFFICIENT_HISTORY`: أقل من 3 Snapshots؛ لا تدعي وجود Trend ناضج.
- `IMPROVING`: تحسن مادي في Stage أو Mandatory Gates أو Research Score، أو وصول Strict Paper إلى PASS.
- `STABLE`: الأدلة مستقرة دون تغير جوهري.
- `REGRESSING`: آخر خطوة تراجعت في Stage/Gates/Score أو انتقل Strict Paper من `PASSED` إلى `BLOCKED`.

**Trend هنا اتجاه قوة الأدلة وثبات Paper فقط، وليس BUY/SELL ولا توقعًا للسعر.**

وتعرض الطبقة أيضًا:

- Current Stage وBest Stage.
- Current Strict Paper status وStrict pass rate.
- Stage/Strict regressions.
- Research Score الحالي/الأول/المتوسط/الأفضل/الأسوأ.
- Delta من أول Snapshot ومن السابقة.
- Mandatory Gates الحالية وتغيرها منذ البداية.
- Strict Gates الحالية.
- Target pass rate وFeature support rate.
- عدد صفقات Paper الحالية وطول الفترة المغطاة.

## Strict Paper Review Protocol V1.25

يبقى V1.25 كما هو دون استبدال:

- آخر `30` صفقة: Mean R ≥ `0.05`، PF ≥ `1.10`، Max DD ≤ `5R`، Net R > 0.
- آخر `60` صفقة: Mean R ≥ `0.07`، PF ≥ `1.15`، Max DD ≤ `7R`، Net R > 0.
- آخر `100` صفقة: Mean R ≥ `0.08`، PF ≥ `1.20`، Max DD ≤ `10R`، Net R > 0.
- Recent Decay Gate يمنع التاريخ الطويل من إخفاء ضعف آخر 30 صفقة.

النوافذ 30/60/100 **متداخلة وتشخيصية فقط وليست OOS مستقلة**.

إذا نجحت جميع Gates تكون النتيجة:

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

## Unified Research Readiness V1.24

V1.24 تجمع Core Readiness + Target Evidence + Execution Interlock في Mandatory Gates، وتعرض Feature Edge / Incremental Walk-Forward كأدلة داعمة مستقلة لتقليل ضغط overfitting.

`Research Score` معلوماتي فقط ولا يمكنه تجاوز Hard Gate فاشل.

أعلى حالة Unified هي:

`STRICT_PAPER_REVIEW_CANDIDATE`

وهي تسمح فقط بالدخول إلى Strict Paper Review، لا بالتداول الحقيقي.

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
13. **Research Evidence History V1.26**.

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
- Historical Target / Feature research / Strict Paper / Research History لا تغيّر التنفيذ تلقائيًا.

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
- Strict Paper Review في `v35.js`.
- **Research Evidence History في `v36.js`** مع Trend + Timeline + Strict Paper history.

## API

- `GET /api/research-history?limit=240`
- `GET /api/strict-paper-review`
- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v36.js` مع بقاء `v35.js` للـStrict Paper Review.
- Unit tests لـResearch Evidence History + Strict Paper Review + Unified Readiness.
- منع ادعاء Trend بعينتين فقط.
- اعتبار تحول Strict Paper من PASS إلى BLOCKED تراجعًا.
- منع Snapshot مكرر داخل نافذة throttle مع حفظ أي تغير مادي فورًا.
- إمكانية إعادة فتح ResearchHistoryStore بأمان بعد إغلاق connection.
- No-lookahead / STOP_FIRST / Frozen-entry logic.
- تشغيل التطبيق و`/health`.
- مزامنة رقم النسخة والواجهة والقدرات.
- بقاء real execution معطّلًا.

## المبدأ

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Validation → Live Shadow → Target Evidence Gate → Unified Research Readiness → Strict Paper Review → Research Evidence History → Extended Paper Observation`

الهدف ليس نسخة تدّعي الربح، بل منظومة تستطيع أن **تثبت أين لديها Edge، تكتشف التدهور الحديث، وتراقب هل جودة الأدلة نفسها ثابتة بمرور الزمن قبل أي انتقال أخطر**.
