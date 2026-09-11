#!/usr/bin/env python3
import io, json, os, time, zipfile
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

API_KEY = os.getenv("BESTCHANGE_API_KEY", "").strip()
LANG = os.getenv("BESTCHANGE_LANG", "ru").strip() or "ru"
TIMEOUT = int(os.getenv("BESTCHANGE_TIMEOUT", "30"))
CACHE_TTL = float(os.getenv("BESTCHANGE_CACHE_TTL", "3"))

V2_HOSTS = [
    "https://bestchange.app",
    "https://mirror1.bestchange.app",
    "https://mirror2.bestchange.app",
    "https://mirror3.bestchange.app",
    "https://mirror4.bestchange.app",
]
INFO_HOSTS = [
    "https://api.bestchange.com",
    "http://api.bestchange.com",
]

app = Flask(__name__)
session = requests.Session()
session.headers.update({
    "Accept": "application/json, */*",
    "Accept-Encoding": "gzip",
    "Connection": "keep-alive",
    "User-Agent": "BestChange-Data-Monitor/5.1",
})

_cache: dict[str, tuple[float, Any]] = {}


def cached(key: str, loader):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    value = loader()
    _cache[key] = (now, value)
    return value


def api_v2_get(path: str):
    if not API_KEY:
        raise RuntimeError("BESTCHANGE_API_KEY is not set")
    last = None
    for host in V2_HOSTS:
        try:
            r = session.get(f"{host}{path}", timeout=TIMEOUT)
            r.raise_for_status()
            return r.json(), host
        except Exception as exc:
            last = exc
    raise RuntimeError(f"BestChange API v2 failed: {last}")


def info_zip_get():
    """Download BestChange's official aggregate export archive."""
    last = None
    for host in INFO_HOSTS:
        try:
            r = session.get(f"{host}/info.zip", timeout=TIMEOUT)
            r.raise_for_status()
            return r.content, host
        except Exception as exc:
            last = exc
    raise RuntimeError(f"BestChange info.zip failed: {last}")


