# BTC AI Trader V2.0 STABLE

نسخة **Stable Experiment** مخصصة للتجربة وقياس النتائج على Paper Trading بدون تغيير منطق العقول أثناء فترة القياس.

> التداول الحقيقي معطّل. V2.0 STABLE للقياس والبحث فقط، ولا تعني أن الاستراتيجية مربحة أو جاهزة لاستخدام أموال حقيقية.

## هدف النسخة

- تجميد منطق التداول الحالي بدل إضافة ميزات أثناء الاختبار.
- تشغيل `SCALP / INTRADAY / SWING` مع `MASTER` وصفقة واحدة فقط.
- الاحتفاظ بكل قدرات V1.28 البحثية، لكن وضعها في شاشة **البحث** بدل ازدحام الشاشة الرئيسية.
- واجهة هاتف حديثة من أربع شاشات: **الرئيسية / الشارت / النتائج / البحث**.
- حفظ نتائج كل تجربة ومقارنتها بالتجارب السابقة.
- الاحتفاظ بنسخة محلية احتياطية على الهاتف وإمكانية تصدير JSON.

## نتائج التجربة

لوحة النتائج تعرض:

- رأس المال الحالي وNet P/L.
- عدد الصفقات وWin Rate.
- Profit Factor وMax Drawdown.
- Equity Curve حسب الصفقات المغلقة.
- Expectancy وAvg R وNet R في Snapshot الخادمي.
- أداء كل عقل: عدد الصفقات، P/L، Win Rate، Profit Factor وAvg R.
- أداء كل Market Regime داخل Snapshot المحفوظ.
- سجل التجارب السابقة مع إمكانية فتح تفاصيل كل تجربة.

## الأرشيف الدائم

V2.0 تضيف `ExperimentArchive` مستقلًا عن محرك التداول.

- محليًا وداخل CI يستخدم SQLite fallback.
- على Render يستخدم `DATABASE_URL` للاتصال بـPostgres.
- Postgres يحفظ التجارب عبر إعادة نشر أو إعادة إنشاء حاوية الويب.
- فشل الأرشيف لا يوقف Market Data أو Paper Trading؛ تظهر حالة التخزين في الواجهة بدل إسقاط التطبيق.
- الضغط على **حفظ النتائج** يحفظ Snapshot خادميًا.
- الضغط على **تجربة جديدة** يحفظ التجربة الحالية أولًا، ثم يصفر Paper Trading وResearch History لبدء حقبة نظيفة.
- زر Reset القديم في واجهة Stable يتم استبداله بسلوك **حفظ وبدء تجربة جديدة**.
- يبقى `localStorage` نسخة احتياطية على الهاتف فقط، وليس المصدر الأساسي للأرشيف.

### API

- `GET /api/experiment/current`
- `GET /api/experiments?limit=20`
- `POST /api/experiment/archive?label=...`
- `POST /api/experiment/new?label=...`

## تصميم الهاتف

- Dark Glass / Gradient بتباين واضح.
- شريط تنقل سفلي من 4 أقسام فقط.
- KPIs كبيرة مناسبة للمس.
- الشارت في شاشة مستقلة لتوفير مساحة أكبر.
- النتائج في شاشة مستقلة مع Equity Curve وسجل التجارب.
- البحث المتقدم في شاشة منفصلة مع بقاء كل طبقات V1.28 متاحة.
- الواجهة تحفظ آخر تبويب فتحه المستخدم.

## المحرك المثبت

منطق التداول الأساسي لم يتغير عن V1.28:

- 18 فريم من `1m` حتى `1Y`.
- 3 Brains + MASTER.
- Adaptive Paper Risk.
- صفقة واحدة فقط.
- أهداف ديناميكية `1R → 5R`.
- Historical Memory.
- Feature Edge / Incremental Walk-Forward.
- Historical Target Advisor.
- Frozen-entry Shadow Validation.
- Unified Readiness.
- Strict Paper Review.
- Research Evidence History.
- 24H → 72H → 7D Stability Ladder.

## إدارة المخاطرة

- رأس المال الافتراضي: `$1,000`.
- Real execution = OFF.
- Paper leverage القصوى الافتراضية: `5x`.
- Soft Pause قبل حد الخسارة الكلي.
- Hard model drawdown limit = `25%` من رأس المال الابتدائي.
- لا Auto Apply من طبقات البحث.

## CI

GitHub Actions يفحص قبل الدمج:

- Python compile.
- JavaScript لجميع الطبقات حتى `v38.js` و`stable.js`.
- Unit tests لجميع طبقات البحث والمخاطرة السابقة.
- اختبار بناء Snapshot: Equity / Avg R / Net R / Brain breakdown.
- اختبار حفظ واسترجاع Experiment Archive في SQLite fallback.
- اختبار أن Stable UI تستخدم API الأرشيف الخادمي مع Local backup.
- Startup + `/health`.

## قاعدة القياس

أثناء تجربة V2.0 STABLE لا نغيّر أوزان العقول أو قواعد الدخول والخروج على `main`. أي فكرة جديدة يجب أن تبقى في فرع Research منفصل، ثم نقارن نتائجها مع التجارب المؤرشفة قبل إدخالها إلى النسخة المستقرة.
