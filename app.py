from __future__ import annotations
import json, os, threading
from pathlib import Path
from flask import Flask, jsonify, render_template
from engine import Engine

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
app=Flask(__name__)
engine=Engine(ROOT,CFG)
threading.Thread(target=engine.run,daemon=True).start()

@app.get("/")
def home(): return render_template("index.html")
@app.get("/health")
def health():
    s=engine.snapshot()
    return jsonify({"ok":s.get("status")!="ERROR","status":s.get("status")})
@app.get("/api/state")
def state(): return jsonify(engine.snapshot())

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")),threaded=True)
