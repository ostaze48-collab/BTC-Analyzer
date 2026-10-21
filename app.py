from __future__ import annotations
import csv, io, json, os, threading
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request, Response

from engine import Engine

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))

app=Flask(__name__,static_folder=None)
engine=Engine(ROOT,CFG)
threading.Thread(target=engine.run,daemon=True).start()

@app.get("/")
def home():
    return send_from_directory(ROOT/"static","dashboard.html")

@app.get("/static/<path:name>")
def static_file(name):
    return send_from_directory(ROOT/"static",name)

@app.get("/api/state")
def state():
    return jsonify(engine.snapshot())

@app.get("/health")
def health():
    s=engine.snapshot()
    return jsonify({
        "ok":s.get("status") in ("OK","DEGRADED"),
        "status":s.get("status"),
        "engine_version":s.get("engine_version"),
        "last_error":(s.get("health") or {}).get("last_error"),
        "last_success_age_sec":(s.get("health") or {}).get("last_success_age_sec"),
    })

@app.post("/api/paper/capital")
def set_paper_capital():
    return jsonify({
        "ok":False,"fixed":True,"start_balance":1000.0,
        "error":"Paper capital is permanently fixed at $1,000 in V2.8."
    }),403


@app.get("/api/paper/trades.csv")
def paper_trades_csv():
    rows=engine.paper.export_rows()
    if not rows:
        return Response("no data\n",mimetype="text/csv")
    buf=io.StringIO()
    w=csv.DictWriter(buf,fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=paper_{engine.paper.get_experiment_id()}.csv"
        }
    )


@app.get("/diag")
def diag():
    s=engine.snapshot()
    return jsonify({
        "app":"BTC Analyzer V2.8",
        "status":s.get("status"),
        "price":s.get("price"),
        "best_setup":(s.get("decision") or {}).get("best_setup"),
        "pnl":s.get("pnl"),
        "health":s.get("health"),
    })

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")),threaded=True)
