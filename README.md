# BTC AI Trader V1.26

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. V1.26 لا تمنح أي أهلية للتنفيذ الحقيقي حتى لو اجتازت كل مراحل البحث الحالية.

## ما الجديد في V1.26؟

V1.26 تضيف **Extended Paper Observation** بعد V1.25 Strict Paper Review. الفكرة الأساسية: لا يكفي أن تنجح المنظومة في لقطة واحدة عند 100 صفقة؛ يجب أن يبقى الأداء مقبولًا بعد وصول صفقات جديدة فعلًا.

### Persisted Checkpoints

تُحفظ نتائج Strict Paper Review في SQLite وفق قواعد تمنع تصنيع دليل زائف من polling أو تحديث الصفحة:

- أول checkpoint لا يُسمح به قبل `100` صفقة Paper مؤهلة.
- بعد ذلك لا يُحفظ checkpoint جديد إلا بعد `20` صفقة مؤهلة جديدة على الأقل.
- تكرار الطلب عند نفس عدد الصفقات يعيد `NO_NEW_ELIGIBLE_TRADES`.
- إذا تقدمت العينة بأقل من 20 صفقة يعيد `CHECKPOINT_GAP_NOT_REACHED`.
- عدد الصفقات المؤهلة `eligible_samples` فريد داخل سجل checkpoints.
- Reset للمحاكاة يمسح سجل checkpoints لأنه لم يعد يمثل نفس تجربة Paper.

بهذا لا تستطيع الواجهة التي تعمل كل دقيقة أن تنشئ أربعة أدلة من نفس البيانات.

## شروط Persistence Confirmation

حتى يظهر:

`PERSISTENCE_CONFIRMED_PAPER_ONLY`

يجب أن تجتمع الشروط التالية:

1. وجود `4` checkpoints محفوظة على الأقل.
2. أن يمتد أول وآخر checkpoint عبر `60` صفقة مؤهلة جديدة على الأقل.
3. أن تكون المسافات بين checkpoints المحفوظة ≥ `20` صفقة جديدة.
4. آخر `3` checkpoints يجب أن تكون `STRICT_PAPER_REVIEW_PASSED`.
5. Strict Paper Review الحالية يجب أن تظل ناجحة الآن.
6. Mean R لآخر 30 صفقة يجب أن يبقى موجبًا عبر آخر 3 checkpoints وألا يهبط في أحدث نقطة لأقل من 50% من متوسط هذه النقاط.
7. Paper-only interlock يجب أن يبقى مقفولًا بالكامل.

إذا تحققت الشروط، المرحلة التالية ليست Live Trading بل:

`CONTINUE_LONG_HORIZON_PAPER_MONITORING`

## لماذا هذا ليس OOS مستقلًا؟

الـcheckpoints منفصلة بعدد صفقات جديدة، لكن نوافذ 30/60/100 داخل كل checkpoint ما زالت تتداخل جزئيًا. لذلك تصف V1.26 هذا الدليل باسم:

`TEMPORAL_PERSISTENCE_DIAGNOSTIC`

وليس Independent OOS.

المنظومة تعرض التنبيه صراحة:

> Checkpoint windows overlap. Persistence across later trade counts is useful stability evidence but is not independent OOS evidence.

## V1.25 Strict Paper Review

V1.25 تفحص آخر 30/60/100 صفقة بوحدة `R`:

- 30 صفقة: Mean R ≥ `0.05`، PF ≥ `1.10`، Max DD ≤ `5R`.
- 60 صفقة: Mean R ≥ `0.07`، PF ≥ `1.15`، Max DD ≤ `7R`.
- 100 صفقة: Mean R ≥ `0.08`، PF ≥ `1.20`، Max DD ≤ `10R`.

وتضيف Recent Decay Gate حتى لا يخفي الأداء الطويل تدهور آخر 30 صفقة.

## حالات V1.26

- `PERSISTENCE_NOT_CONFIRMED`: Strict Paper الحالية غير ناجحة أو الأدلة الزمنية غير متوافقة.
- `PERSISTENCE_BUILDING`: Strict Paper ناجحة لكن عدد checkpoints/الامتداد الزمني غير كافٍ بعد.
- `PERSISTENCE_CONFIRMED_PAPER_ONLY`: ثبات Paper مؤكد وفق شروط V1.26 الحالية، مع بقاء كل التنفيذ الحقيقي معطّلًا.

دائمًا:

- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `guarantee = NONE`

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
13. Extended Paper Observation V1.26.

## السوق وإدارة المخاطرة

- BTCUSDT.
- 18 فريمًا من `1m` حتى `1Y`.
- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- الرافعة Paper بحد أقصى افتراضي `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%`.
- أهداف Risk Engine الحالية من `1R` حتى `5R`.
- Soft Pause + Hard model drawdown limit `25%`.
- Historical/Feature/Target research لا يغير التنفيذ تلقائيًا.

## واجهة الهاتف

V1.26 تضيف لوحة Extended Paper Observation تعرض:

- Status.
- عدد checkpoints الحالية والمطلوبة.
- Trade span الحالي والمطلوب.
- Last-4 pass rate.
- Next stage.
- Timeline لآخر checkpoints مع eligible samples و30-trade Mean R.
- كل persistence gates وأسباب الفشل.
- زر حفظ checkpoint يدوي.
- محاولة checkpoint تلقائية دورية؛ backend هو الذي يقرر إن كانت 20 صفقة جديدة قد اكتملت.

## API

- `GET /api/extended-paper-observation`
- `POST /api/extended-paper-observation/checkpoint`
- `GET /api/strict-paper-review`
- `GET /api/unified-readiness`
- `GET /api/target-evidence-gate`
- `GET /api/live-shadow-target`
- `GET /api/full-target-walkforward?brain=INTRADAY`
- `POST /api/full-target-walkforward?brain=INTRADAY&max_points=300`

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript syntax حتى `v36.js`.
- Unit tests للتخزين الدائم للـcheckpoints.
- منع polling من تصنيع persistence evidence.
- شرط 20 صفقة جديدة بين checkpoints.
- شرط 4 checkpoints و60 صفقة span.
- كسر التأكيد عند checkpoint حديث فاشل أو recent edge decay.
- Strict Paper / Unified Readiness / Target Evidence / No-lookahead.
- تشغيل التطبيق و`/health`.
- بقاء real execution وtarget auto-apply معطلين.

## المبدأ

`Market Data → 3 Brains → MASTER → Adaptive Risk → Historical/OOS Evidence → Live Shadow → Unified Readiness → Strict Paper Review → Persisted Trade Checkpoints → Extended Paper Observation`

الهدف هو أن لا تُكافأ المنظومة على نجاح لحظي؛ بل أن **تثبت أن سلوكها يبقى متماسكًا بعد وصول بيانات وصفقات جديدة، وأن تسجل الفشل كما تسجل النجاح**.
