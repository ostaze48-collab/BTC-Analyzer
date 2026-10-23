# BTC AI Trader V1.18

منظومة بحث ومحاكاة **Paper Trading فقط** لتحليل BTCUSDT عبر ثلاثة عقول مترابطة: `SCALP` و`INTRADAY` و`SWING`، ثم اختيار صفقة واحدة بواسطة `MASTER`.

> التداول الحقيقي معطّل. لا يتم الانتقال إليه إلا بعد اجتياز Readiness Gate واختبارات Out-of-Sample/Walk-Forward وShadow/Paper طويلة بما يكفي. النتائج التاريخية ليست ضمانًا للأرباح المستقبلية.

## المنظومة الحالية

- قراءة 18 فريمًا من `1m` حتى `1Y`، مع طبقات Micro / Intraday / Swing / Macro.
- مئات Background Features في الخادم، مع منع الخصائص المترابطة من التحول إلى أصوات مستقلة.
- EMA/RSI/MACD/ATR/VWAP/Volume/Volatility، Support/Resistance، Swing، BOS/CHoCH، FVG، Order Blocks، Liquidity Sweeps، Trend Channels، Candlestick وClassical Patterns.
- Cycle/Valuation: Power Law، HPR/Rainbow، Mayer، Pi Cycle، 4-Year SMA.
- Network Intelligence وDerivatives Intelligence في `SHADOW_ONLY`.
- Feature Edge Lab + Incremental Walk-Forward بدل ترقية أي مؤشر لمجرد نجاحه على عينة واحدة.
- Historical Setup Memory + Analog Edge Validation.
- Long Historical Replay Memory تُحمّل Lazy حسب العقل وتوسع التاريخ لسنوات حيث يلزم.
- **Candidate Evidence Matrix V1.18** تقرأ المرشحين الثلاثة تاريخيًا في نفس اللحظة بدل فحص الفائز فقط.
- Learning Journal يحفظ Features/Regime/MFE/MAE وHistorical Evidence مع نتيجة الصفقة.
- Adaptive Position Size / Leverage / 1R→5R، صفقة واحدة فقط، Soft Pause قبل حد الخسارة الصلب 25% في نموذج Paper.

## Candidate Evidence Matrix V1.18

عند كل تحليل، تظل العقول الثلاثة ظاهرة حتى إذا كان أحدها `WAIT`. لكل عقل تعرض المنظومة:

- الاتجاه وAnchor timeframe.
- Confidence / Safety / Final Score / R:R / EV.
- حالة Risk Gate.
- عدد الحالات التاريخية المشابهة.
- متوسط التشابه.
- Stop-before-1R.
- نسب الوصول إلى `1R / 2R / 3R / 4R / 5R`.
- سجل أداء نفس العقل داخل نفس Market Regime: عدد الصفقات وWin Rate وProfit Factor.
- حالة Long Historical Archive وعدد الشموع المحملة.
- Evidence Score بحثي لترتيب قوة الأدلة فقط.

تظهر الواجهة بوضوح الفرق بين:

- **MASTER الحالي**: الاختيار الفعلي لمحرك القواعد/المخاطرة.
- **الأقوى تاريخيًا Shadow**: العقل الذي تظهر له أدلة تاريخية أقوى.

الاثنان لا يُدمجان تلقائيًا. `Candidate Evidence Matrix` وزنها في MASTER يظل `0` حتى يثبت Full-engine OOS أن استخدامها يحسن النتائج بدون زيادة غير مقبولة في Drawdown.

## هل بيانات الشارت السابقة مفيدة فعلًا؟

لا تعتبر المنظومة مجرد التشابه التاريخي دليلاً كافيًا. البيانات تمر عبر:

1. Historical Analog search.
2. Edge Lab بفصل زمني Train/Test.
3. Incremental Walk-Forward: Baseline مقابل Baseline + feature/filter.
4. Shadow-only observation.
5. Full-engine OOS replay لاحقًا.
6. Paper/Shadow confirmation.
7. Readiness Gate.