def decode_dat(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_zip_member(blob: bytes, member: str) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return decode_dat(z.read(member))


def split_lines(text: str):
    return [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]


def parse_info_currencies(blob: bytes):
    text = read_zip_member(blob, "bm_cy.dat")
    out = []
    for line in split_lines(text):
        parts = line.split(";")
        if len(parts) < 3:
            continue
        try:
            cid = int(parts[0])
        except ValueError:
            continue
        # bm_cy.dat contains id;position;name;...
        out.append({
            "id": cid,
            "name": parts[2],
            "position": int(parts[1]) if parts[1].isdigit() else None,
        })
    return out


def parse_info_changers(blob: bytes):
    text = read_zip_member(blob, "bm_exch.dat")
    out = []
    for line in split_lines(text):
        parts = line.split(";")
        if len(parts) < 2:
            continue
        try:
            eid = int(parts[0])
        except ValueError:
            continue
        out.append({
            "id": eid,
            "name": parts[1],
            "url": f"https://www.bestchange.com/click.php?id={eid}",
        })
    return out


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_info_rates(blob: bytes, from_id: int, to_id: int, city_id: int | None = None):
    text = read_zip_member(blob, "bm_rates.dat")
    rows = []
    for line in split_lines(text):
        parts = line.split(";")
        # Official legacy BestChange format:
        # 0 give_id, 1 get_id, 2 exchange_id, 3 rate_give,
        # 4 rate_get, 5 reserve, 6 reviews, 7 unused/param,
        # 8 min_sum, 9 max_sum, 10 city_id.
        if len(parts) < 11:
            continue
        try:
            give_id = int(parts[0])
            get_id = int(parts[1])
            exchange_id = int(parts[2])
            row_city = int(parts[10])
        except ValueError:
            continue
        if give_id != from_id or get_id != to_id:
            continue
        if city_id is not None and row_city != city_id:
            continue

        rate_give = num(parts[3])
        rate_get = num(parts[4])
        rate = None
        if rate_give is not None and rate_get not in (None, 0):
            rate = rate_give / rate_get

        rows.append({
            "giveId": give_id,
            "getId": get_id,
            "changerId": exchange_id,
            "rate": rate,
            "in": rate_give,
            "out": rate_get,
            "reserve": num(parts[5]),
            "reviews": num(parts[6]),
            "min": num(parts[8]),
            "max": num(parts[9]),
            "cityId": row_city,
            "raw": parts,
        })
    return rows


def normalize_v2_rows(payload: Any, from_id: int, to_id: int, city_id: int | None = None):
    """Best-effort v2 parser; legacy export is used as a guaranteed fallback."""
    found = []

    def walk(obj, inherited_id=None):
        if isinstance(obj, list):
            # Positional legacy-like row nested inside JSON.
            if len(obj) >= 11 and all(not isinstance(x, (dict, list)) for x in obj[:11]):
                try:
                    local = parse_positional(obj)
                    if local:
                        found.append(local)
                        return
                except Exception:
                    pass
            for x in obj:
                walk(x, inherited_id)
            return
        if not isinstance(obj, dict):
            return

        # If object key itself is a numeric exchanger id, carry it down.
        current_id = inherited_id
        if current_id is None:
            for key in ("changerId", "changer_id", "exchangeId", "exchange_id", "exchangerId", "exchanger_id"):
                if key in obj:
                    current_id = scalar_id(obj[key])
                    break
        if current_id is None:
            for key in ("changer", "exchange", "exchanger"):
                if key in obj:
                    current_id = scalar_id(obj[key])
                    if current_id is not None:
                        break

        # Some API shapes use currency ids in every record.
        rec_from = scalar_int(obj.get("fromCurrencyId") or obj.get("from_currency_id") or obj.get("giveId") or obj.get("give_id"))
        rec_to = scalar_int(obj.get("toCurrencyId") or obj.get("to_currency_id") or obj.get("getId") or obj.get("get_id"))
        if rec_from is not None and rec_to is not None and (rec_from != from_id or rec_to != to_id):
            pass
        else:
            rate = scalar_num(obj.get("rate") or obj.get("price") or obj.get("exchangeRate") or obj.get("exchange_rate"))
            if rate is None:
                rn = scalar_num(obj.get("rateNum") or obj.get("rate_num") or obj.get("inRate") or obj.get("in_rate"))
                rd = scalar_num(obj.get("rateDen") or obj.get("rate_den") or obj.get("outRate") or obj.get("out_rate"))
                if rn is not None and rd not in (None, 0):
                    rate = rn / rd
            in_amt = scalar_num(obj.get("in") or obj.get("input") or obj.get("fromAmount") or obj.get("from_amount") or obj.get("giveAmount") or obj.get("give_amount"))
            out_amt = scalar_num(obj.get("out") or obj.get("output") or obj.get("toAmount") or obj.get("to_amount") or obj.get("getAmount") or obj.get("get_amount"))
            if rate is None and in_amt not in (None, 0) and out_amt is not None:
                rate = out_amt / in_amt
            row_city = scalar_int(obj.get("cityId") or obj.get("city_id") or obj.get("city"))
            if city_id is None or row_city in (None, city_id):
                if current_id is not None and rate is not None:
                    found.append({
                        "giveId": rec_from or from_id,
                        "getId": rec_to or to_id,
                        "changerId": current_id,
                        "rate": rate,
                        "in": in_amt,
                        "out": out_amt,
                        "reserve": scalar_num(obj.get("reserve") or obj.get("reserveAmount") or obj.get("reserve_amount")),
                        "reviews": scalar_num(obj.get("reviews") or obj.get("reviewCount") or obj.get("review_count")),
                        "min": scalar_num(obj.get("min") or obj.get("minAmount") or obj.get("min_amount") or obj.get("minSum") or obj.get("min_sum") or obj.get("inmin") or obj.get("inMin")),
                        "max": scalar_num(obj.get("max") or obj.get("maxAmount") or obj.get("max_amount") or obj.get("maxSum") or obj.get("max_sum") or obj.get("inmax") or obj.get("inMax")),
                        "cityId": row_city,
                        "raw": obj,
                    })

        # Mapping keyed by exchanger id.
        for key, value in obj.items():
            if isinstance(key, str) and key.isdigit() and isinstance(value, (dict, list)):
                walk(value, int(key))
            else:
                if isinstance(value, (dict, list)):
                    walk(value, current_id)

    def parse_positional(vals):
        try:
            give_id, get_id, exchange_id = int(vals[0]), int(vals[1]), int(vals[2])
            if give_id != from_id or get_id != to_id:
                return None
            rg, rt = float(vals[3]), float(vals[4])
            return {
                "giveId": give_id, "getId": get_id, "changerId": exchange_id,
                "rate": rg / rt if rt else None, "in": rg, "out": rt,
                "reserve": num(vals[5]), "reviews": num(vals[6]),
                "min": num(vals[8]), "max": num(vals[9]), "cityId": int(vals[10]) if str(vals[10]).lstrip("-").isdigit() else None,
                "raw": vals,
            }
        except Exception:
            return None

    walk(payload)
    # De-duplicate exact offers.
    seen = set(); dedup = []
    for row in found:
        key = (row.get("changerId"), row.get("rate"), row.get("reserve"), row.get("min"), row.get("max"), row.get("cityId"))
        if key not in seen:
            seen.add(key); dedup.append(row)
    return dedup


def scalar_id(value):
    if isinstance(value, dict):
        for k in ("id", "changerId", "exchangeId", "exchangerId"):
            if k in value:
                return scalar_int(value[k])
        return None
    return scalar_int(value)


def scalar_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def scalar_num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/currencies")
def currencies():
    def load():
        p, host = api_v2_get(f"/v2/{API_KEY}/currencies/{LANG}")
        return {"host": host, "data": p}
    try:
        return jsonify(cached("currencies", load))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.get("/api/changers")
def changers():
    def load():
        p, host = api_v2_get(f"/v2/{API_KEY}/changers/{LANG}")
        return {"host": host, "data": p}
    try:
        return jsonify(cached("changers", load))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/rates")
def rates():
    a=request.args.get("from", type=int)
    b=request.args.get("to", type=int)
    c=request.args.get("city", type=int)
    if not a or not b:
        return jsonify({"error":"from and to are required"}),400
    token=f"{a}-{b}" + (f"-{c}" if c else "")
    try:
        p, host = api_v2_get(f"/v2/{API_KEY}/rates/{token}")
        rows = normalize_v2_rows(p, a, b, c)
        # The real v2 response is {"rates":{"A-B":[...]}}. Normalize directly too.
        if not rows and isinstance(p, dict):
            rate_map = p.get("rates")
            if isinstance(rate_map, dict):
                raw_rows = rate_map.get(token)
                if isinstance(raw_rows, list):
                    for item in raw_rows:
                        if not isinstance(item, dict):
                            continue
                        changer_id = scalar_id(item.get("changer") if "changer" in item else item.get("changerId"))
                        rate = scalar_num(item.get("rate"))
                        rank_rate = scalar_num(item.get("rankrate") or item.get("rankRate"))
                        if changer_id is None or rate is None:
                            continue
                        rows.append({
                            "giveId": a, "getId": b, "changerId": changer_id,
                            "rate": rate, "rankRate": rank_rate,
                            "reserve": scalar_num(item.get("reserve")),
                            "min": scalar_num(item.get("inmin") or item.get("min")),
                            "max": scalar_num(item.get("inmax") or item.get("max")),
                            "marks": item.get("marks") if isinstance(item.get("marks"), list) else [],
                            "extra": item.get("extra"), "raw": item,
                        })
        # Deduplicate
        unique=[]; seen=set()
        for row in rows:
            k=(row.get("changerId"), row.get("rate"), row.get("reserve"), row.get("min"), row.get("max"))
            if k not in seen:
                seen.add(k); unique.append(row)
        unique.sort(key=lambda r: (r.get("rankRate") if r.get("rankRate") is not None else r.get("rate", 0)), reverse=True)
        return jsonify({"pair":token,"from":a,"to":b,"city":c,"host":host,"source":"BestChange API v2","count":len(unique),"rates":unique})
    except Exception as e:
        return jsonify({"error":str(e),"pair":token}),502

@app.get("/api/presences")
def presences():
    a=request.args.get("from",type=int); b=request.args.get("to",type=int); c=request.args.get("city",type=int)
    if not a or not b: return jsonify({"error":"from and to are required"}),400
    token=f"{a}-{b}" + (f"-{c}" if c else "")
    try:
        p,host=api_v2_get(f"/v2/{API_KEY}/presences/{token}")
        return jsonify({"from":a,"to":b,"city":c,"host":host,"raw":p})
    except Exception as e:
        return jsonify({"error":str(e),"pair":token}),502

@app.get("/api/debug/rates")
def debug_rates():
    a=request.args.get("from",type=int); b=request.args.get("to",type=int); c=request.args.get("city",type=int)
    if not a or not b: return jsonify({"error":"from and to are required"}),400
    token=f"{a}-{b}" + (f"-{c}" if c else "")
    result={"pair":token}
    try:
        p,host=api_v2_get(f"/v2/{API_KEY}/rates/{token}")
        result.update({"host":host,"type":type(p).__name__,"keys":list(p.keys())[:50] if isinstance(p,dict) else [],"normalized_count":len(normalize_v2_rows(p,a,b,c)),"sample":(p[:3] if isinstance(p,list) else p)})
    except Exception as e:
        result["error"]=str(e)
    return jsonify(result)


@app.get("/api/health")
def health():
    return jsonify({"ok":bool(API_KEY),"lang":LANG,"cacheTtl":CACHE_TTL})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
