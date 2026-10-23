# BTC AI Trader V1.28

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا توجد في V1.28 أي درجة Stability تسمح تلقائيًا باستخدام أموال حقيقية أو تغيير الأهداف الفعلية.

## ما الجديد في V1.28؟

V1.28 تضيف **Multi‑Day Stability Ladder** فوق V1.27. الهدف هو الانتقال من نافذة قصيرة 24 ساعة إلى سلم ثبات متسلسل:

- `L1_24H`
- `L2_72H`
- `L3_168H` = 7 أيام

لا يمكن القفز إلى مستوى أعلى إذا فشل المستوى السابق.

### L1 · 24H

- ≥ 24 ساعة تاريخ أدلة.
- ≥ 8 Snapshots.
- ≥ 20 صفقة Paper جديدة.
- ≥ 120 صفقة Paper إجمالًا.
- نشاط تداول في ≥ يوم UTC واحد.
- Strict Paper pass rate ≥ 75%.
- Unified mandatory pass rate ≥ 75%.
- لا regressions.
- V1.27 canonical 24H gate يجب أن يمر أيضًا.

### L2 · 72H

- ≥ 72 ساعة.
- ≥ 18 Snapshots.
- ≥ 45 صفقة Paper جديدة.
- ≥ 150 صفقة إجمالًا.
- نشاط Paper موزع على ≥ 3 أيام UTC.
- Strict pass rate ≥ 80%.
- Mandatory pass rate ≥ 80%.
- صفر regressions.

### L3 · 7D

- ≥ 168 ساعة.
- ≥ 35 Snapshots.
- ≥ 90 صفقة Paper جديدة.
- ≥ 200 صفقة إجمالًا.
- نشاط Paper موزع على ≥ 6 أيام UTC.
- Strict pass rate ≥ 85%.
- Mandatory pass rate ≥ 85%.
- صفر regressions.

### لماذا Active Trade Days؟

وجود 90 صفقة في يوم واحد ثم عدم وجود نشاط بقية الأسبوع لا يعتبر استقرارًا أسبوعيًا. V1.28 تحسب الأيام التي زاد فيها العدد التراكمي للصفقات المغلقة، وتفرض توزيع النشاط زمنيًا.

## حالات السلم

- `MULTIDAY_STABILITY_BLOCKED`
- `STABILITY_24H_CONFIRMED`
- `STABILITY_72H_CONFIRMED`
- `STABILITY_7D_CONFIRMED`

حتى عند `STABILITY_7D_CONFIRMED`:

- `paper_only = true`
- `automatic_real_execution = false`
- `real_execution_eligibility = false`
- `live_execution_enabled = false`
- `target_auto_apply = false`
- `guarantee = NONE`

والمرحلة التالية فقط:

`EXTENDED_MULTI_WEEK_PAPER_OBSERVATION`

## الطبقات السابقة محفوظة

- V1.24 Unified Research Readiness.
- V1.25 Strict Paper Review بنوافذ 30/60/100.
- V1.26 Research Evidence History.
- V1.27 24H Evidence Stability Window.
- V1.28 Multi‑Day Stability Ladder.

## واجهة الهاتف

- `v35.js`: Strict Paper Review.
- `v36.js`: Research Evidence History.
- `v37.js`: 24H Evidence Stability Window.
- `v38.js`: 24H → 72H → 7D Multi‑Day Ladder، ويقرأ نفس Research History دون التأثير على MASTER.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- Paper leverage القصوى الافتراضية: `5x`.
- Dynamic risk/stop/targets بين `1R` و`5R`.
- Soft Pause + hard drawdown limit.
- لا Auto Apply من أي طبقة بحثية.

## CI

GitHub Actions يفحص:

- Python compile.
- JavaScript حتى `v38.js`.
- عدم القفز بين درجات السلم.
- منع دفعة تداول في يوم واحد من اجتياز 7D.
- استمرار اختبارات V1.27 وStrict Paper وEvidence History وNo-lookahead.
- Startup + `/health`.

## المبدأ

`Market Data → 3 Brains → MASTER → Adaptive Risk → Historical Memory → OOS Validation → Unified Readiness → Strict Paper → Evidence History → 24H Stability → 72H Stability → 7D Stability → Extended Multi‑Week Paper Observation`

الهدف هو أن تُثبت المنظومة أن جودة الأدلة **مستمرة وموزعة زمنيًا**، لا ناتجة عن لقطة أو يوم تداول استثنائي واحد.