واجهة V1.18 تعرض `Analog Validation Status` بجانب مصفوفة العقول، لذلك يمكن التفريق بين “وجدنا حالات مشابهة” و“ثبت أن هذه المعلومات حسنت الاختيار خارج العينة”.

## Long Historical Replay Memory

التحميل Lazy ولا يحمّل كل تاريخ Bitcoin عند startup:

- `SCALP`: تاريخ أعمق لـ5m/15m/1H/4H/1D.
- `INTRADAY`: 15m حتى 1W.
- `SWING`: 4H/1D/1W/1M لسنوات حيث يتوفر.

الأرشيف يعمل بالخلفية، يُخزن مؤقتًا، يُدمج مع الشموع الحالية بدون timestamps مكررة، ويستمر بحالة `PARTIAL` إذا فشل مصدر جزئي.

## إدارة الصفقة والمخاطرة

- رأس المال التجريبي: `$1,000`.
- صفقة نشطة واحدة فقط.
- النظام يحدد LONG/SHORT والحجم والرافعة Paper تلقائيًا.
- الرافعة القصوى الافتراضية: `5x`.
- Stop-risk ديناميكي، بحد أعلى افتراضي يقارب `1.4%` في الفرص الأقوى.
- أهداف ديناميكية من `1R` إلى `5R`.
- تخفيض المخاطرة مع Drawdown.
- توقف وقائي عن فتح صفقات جديدة قرب `23%` تراجع.
- Hard floor نموذجي عند `25%` من رأس المال الابتدائي.

في التداول الحقيقي لا يمكن ضمان 25% بدقة بسبب gaps/slippage/liquidation/exchange failures، لذلك Real Execution يبقى معطلًا.

## واجهة الهاتف

Phone-First وتعرض:

- MASTER ورأس المال والقفل.
- العقول الثلاثة.
- **مقارنة العقول قبل الصفقة Historical Evidence Matrix** بالسحب على الهاتف.
- كل الفريمات من الدقيقة إلى السنة.
- الشارت الذكي والرسومات.
- Adaptive Risk/Leverage.
- Cycle / Network / Derivatives.
- Historical Setup Memory وAnalog Validation.
- Long Historical Archive.
- Feature Edge Lab / Incremental Walk-Forward.
- Learning Journal / Backtest / سجل الصفقات.

## مزامنة التطوير

V1.18 تضيف `System Manifest` مركزيًا. قاعدة المشروع هي:

`Logic + Replay + Journal + API + UI + Tests + Version` تتحدث معًا في نفس PR.

CI يتحقق من أن كل ملفات الواجهة المسجلة في الـManifest محملة مرة واحدة، كل الفريمات موجودة، رقم الإصدار متزامن، JavaScript صالح، Python قابل للـcompile، Unit Tests ناجحة، والتطبيق يقلع ويجيب `/health`.

## التشغيل محليًا

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

ثم:

```bash
pip install -r requirements.txt
python run.py
```

وافتح `http://127.0.0.1:8000`.

## Environment Variables الأساسية

```text
BTC_SYMBOL=BTCUSDT
PAPER_START_CAPITAL=1000
PAPER_FEE_RATE=0.001
MIN_CONFIDENCE=65
MIN_SAFETY_SCORE=68
MIN_RR=1.5
MAX_STOP_PCT=2.5
MAX_PAPER_LEVERAGE=5
MAX_RISK_PER_TRADE=0.014
MAX_TOTAL_DRAWDOWN=0.25
SOFT_PAUSE_DRAWDOWN=0.23
```

## مبدأ المشروع

`Market Data → 1m→1Y Analysis → 3 Brains → MASTER → Adaptive Risk → One Trade → Historical Evidence for ALL Brains → OOS Validation → Journal → Walk-Forward Learning → Readiness Gate`

الهدف ليس جمع أكبر عدد ممكن من المؤشرات وإعطائها نفس الوزن؛ الهدف إنشاء Feature Pool واسع ثم الاحتفاظ فقط بما يثبت Edge إضافيًا ومستقرًا خارج العينة.
