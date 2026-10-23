# BTC AI Trader V1.20

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward طويلة بما يكفي.

## المكونات الحالية

- 18 فريمًا من `1m` حتى `1Y`.
- مؤشرات فنية + Market Structure + Liquidity + Patterns + مئات Background Features.
- Cycle/Valuation Models.
- Network وDerivatives في `SHADOW_ONLY`.
- Feature Edge Lab + Incremental Walk-Forward.
- Historical Setup Memory + Analog Edge Validation.
- Long Historical Replay Memory + Historical Signature Cache.
- Historical Target Advisor لاختيار `1R→5R` تاريخيًا بشكل محافظ.
- **Target Policy Validation V1.20** لمقارنة الهدف الحالي بالهدف التاريخي على مسارات Paper قابلة للحسم.
- Adaptive paper risk/leverage، صفقة واحدة فقط، وحد حماية رأسمال تجريبي.
- Learning Journal + Backtesting + Readiness Gate.

## Target Policy Validation V1.20

V1.20 لا تفترض أن توصية Historical Target Advisor أفضل. بل تعيد تقييم الصفقات المسجلة تحت سياستين:

1. `Baseline`: هدف Risk Engine الذي استخدمته الصفقة فعليًا.
2. `Advisor`: الهدف الذي كان Historical Target Advisor سيختاره وقت الدخول.

وتطبق على كليهما نفس بنية الخروج الحالية:

- TP1: إغلاق 30%.
- TP2: إغلاق 40%.
- TP3: إغلاق 30%.
- بعد TP1 ينتقل الوقف إلى Entry.
- بعد TP2 ينتقل الوقف إلى TP1.

### منع النتائج الوهمية

- يتم تحويل MFE إلى `R` باستخدام Stop distance المسجل وقت الدخول.
- إذا كان المسار المسجل يكفي لحسم الهدف البديل، يتم حساب النتيجة.
- إذا أغلقت صفقة Paper قبل أن نعرف هل هدف أعلى كان سيُضرب لاحقًا، النتيجة تصبح `UNRESOLVED` وتُستبعد بدل تخمينها.
- يتم عرض `Resolution Coverage` حتى لا تبدو عينة ناقصة كأنها اختبار كامل.
- يوجد Holdout زمني في آخر 30% من المقارنات المحسومة.
- المقارنة تشمل Mean R وWin Rate وProfit Factor وMax Drawdown R.
- إعلان `JOURNAL_SHADOW_OUTPERFORMS` يحتاج تحسنًا في العينة والـHoldout دون زيادة Drawdown فوق الحدود.
- `auto_apply = false` و`weight_in_risk_engine = 0` دائمًا في هذه المرحلة.

هذه الطبقة **اختبار جزئي** فقط، لأن Journal لا يحتفظ بالشموع التي حدثت بعد إغلاق الصفقة. المرحلة التالية هي Full Historical Target Walk-Forward على بيانات الشموع نفسها لحسم كل المسارات.

## Historical Target Advisor

- يقارن أهداف `1R` إلى `5R` باستخدام الحالات التاريخية الأقرب.
- يستخدم Hit Rate من كامل مجموعة الحالات المتشابهة.
- Laplace smoothing يقلل الثقة الزائدة في العينة الصغيرة.
- في الوضع المحافظ يعتبر كل non-hit = `-1R`.
- يبقى `SHADOW_ONLY` ولا يغير التنفيذ.

## Historical Memory

- SCALP: تاريخ أعمق للفريمات الصغيرة والمتوسطة.
- INTRADAY: أشهر/سنوات حسب الفريم.
- SWING: عدة سنوات على 4H/1D/1W/1M حيث يتوفر.
- Signature Cache يبني حتى نحو 720 بصمة موزعة على الذاكرة المتاحة.
- No-lookahead: لا تُستخدم نقطة تاريخية إذا لم توجد بعدها Future Window كاملة.
- `STOP_FIRST_CONSERVATIVE` عند تعارض Stop وTarget في الشمعة نفسها.

## إدارة المخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة واحدة فقط.
- النظام يحدد LONG/SHORT وحجم المركز والرافعة Paper تلقائيًا.
- الرافعة الافتراضية القصوى: `5x`.
- مخاطرة Stop ديناميكية بحد أعلى افتراضي يقارب `1.4%` للفرص الأقوى.
- الأهداف الحالية من `1R` حتى `5R`.
- الحد الصلب للنموذج التجريبي: `25%` من رأس المال الابتدائي، مع Soft Pause قبل الوصول إليه.

## واجهة الهاتف

الواجهة Phone-First وتعرض كل طبقات النظام، ومنها:

- MASTER والعقول الثلاثة.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت والرسومات الفنية.
- Risk / Leverage / Targets.
- Cycle / Network / Derivatives.
- Edge Lab + Incremental Walk-Forward.
- Historical Memory + Analog Validation + Signature Cache.
- Historical Target Advisor 1R→5R.
- Target Policy Validation: Baseline vs Advisor + Coverage + Holdout.

## CI

يفحص GitHub Actions:

- Python compile.
- JavaScript syntax حتى `v30.js`.
- Unit tests، بما فيها Target Policy counterfactual logic.
- تشغيل التطبيق و`/health`.
- مزامنة النسخة والواجهة مع قدرات النظام.

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

`Market Data → Multi-Timeframe Analysis → 3 Brains → MASTER → Adaptive Risk → Historical Memory → Analog Evidence → Target Advisor → Target Policy Validation → Full OOS Replay → Journal → Readiness Gate`

الهدف ليس كثرة المؤشرات بحد ذاتها، بل استخدام Pool واسع ثم استبعاد الضوضاء والاحتفاظ فقط بما يثبت Edge إضافيًا ومستقرًا خارج العينة.
