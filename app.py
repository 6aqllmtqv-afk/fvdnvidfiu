#!/usr/bin/env python3
import os, json, re, time
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import requests

load_dotenv()
BASE_HOSTS = [
    "https://bestchange.app",
    "https://mirror1.bestchange.app",
    "https://mirror2.bestchange.app",
    "https://mirror3.bestchange.app",
    "https://mirror4.bestchange.app",
]
KEY = os.getenv("BESTCHANGE_API_KEY", "").strip()
LANG = os.getenv("BESTCHANGE_LANG", "ru")
TIMEOUT = int(os.getenv("BESTCHANGE_TIMEOUT", "30"))

app = Flask(__name__)
session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "Connection": "keep-alive",
    "User-Agent": "BestChangeDataCollector-Web/1.0",
})

cache = {}
CACHE_TTL = int(os.getenv("BESTCHANGE_CACHE_TTL", "1"))

def api_get(path):
    if not KEY:
        raise RuntimeError("BESTCHANGE_API_KEY is not set")
    last = None
    for host in BASE_HOSTS:
        try:
            r = session.get(host + path, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json(), host
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))

def listify(payload, preferred=(), keep_non_dict=False):
    """Convert BestChange API collections into a list.

    Supports JSON arrays, wrapped arrays/objects, ID-keyed objects, and
    positional list records used by some BestChange API/export variants.
    """
    if isinstance(payload, list):
        return payload if keep_non_dict else [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, tuple):
        return list(payload) if keep_non_dict else [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    keys = tuple(preferred) + (
        "data", "items", "result", "currencies", "changers", "groups",
        "countries", "cities", "presences", "rates", "exchangeRates",
        "rows", "list", "values"
    )

    for k in keys:
        if k not in payload:
            continue
        v = payload[k]
        if isinstance(v, (list, tuple)):
            return list(v) if keep_non_dict else [x for x in v if isinstance(x, dict)]
        if isinstance(v, dict):
            vals = list(v.values())
            if vals:
                return vals if keep_non_dict else [x for x in vals if isinstance(x, dict)]
            nested = listify(v, keep_non_dict=keep_non_dict)
            if nested:
                return nested

    vals = list(payload.values())
    if vals:
        return vals if keep_non_dict else [x for x in vals if isinstance(x, dict)]
    return []

def pick(o, *keys, default=None):
    for k in keys:
        if isinstance(o, dict) and k in o and o[k] is not None:
            return o[k]
    return default

def cached(key, loader):
    now = time.time()
    item = cache.get(key)
    if item and now - item[0] < CACHE_TTL:
        return item[1]
    value = loader()
    cache[key] = (now, value)
    return value

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/currencies")
def currencies():
    def load():
        p, host = api_get(f"/v2/{KEY}/currencies/{LANG}")
        rows = listify(p, ("currencies",))
        out = []
        for x in rows:
            cid = pick(x, "id", "currencyId")
            if cid is None: continue
            name = pick(x, "name", "title", "code", default=str(cid))
            if isinstance(name, dict):
                name = name.get(LANG) or name.get("ru") or name.get("en") or next(iter(name.values()), str(cid))
            out.append({
                "id": int(cid),
                "name": str(name),
                "code": str(pick(x, "code", "symbol", default="") or ""),
                "groupId": pick(x, "groupId", "group_id"),
                "raw": x,
            })
        return {"host": host, "items": out}
    try: return jsonify(cached("currencies", load))
    except Exception as e: return jsonify({"error": str(e)}), 502

@app.get("/api/changers")
def changers():
    def load():
        p, host = api_get(f"/v2/{KEY}/changers/{LANG}")
        rows = listify(p, ("changers",))
        out=[]
        for x in rows:
            cid=pick(x,"id","changerId")
            if cid is None: continue
            name = pick(x, "name", "title", default=str(cid))
            if isinstance(name, dict):
                name = name.get(LANG) or name.get("ru") or name.get("en") or next(iter(name.values()), str(cid))
            out.append({"id":int(cid),"name":str(name),"url":str(pick(x,"url","site","website",default="") or ""),"raw":x})
        return {"host": host, "items": out}
    try: return jsonify(cached("changers", load))
    except Exception as e: return jsonify({"error": str(e)}), 502

def normalize_rate(row):
    """Normalize BestChange rate records.

    BestChange API rate records can be JSON objects or positional arrays.
    The positional layout matches the long-standing BestChange rate export:
    give_id, get_id, exchange_id, rate_num, rate_den, reserve, reviews,
    ..., min_sum, max_sum, city_id.
    """
    if isinstance(row, (list, tuple)):
        vals = list(row)
        while len(vals) < 11:
            vals.append(None)
        give_id, get_id, exchange_id = vals[0], vals[1], vals[2]
        try:
            rate = float(vals[3]) / float(vals[4]) if vals[3] not in (None, '') and vals[4] not in (None, '', 0) else None
        except (TypeError, ValueError, ZeroDivisionError):
            rate = None
        return {
            "giveId": give_id,
            "getId": get_id,
            "changerId": exchange_id,
            "rate": rate,
            "in": None,
            "out": None,
            "reserve": vals[5],
            "reviews": vals[6],
            "min": vals[8],
            "max": vals[9],
            "cityId": vals[10],
            "fromFee": None,
            "toFee": None,
            "fee": None,
            "param": vals[7],
            "updatedAt": None,
            "raw": row,
        }

    if not isinstance(row, dict):
        return {"changerId": None, "rate": None, "raw": row}

    changer_id = pick(row,
        "changerId", "changer_id", "exchangeId", "exchange_id", "exchange", "changer", "id")
    input_amount = pick(row, "in", "input", "give", "fromAmount", "from_amount", "giveAmount", "give_amount")
    output_amount = pick(row, "out", "output", "get", "toAmount", "to_amount", "getAmount", "get_amount")
    rate = pick(row, "rate", "price", "exchangeRate", "exchange_rate", "perc")
    if rate is None:
        numerator = pick(row, "rateNum", "rate_num", "inRate", "in_rate")
        denominator = pick(row, "rateDen", "rate_den", "outRate", "out_rate")
        if numerator not in (None, '') and denominator not in (None, '', 0):
            try:
                rate = float(numerator) / float(denominator)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    if rate is None and input_amount not in (None, '', 0) and output_amount not in (None, ''):
        try:
            rate = float(output_amount) / float(input_amount)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    return {
        "giveId": pick(row, "giveId", "give_id", "fromCurrencyId", "from_currency_id"),
        "getId": pick(row, "getId", "get_id", "toCurrencyId", "to_currency_id"),
        "changerId": changer_id,
        "rate": rate,
        "in": input_amount,
        "out": output_amount,
        "reserve": pick(row, "reserve", "amount", "reserveAmount", "reserve_amount"),
        "reviews": pick(row, "reviews", "review", "reviewCount", "review_count"),
        "min": pick(row, "min", "minAmount", "min_amount", "minSum", "min_sum", "inmin", "inMin", "in_min"),
        "max": pick(row, "max", "maxAmount", "max_amount", "maxSum", "max_sum", "inmax", "inMax", "in_max"),
        "cityId": pick(row, "cityId", "city_id"),
        "fromFee": pick(row, "fromFee", "from_fee"),
        "toFee": pick(row, "toFee", "to_fee"),
        "fee": pick(row, "fee"),
        "param": pick(row, "param", "parameters", "memo", "tag"),
        "updatedAt": pick(row, "updatedAt", "updated_at", "timestamp"),
        "raw": row,
    }

@app.get("/api/rates")
def rates():
    a = request.args.get("from", type=int)
    b = request.args.get("to", type=int)
    c = request.args.get("city", type=int)
    if not a or not b:
        return jsonify({"error": "from and to are required"}), 400
    token = f"{a}-{b}" + (f"-{c}" if c else "")

    def load():
        p, host = api_get(f"/v2/{KEY}/rates/{token}")
        rows = listify(p, ("rates", "exchangeRates"), keep_non_dict=True)
        normalized = [normalize_rate(x) for x in rows]
        # Drop entries which cannot identify an exchanger at all; these are
        # usually metadata/wrapper records rather than offers.
        normalized = [x for x in normalized if x.get("changerId") is not None]
        normalized = [x for x in normalized if x.get("rate") is not None]
        return {
            "from": a, "to": b, "city": c, "host": host,
            "count": len(normalized), "rates": normalized,
            "raw": p,
            "raw_type": type(p).__name__,
            "raw_keys": list(p.keys())[:30] if isinstance(p, dict) else []
        }

    try:
        return jsonify(cached("rates:" + token, load))
    except Exception as e:
        return jsonify({"error": str(e), "pair": token}), 502

@app.get("/api/debug/rates")
def debug_rates():
    a = request.args.get("from", type=int)
    b = request.args.get("to", type=int)
    c = request.args.get("city", type=int)
    if not a or not b:
        return jsonify({"error": "from and to are required"}), 400
    token = f"{a}-{b}" + (f"-{c}" if c else "")
    try:
        p, host = api_get(f"/v2/{KEY}/rates/{token}")
        return jsonify({
            "pair": token,
            "host": host,
            "type": type(p).__name__,
            "keys": list(p.keys()) if isinstance(p, dict) else [],
            "sample": (p[:3] if isinstance(p, list) else p),
        })
    except Exception as e:
        return jsonify({"error": str(e), "pair": token}), 502

@app.get("/api/presences")
def presences():
    a=request.args.get("from", type=int); b=request.args.get("to", type=int); c=request.args.get("city", type=int)
    if not a or not b: return jsonify({"error":"from and to are required"}),400
    token=f"{a}-{b}" + (f"-{c}" if c else "")
    try:
        p,host=api_get(f"/v2/{KEY}/presences/{token}")
        return jsonify({"from":a,"to":b,"city":c,"host":host,"items":listify(p,("presences",)),"raw":p})
    except Exception as e: return jsonify({"error":str(e)}),502

@app.get("/api/health")
def health():
    return jsonify({"ok":bool(KEY),"lang":LANG,"cacheTtl":CACHE_TTL})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")),debug=False)
