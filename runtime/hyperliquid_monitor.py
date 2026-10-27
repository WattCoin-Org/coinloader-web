#!/usr/bin/env python3
"""Hyperliquid Perps, Funding & Liquidation Risk Monitor (strictly read-only, stdlib + bot_common).

Reads public telemetry from the unauthenticated Hyperliquid L1 Info endpoint (POST https://api.hyperliquid.xyz/info)
or an --offline fixture and reports:

* wallet / subaccount perp risk: margin utilisation, effective leverage, per-position liquidation distance, position
  concentration, adverse funding carry, stop-loss (reduceOnly trigger) coverage and HIP-1 spot balances;
* market-wide funding APR, mark-vs-oracle basis, open interest / volume turnover and cross-venue predicted funding
  (Hyperliquid vs Binance vs Bybit, interval-normalised) with sign-flip detection;
* vault posture (HLP or any vault): leader skin, deposits / closure, account-value drawdown and the vault's own
  (and child sub-vaults') positions.

It never calls /exchange, never signs anything and refuses private keys, seed phrases, WIF / xprv and API tokens.
Exit codes: 0 clean, 1 MEDIUM, 2 HIGH, 3 CRITICAL, 10 bad input / refusal, 11 degraded data source.

Offline fixture (JSON): {"metaAndAssetCtxs": [...], "predictedFundings": [...],
"clearinghouseState": {addr: {...}}, "spotClearinghouseState": {addr: {...}}, "frontendOpenOrders": {addr: [...]},
"vaultDetails": {addr: {...} | null}} using the same shapes as the live Info endpoint (addresses lower-case).
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))


def _make_fallback_bc():
    """Minimal inline stand-in for lib/bot_common.py so the script also works standalone."""
    import datetime
    import tempfile
    import time
    import urllib.error
    import urllib.request

    m = types.SimpleNamespace()
    m.USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) BotCommon/1.0"
    m.SEV = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    m.EXIT_OK, m.EXIT_MEDIUM, m.EXIT_HIGH, m.EXIT_CRITICAL, m.EXIT_USAGE, m.EXIT_DEGRADED = 0, 1, 2, 3, 10, 11
    sev_exit = {"MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

    def utc_now():
        return datetime.datetime.now(datetime.timezone.utc)

    class HttpResult:
        def __init__(self, status, data=None, error=None, headers=None, attempts=1, raw=b""):
            self.status, self.data, self.error = status, (data if data is not None else {}), error
            self.headers, self.attempts, self.raw = headers or {}, attempts, raw

        @property
        def ok(self):
            return 200 <= self.status < 300

    def _parse(raw):
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        try:
            return json.loads(text)
        except ValueError:
            return {"_raw": text[:300]}

    def http_json(url, body=None, headers=None, retries=4, backoff=0.5, timeout=20, method=None):
        hdrs = {"User-Agent": m.USER_AGENT, "Accept": "application/json"}
        hdrs.update(headers or {})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if data is not None:
            hdrs.setdefault("Content-Type", "application/json")
        last = HttpResult(-1, error="no attempt")
        for attempt in range(1, retries + 2):
            try:
                req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()[:2_000_000]
                    return HttpResult(r.status, _parse(raw), attempts=attempt, raw=raw)
            except urllib.error.HTTPError as e:
                raw = e.read() if e.fp else b""
                last = HttpResult(e.code, _parse(raw), error="HTTP %d" % e.code, attempts=attempt)
                if e.code != 429 and e.code < 500:
                    return last
            except Exception as e:  # noqa: BLE001 - URLError, timeouts, resets
                last = HttpResult(-1, {"_error": str(e)}, error=str(e), attempts=attempt)
            if attempt <= retries:
                time.sleep(backoff * (2 ** (attempt - 1)))
        return last

    class Finding:
        def __init__(self, sev, code, msg, evidence=None, key=None):
            if sev not in m.SEV:
                raise ValueError("bad severity %r" % (sev,))
            self.sev, self.code, self.msg, self.evidence, self.key = sev, code, msg, evidence or {}, key or code

        def to_dict(self):
            return {"sev": self.sev, "code": self.code, "key": self.key, "msg": self.msg, "evidence": self.evidence}

        @classmethod
        def from_dict(cls, d):
            return cls(d["sev"], d["code"], d.get("msg", ""), d.get("evidence"), d.get("key"))

        def __repr__(self):
            return "Finding(%s %s)" % (self.sev, self.key)

    def sort_findings(findings):
        return sorted(findings, key=lambda f: (-m.SEV[f.sev], f.code, f.key))

    def exit_code(findings, degraded=False, fail_on="medium"):
        threshold = m.SEV[fail_on.upper()]
        worst = max(findings, key=lambda f: m.SEV[f.sev], default=None)
        if worst is not None and m.SEV[worst.sev] >= threshold and worst.sev in sev_exit:
            return sev_exit[worst.sev]
        return 11 if degraded else 0

    def snapshot_header(tool, endpoints=None, fallbacks=None, now=None):
        now = now or utc_now()
        lines = ["snapshot   %s | tool=%s" % (now.strftime("%Y-%m-%d %H:%M:%S UTC"), tool)]
        if endpoints:
            lines.append("endpoints  " + ", ".join(sorted(endpoints)))
        if fallbacks:
            lines.append("fallbacks  " + ", ".join(fallbacks))
        return "\n".join(lines)

    class StateStore:
        def __init__(self, path):
            self.path = path

        def load(self):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, ValueError):
                return {"schema": 1, "items": {}}
            if not isinstance(doc, dict) or doc.get("schema") != 1 or not isinstance(doc.get("items"), dict):
                return {"schema": 1, "items": {}}
            return doc

        def get(self, name):
            return self.load()["items"].get(name)

        def put(self, name, snapshot):
            doc = self.load()
            doc["items"][name] = snapshot
            d = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".state-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)

    def diff_findings(old, new):
        def norm(items):
            return {f.key: f for f in (Finding.from_dict(i) if isinstance(i, dict) else i for i in items)}

        new_m, old_m = norm(new), (norm(old) if old is not None else {})
        res = {"NEW": [], "CHANGED": [], "RESOLVED": []}
        for k in sorted(new_m):
            if k not in old_m:
                res["NEW"].append(new_m[k])
            elif (old_m[k].sev, old_m[k].msg) != (new_m[k].sev, new_m[k].msg):
                res["CHANGED"].append(new_m[k])
        res["RESOLVED"] = [old_m[k] for k in sorted(old_m) if k not in new_m]
        return res

    m.utc_now, m.HttpResult, m.http_json, m.Finding = utc_now, HttpResult, http_json, Finding
    m.sort_findings, m.exit_code, m.snapshot_header = sort_findings, exit_code, snapshot_header
    m.StateStore, m.diff_findings = StateStore, diff_findings
    return m


try:
    import bot_common as bc  # noqa: E402
except ImportError:
    bc = _make_fallback_bc()

TOOL = "hyperliquid-monitor"
INFO_URL = "https://api.hyperliquid.xyz/info"
SCOPE_NOTE = ("SCOPE_NOTE: Strictly read-only, keyless and non-custodial: the only network call is the public, "
              "unauthenticated POST https://api.hyperliquid.xyz/info endpoint (metaAndAssetCtxs, predictedFundings, "
              "clearinghouseState, spotClearinghouseState, frontendOpenOrders, vaultDetails) or an --offline fixture. "
              "It never calls /exchange, never places, cancels or modifies orders, never signs or broadcasts orders, "
              "withdrawals or transfers, and never accepts private keys, API wallet keys, seed phrases, WIF/xprv or "
              "API tokens. Liquidation prices are point-in-time clearinghouse estimates that shift with mark price, "
              "funding payments and cross-margin PnL of other positions; funding, basis and predicted cross-venue "
              "rates change every hour and \"no findings\" never means \"safe\". No financial, trading, leverage or "
              "investment advice. Refuses: secret/key input, order placement or signing, and targeting third-party "
              "accounts for liquidation hunting or exploitation.")

HLP_VAULT = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
PROTOCOL_VAULTS = {HLP_VAULT: "Hyperliquidity Provider (HLP)"}
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TICKER_RE = re.compile(r"^[A-Za-z0-9]{1,15}$")
HOURS_PER_YEAR = 24 * 365
DEFAULT_INTERVAL = {"HlPerp": 1, "BinPerp": 8, "BybitPerp": 8}
VENUES = ("HlPerp", "BinPerp", "BybitPerp")
VENUE_LABEL = {"HlPerp": "Hyperliquid", "BinPerp": "Binance", "BybitPerp": "Bybit"}
MAX_CHILD_ACCOUNTS = 10
EXTREMES_MIN_OI_USD = 1_000_000
CONCENTRATION_SHARE = 0.75
CONCENTRATION_EQUITY_MULT = 5.0
CROSS_VENUE_APR_SPREAD = 50.0
FUNDING_SHIFT_APR = 50.0
LIQ_TIGHTEN_PP = 5.0
MARGIN_SPIKE_PP = 15.0
SIZE_CHANGE_REL = 0.10
FAIL_ON = ("critical", "high", "medium", "low", "info", "none")


# ---------------------------------------------------------------- secret / signing refusal
_B58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
_XPRV_PREFIXES = ("xprv", "yprv", "zprv", "Yprv", "Zprv", "tprv", "uprv", "vprv", "Uprv", "Vprv")
_TOKEN_PREFIXES = ("sk-", "wck_", "wcl_", "hl_")
_SEED_COUNTS = (12, 15, 18, 21, 24)
_REFUSED_FLAGS = ("--private-key", "--privkey", "--priv-key", "--secret", "--secret-key", "--seed", "--seed-phrase",
                  "--mnemonic", "--api-key", "--api-secret", "--api-wallet", "--agent-key", "--key", "--sign",
                  "--wif", "--xprv", "--passphrase", "--order", "--place-order", "--withdraw", "--transfer")
_PATH_FLAGS = ("--state", "--out", "--offline")
_VALUE_FLAGS = _PATH_FLAGS + ("--format", "--fail-on", "--top", "--timeout", "--liq-crit-pct", "--liq-warn-pct",
                              "--margin-util-warn", "--funding-apr-warn", "--basis-warn-bps")
REFUSAL = ("REFUSED: hyperliquid-monitor is strictly read-only and keyless. It never accepts private keys, API wallet "
           "(agent) keys, seed phrases, WIF / xprv extended keys or API tokens, and never signs, places orders, "
           "withdraws or transfers. Pass public 0x wallet / vault addresses (0x + 40 hex) and coin tickers only. The "
           "rejected value was not stored, echoed or sent anywhere; if it was a real secret, treat it as exposed (it "
           "may sit in your shell history) and rotate it / move funds to a fresh wallet.")


def split_tokens(values):
    return [t for v in values for t in re.split(r"[,\s]+", v) if t]


def detect_secret(value, path=False):
    """Names the kind of secret a single argv value looks like (never returns the value itself), else None.

    path=True (values of --state / --out / --offline) skips the API-token prefix heuristic so a file such as
    hl_state.json is not mistaken for an hl_ token.
    """
    v = value.strip()
    words = v.split()
    if len(words) in _SEED_COUNTS and all(re.fullmatch(r"[A-Za-z]{2,12}", w) for w in words):
        return "BIP-39 seed phrase"
    for t in split_tokens([v]):
        if re.fullmatch(r"(0x)?[0-9a-fA-F]{64}", t):
            return "64-hex private key"
        if t.startswith(_XPRV_PREFIXES) and len(t) >= 16 and _B58.match(t):
            return "extended private key (xprv)"
        if _B58.match(t) and ((len(t) == 51 and t[0] in "59") or (len(t) == 52 and t[0] in "KLc")):
            return "WIF private key"
        if not path and t.lower().startswith(_TOKEN_PREFIXES) and len(t) >= 8:
            return "API token"
    return None


def detect_refusal(argv):
    """Scans raw argv; returns a kind string when the invocation must be refused (before any parsing / network)."""
    loose, prev = [], ""
    for a in argv:
        flag = a.split("=", 1)[0]
        if flag.startswith("--") and flag.lower() in _REFUSED_FLAGS:
            return "signing / secret option %s" % flag.lower()
        val = a.split("=", 1)[1] if a.startswith("--") and "=" in a else a
        is_path = prev in _PATH_FLAGS or (a.startswith("--") and "=" in a and flag in _PATH_FLAGS)
        kind = detect_secret(val, path=is_path)
        if kind:
            return kind
        if not a.startswith("-") and prev not in _VALUE_FLAGS and re.fullmatch(r"[a-z]{3,8}", val):
            loose.append(val)
        prev = a
    if len(loose) >= 12:  # an unquoted mnemonic spread over many positional words
        return "BIP-39 seed phrase"
    return None


# ---------------------------------------------------------------- number helpers
def fnum(v, default=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def fmt_usd(v, dp=0):
    if v is None:
        return "n/a"
    s = "{:,.{}f}".format(abs(v), dp)
    return ("-$" if v < 0 else "$") + s


def fmt_pct(v, dp=2, signed=False):
    if v is None:
        return "n/a"
    return ("{:+.{}f}%" if signed else "{:.{}f}%").format(v, dp)


def fmt_px(v):
    if v is None:
        return "n/a"
    a = abs(v)
    dp = 2 if a >= 100 else 4 if a >= 1 else 6 if a >= 0.01 else 8
    return "{:,.{}f}".format(v, dp)


def fmt_size(v):
    return "n/a" if v is None else ("{:,.6f}".format(v).rstrip("0").rstrip(".") or "0")


def fmt_num(v, dp=2):
    return "n/a" if v is None else "{:,.{}f}".format(v, dp)


def apr_from_rate(rate, interval_hours=1.0):
    """Per-interval funding rate -> annualised APR in percent."""
    if rate is None or not interval_hours:
        return None
    return rate / float(interval_hours) * HOURS_PER_YEAR * 100.0


def basis_bps(px, oracle):
    if px is None or not oracle:
        return None
    return (px - oracle) / oracle * 10000.0


def short_addr(a):
    return a[:6] + ".." + a[-4:] if a and len(a) > 12 else (a or "")


# ---------------------------------------------------------------- data source
class Source:
    """POSTs to the public Info endpoint only, or serves a deterministic --offline fixture."""

    def __init__(self, timeout=15, offline=None):
        self.timeout, self.fx = timeout, offline
        self.degraded, self.endpoints, self.calls = set(), set(), []

    def info(self, body, key=None):
        """Returns parsed JSON or raises nothing: failures are recorded in .degraded and return the _MISSING marker."""
        typ = body["type"]
        self.calls.append(dict(body))
        if self.fx is not None:
            d = self.fx.get(typ, _MISSING)
            if key is not None and isinstance(d, dict):
                d = d.get(key.lower(), _MISSING)
            elif key is not None:
                d = _MISSING
            if d is _MISSING:
                self.degraded.add(typ if key is None else "%s:%s" % (typ, short_addr(key)))
            return d
        res = bc.http_json(INFO_URL, body=body, headers={"Content-Type": "application/json"}, retries=2,
                           timeout=self.timeout)
        if res.status == 200 and not (isinstance(res.data, dict) and ("_raw" in res.data or "_error" in res.data)):
            self.endpoints.add("POST " + INFO_URL)
            return res.data
        self.degraded.add((typ if key is None else "%s:%s" % (typ, short_addr(key))) + " (%s)" % (res.error or res.status))
        return _MISSING


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


# ---------------------------------------------------------------- market model
def parse_markets(meta_ctx):
    """metaAndAssetCtxs -> {coin: market dict}. Delisted markets and malformed rows are skipped."""
    if not (isinstance(meta_ctx, list) and len(meta_ctx) >= 2 and isinstance(meta_ctx[0], dict)
            and isinstance(meta_ctx[1], list)):
        return None
    out = {}
    for u, c in zip(meta_ctx[0].get("universe") or [], meta_ctx[1]):
        if not isinstance(u, dict) or not isinstance(c, dict) or not u.get("name") or u.get("isDelisted"):
            continue
        mark, oracle, mid = fnum(c.get("markPx")), fnum(c.get("oraclePx")), fnum(c.get("midPx"))
        h = fnum(c.get("funding"))
        oi = fnum(c.get("openInterest"), 0.0)
        px = mark if mark is not None else oracle
        oi_usd = oi * px if px is not None else None
        vol = fnum(c.get("dayNtlVlm"), 0.0)
        prev = fnum(c.get("prevDayPx"))
        impact = c.get("impactPxs") or []
        out[u["name"]] = {
            "coin": u["name"], "max_leverage": u.get("maxLeverage"),
            "mark": mark, "oracle": oracle, "mid": mid, "prev_day": prev,
            "change_24h_pct": (px - prev) / prev * 100.0 if px is not None and prev else None,
            "funding_1h": h, "funding_1h_pct": h * 100.0 if h is not None else None,
            "funding_8h_pct": h * 8 * 100.0 if h is not None else None, "funding_apr": apr_from_rate(h, 1),
            "premium": fnum(c.get("premium")),
            "basis_bps": basis_bps(mark, oracle), "mid_spread_bps": basis_bps(mid, oracle),
            "impact_bid": fnum(impact[0]) if len(impact) > 0 else None,
            "impact_ask": fnum(impact[1]) if len(impact) > 1 else None,
            "open_interest": oi, "oi_usd": oi_usd, "volume_24h": vol,
            "turnover": vol / oi_usd if oi_usd else None, "venues": {},
        }
    return out


def attach_predicted(markets, predicted):
    """predictedFundings -> per-venue raw rate, interval and APR; spreads + sign flips vs Hyperliquid."""
    if not isinstance(predicted, list):
        return False
    for row in predicted:
        if not (isinstance(row, list) and len(row) == 2 and row[0] in markets and isinstance(row[1], list)):
            continue
        venues = {}
        for item in row[1]:
            if not (isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict)):
                continue
            name, d = item
            rate = fnum(d.get("fundingRate"))
            if rate is None:
                continue
            iv = fnum(d.get("fundingIntervalHours")) or DEFAULT_INTERVAL.get(name, 8)
            venues[name] = {"rate": rate, "interval_h": iv, "apr": apr_from_rate(rate, iv),
                            "next_funding_ms": d.get("nextFundingTime")}
        m = markets[row[0]]
        m["venues"] = venues
        hl = venues.get("HlPerp")
        for v in ("BinPerp", "BybitPerp"):
            if hl and v in venues:
                venues[v]["spread_apr"] = hl["apr"] - venues[v]["apr"]
                venues[v]["sign_flip"] = (hl["rate"] > 0 > venues[v]["rate"]) or (hl["rate"] < 0 < venues[v]["rate"])
    return True


def select_markets(markets, coins, top):
    """Returns (selected coin names, unknown requested coins). --coins wins over --top."""
    if coins:
        lower = {k.lower(): k for k in markets}
        sel, unknown = [], []
        for c in coins:
            k = lower.get(c.lower())
            if k is None:
                unknown.append(c)
            elif k not in sel:
                sel.append(k)
        return sel, unknown
    ranked = sorted(markets.values(), key=lambda m: (-(m["oi_usd"] or 0), m["coin"]))
    return [m["coin"] for m in ranked[:top]], []


def funding_extremes(markets, n=5, min_oi=EXTREMES_MIN_OI_USD):
    pool = [m for m in markets.values() if m["funding_apr"] is not None and (m["oi_usd"] or 0) >= min_oi]
    return [m["coin"] for m in sorted(pool, key=lambda m: (-abs(m["funding_apr"]), m["coin"]))[:n]]


def market_findings(m, opts):
    out, coin = [], m["coin"]
    apr = m["funding_apr"]
    if apr is not None and abs(apr) >= opts["funding_apr_warn"]:
        sev = "HIGH" if abs(apr) >= max(100.0, opts["funding_apr_warn"]) else "MEDIUM"
        side = "longs pay shorts" if apr > 0 else "shorts pay longs"
        out.append(bc.Finding(sev, "MARKET_EXTREME_FUNDING",
                              "%s funding %s APR (%s/h, %s/8h): %s" % (coin, fmt_pct(apr, 1, True), fmt_pct(m["funding_1h_pct"], 4, True),
                                                                       fmt_pct(m["funding_8h_pct"], 4, True), side),
                              {"coin": coin, "funding_apr_pct": round(apr, 4), "funding_1h": m["funding_1h"]},
                              key="mkt:%s:FUNDING" % coin))
    b = m["basis_bps"]
    if b is not None and abs(b) >= opts["basis_warn_bps"]:
        sev = "HIGH" if abs(b) >= max(100.0, opts["basis_warn_bps"]) else "MEDIUM"
        out.append(bc.Finding(sev, "MARKET_BASIS_DISLOCATION",
                              "%s mark %s vs oracle %s: basis %+.1f bps" % (coin, fmt_px(m["mark"]), fmt_px(m["oracle"]), b),
                              {"coin": coin, "basis_bps": round(b, 3), "mark": m["mark"], "oracle": m["oracle"]},
                              key="mkt:%s:BASIS" % coin))
    worst = None
    for v in ("BinPerp", "BybitPerp"):
        d = m["venues"].get(v)
        if not d or "spread_apr" not in d:
            continue
        big = abs(d["spread_apr"]) >= CROSS_VENUE_APR_SPREAD
        if big or d["sign_flip"]:
            score = (big, abs(d["spread_apr"]))
            if worst is None or score > worst[0]:
                worst = (score, v, d, big)
    if worst:
        _, v, d, big = worst
        hl = m["venues"]["HlPerp"]
        out.append(bc.Finding("MEDIUM" if big else "INFO", "CROSS_VENUE_FUNDING_DIVERGENCE",
                              "%s predicted funding Hyperliquid %s APR (%s/%dh) vs %s %s APR (%s/%dh): spread %s APR%s"
                              % (coin, fmt_pct(hl["apr"], 1, True), fmt_pct(hl["rate"] * 100, 4, True), hl["interval_h"],
                                 VENUE_LABEL[v], fmt_pct(d["apr"], 1, True), fmt_pct(d["rate"] * 100, 4, True), d["interval_h"],
                                 fmt_pct(d["spread_apr"], 1, True), ", SIGN FLIP" if d["sign_flip"] else ""),
                              {"coin": coin, "venue": v, "spread_apr_pct": round(d["spread_apr"], 4), "sign_flip": d["sign_flip"]},
                              key="mkt:%s:XVENUE" % coin))
    return out


# ---------------------------------------------------------------- account (wallet / vault) model
def margin_summary(ch):
    ms = ch.get("marginSummary") or {}
    av, ntl = fnum(ms.get("accountValue"), 0.0), fnum(ms.get("totalNtlPos"), 0.0)
    used = fnum(ms.get("totalMarginUsed"), 0.0)
    return {"account_value": av, "total_ntl_pos": ntl, "total_raw_usd": fnum(ms.get("totalRawUsd"), 0.0),
            "total_margin_used": used, "withdrawable": fnum(ch.get("withdrawable"), 0.0),
            "cross_maint_margin_used": fnum(ch.get("crossMaintenanceMarginUsed")),
            "leverage": ntl / av if av > 0 else None,
            "margin_util_pct": used / av * 100.0 if av > 0 else (100.0 if used > 0 else 0.0)}


def liq_distance(side, mark, liq):
    """Signed distance in % of mark (positive = room before liquidation). None when no liquidation price."""
    if liq is None or not mark:
        return None, None
    usd = (mark - liq) if side == "LONG" else (liq - mark)
    return usd, usd / mark * 100.0


def parse_positions(ch, markets, account_value):
    out = []
    for ap in ch.get("assetPositions") or []:
        p = (ap or {}).get("position") or {}
        szi = fnum(p.get("szi"), 0.0)
        if not szi or not p.get("coin"):
            continue
        coin = p["coin"]
        side = "LONG" if szi > 0 else "SHORT"
        mk = (markets or {}).get(coin) or {}
        value = abs(fnum(p.get("positionValue"), 0.0))
        mark = mk.get("mark") or (value / abs(szi) if value else None)
        lev = p.get("leverage") or {}
        lev_type, lev_val = lev.get("type", "cross"), fnum(lev.get("value"))
        margin = fnum(p.get("marginUsed"), 0.0)
        if lev_type == "isolated":
            eff = value / margin if margin > 0 else lev_val
        else:
            eff = value / account_value if account_value > 0 else lev_val
        liq = fnum(p.get("liquidationPx"))
        d_usd, d_pct = liq_distance(side, mark, liq)
        cf = p.get("cumFunding") or {}
        out.append({
            "coin": coin, "side": side, "szi": szi, "position_value": value, "entry_px": fnum(p.get("entryPx")),
            "mark": mark, "oracle": mk.get("oracle"), "unrealized_pnl": fnum(p.get("unrealizedPnl"), 0.0),
            "roe_pct": (fnum(p.get("returnOnEquity"), 0.0) or 0.0) * 100.0, "leverage_type": lev_type,
            "leverage_setting": lev_val, "effective_leverage": eff, "max_leverage": p.get("maxLeverage"),
            "margin_used": margin, "liquidation_px": liq, "liq_distance_usd": d_usd, "liq_distance_pct": d_pct,
            "cum_funding_all_time": fnum(cf.get("allTime")), "cum_funding_since_open": fnum(cf.get("sinceOpen")),
            "funding_1h": mk.get("funding_1h"), "funding_apr": mk.get("funding_apr"),
        })
    out.sort(key=lambda x: (-x["position_value"], x["coin"]))
    return out


def margin_findings(acct, ms, opts, kp):
    u, warn = ms["margin_util_pct"], opts["margin_util_warn"]
    crit, med = max(85.0, warn), min(50.0, warn)
    if u >= crit:
        sev, code = "CRITICAL", "MARGIN_UTIL_CRITICAL"
    elif u >= warn:
        sev, code = "HIGH", "MARGIN_UTIL_HIGH"
    elif u >= med:
        sev, code = "MEDIUM", "MARGIN_UTIL_ELEVATED"
    else:
        return []
    return [bc.Finding(sev, code, "%s margin utilisation %.1f%% (%s used of %s account value, leverage %s)"
                       % (acct, u, fmt_usd(ms["total_margin_used"]), fmt_usd(ms["account_value"]),
                          "n/a" if ms["leverage"] is None else "%.2fx" % ms["leverage"]),
                       {"margin_util_pct": round(u, 4), "account_value": ms["account_value"]}, key=kp + ":MARGIN_UTIL")]


def position_findings(acct, p, opts, kp):
    out, coin, d = [], p["coin"], p["liq_distance_pct"]
    pk = "%s:%s" % (kp, coin)
    if d is not None:
        crit, warn = opts["liq_crit_pct"], opts["liq_warn_pct"]
        wrong_side = d <= 0
        if wrong_side or d < crit:
            sev, code = "CRITICAL", "LIQ_DISTANCE_CRITICAL"
        elif d < warn:
            sev, code = "HIGH", "LIQ_DISTANCE_HIGH"
        elif d < 2 * warn:
            sev, code = "MEDIUM", "LIQ_DISTANCE_MEDIUM"
        else:
            sev = None
        if sev:
            msg = "%s %s %s: mark %s vs liquidation %s -> %s (%s)" % (
                acct, p["side"], coin, fmt_px(p["mark"]), fmt_px(p["liquidation_px"]),
                "AT/THROUGH LIQUIDATION PRICE (directional check failed)" if wrong_side else "%.2f%% away" % d,
                fmt_usd(p["liq_distance_usd"], 2))
            out.append(bc.Finding(sev, code, msg, {"coin": coin, "side": p["side"], "liq_distance_pct": round(d, 4),
                                                   "liquidation_px": p["liquidation_px"], "mark": p["mark"]},
                                  key=pk + ":LIQ_DISTANCE"))
    eff = p["effective_leverage"]
    if eff is not None and eff >= 10:
        out.append(bc.Finding("HIGH" if eff >= 20 else "MEDIUM", "HIGH_EFFECTIVE_LEVERAGE",
                              "%s %s %s effective leverage %.1fx (%s %s setting, %s notional)"
                              % (acct, p["side"], coin, eff, p["leverage_type"],
                                 "n/a" if p["leverage_setting"] is None else "%gx" % p["leverage_setting"],
                                 fmt_usd(p["position_value"])),
                              {"coin": coin, "effective_leverage": round(eff, 4), "leverage_type": p["leverage_type"]},
                              key=pk + ":LEVERAGE"))
    return out


def concentration_findings(acct, positions, account_value, kp):
    total = sum(p["position_value"] for p in positions)
    out = []
    for p in positions:
        share = p["position_value"] / total if total else 0.0
        by_share = len(positions) >= 2 and share >= CONCENTRATION_SHARE
        by_equity = account_value > 0 and p["position_value"] >= CONCENTRATION_EQUITY_MULT * account_value
        if by_share or by_equity:
            out.append(bc.Finding("MEDIUM", "SINGLE_POSITION_CONCENTRATION",
                                  "%s %s %s is %.0f%% of total notional (%s) and %.1fx account value"
                                  % (acct, p["side"], p["coin"], share * 100, fmt_usd(p["position_value"]),
                                     p["position_value"] / account_value if account_value > 0 else float("inf")),
                                  {"coin": p["coin"], "share_pct": round(share * 100, 4)},
                                  key="%s:%s:CONCENTRATION" % (kp, p["coin"])))
    return out


def funding_findings(acct, p, opts, kp):
    h, apr = p["funding_1h"], p["funding_apr"]
    if h is None or apr is None:
        return []
    adverse = (p["side"] == "LONG" and h > 0) or (p["side"] == "SHORT" and h < 0)
    warn = opts["funding_apr_warn"]
    if not adverse or abs(apr) < warn:
        return []
    daily = p["position_value"] * abs(h) * 24
    return [bc.Finding("HIGH" if abs(apr) >= 2 * warn else "MEDIUM", "ADVERSE_FUNDING_BLEED",
                       "%s %s %s pays funding at %s APR (%s/h): est. %s/day carry on %s notional"
                       % (acct, p["side"], p["coin"], fmt_pct(abs(apr), 1), fmt_pct(abs(h) * 100, 4), fmt_usd(daily, 2),
                          fmt_usd(p["position_value"])),
                       {"coin": p["coin"], "funding_apr_pct": round(apr, 4), "daily_cost_usd": round(daily, 4)},
                       key="%s:%s:FUNDING_BLEED" % (kp, p["coin"]))]


def is_stop_order(o, side, mark):
    """True for a stop-loss style trigger (Stop Market / Stop Limit, or a loss-side trigger when the type is unknown)."""
    ot = str(o.get("orderType") or "").lower()
    if "stop" in ot:
        return True
    if "take" in ot:
        return False
    tp = fnum(o.get("triggerPx"))
    if tp is None or mark is None:
        return False
    return tp < mark if side == "LONG" else tp > mark


def order_coverage(p, orders):
    """Classifies the open orders on p's coin: protective stops, take-profits and non-reduceOnly opposite triggers."""
    close_side = "A" if p["side"] == "LONG" else "B"
    stops, tps, loose = [], [], []
    for o in orders:
        if o.get("coin") != p["coin"] or o.get("side") != close_side or not o.get("isTrigger"):
            continue
        if not o.get("reduceOnly"):
            loose.append(o)
        elif is_stop_order(o, p["side"], p["mark"]):
            stops.append(o)
        else:
            tps.append(o)
    return {"stops": stops, "tps": tps, "loose": loose}


def protection_findings(acct, p, cov, opts, kp):
    out, coin = [], p["coin"]
    pk = "%s:%s" % (kp, coin)
    if not cov["stops"]:
        eff, d = p["effective_leverage"] or 0.0, p["liq_distance_pct"]
        if eff >= 10 or (d is not None and d < 2 * opts["liq_warn_pct"]):
            sev = "HIGH"
        elif eff > 1 or (p["leverage_type"] == "isolated" and (p["leverage_setting"] or 0) > 1):
            sev = "MEDIUM"
        else:
            sev = "LOW"
        note = "take-profit only, " if cov["tps"] else ""
        out.append(bc.Finding(sev, "UNPROTECTED_POSITION_NO_SL",
                              "%s %s %s (%s notional, %.1fx effective, liq distance %s) has no reduceOnly stop-loss "
                              "trigger (%s%d open trigger order(s) on the closing side)"
                              % (acct, p["side"], coin, fmt_usd(p["position_value"]), eff,
                                 fmt_pct(d) if d is not None else "n/a", note,
                                 len(cov["tps"]) + len(cov["loose"])),
                              {"coin": coin, "effective_leverage": round(eff, 4)}, key=pk + ":NO_SL"))
    if cov["loose"]:
        flips = any(fnum(o.get("sz"), 0.0) > abs(p["szi"]) for o in cov["loose"])
        out.append(bc.Finding("MEDIUM" if flips else "LOW", "NON_REDUCE_ONLY_STOP",
                              "%s %s %s has %d trigger order(s) on the closing side without reduceOnly%s"
                              % (acct, p["side"], coin, len(cov["loose"]),
                                 " and larger than the position (could flip it)" if flips else " (could open a new position)"),
                              {"coin": coin, "oids": [o.get("oid") for o in cov["loose"]]}, key=pk + ":NON_REDUCE_ONLY"))
    return out


def parse_spot(spot):
    out = []
    for b in (spot or {}).get("balances") or []:
        total, hold = fnum(b.get("total"), 0.0), fnum(b.get("hold"), 0.0)
        if not total:
            continue
        out.append({"coin": b.get("coin"), "token": b.get("token"), "total": total, "hold": hold,
                    "available": total - hold, "entry_ntl": fnum(b.get("entryNtl"))})
    out.sort(key=lambda x: (-(x["entry_ntl"] or 0), str(x["coin"])))
    return out


def audit_account(addr, ch, markets, opts, label, kp, orders=None, wallet=False):
    """Margin + positions for one clearinghouse account; wallets also get funding-carry and stop-loss checks
    (orders=None means frontendOpenOrders was unavailable, so protection is not judged)."""
    ms = margin_summary(ch)
    positions = parse_positions(ch, markets, ms["account_value"])
    for p in positions:
        p["account"] = addr
    findings = margin_findings(label, ms, opts, kp)
    for p in positions:
        findings += position_findings(label, p, opts, kp)
        if wallet:
            findings += funding_findings(label, p, opts, kp)
    findings += concentration_findings(label, positions, ms["account_value"], kp)
    if wallet and orders is not None:
        for p in positions:
            cov = order_coverage(p, orders)
            p["sl_orders"], p["tp_orders"], p["non_reduce_only"] = len(cov["stops"]), len(cov["tps"]), len(cov["loose"])
            findings += protection_findings(label, p, cov, opts, kp)
    return {"address": addr, "margin": ms, "positions": positions}, findings


def audit_wallet(src, addr, markets, opts):
    a = addr.lower()
    kp, label = "w:" + a, "wallet " + short_addr(a)
    ch = src.info({"type": "clearinghouseState", "user": a}, key=a)
    if not isinstance(ch, dict):
        return {"address": a, "error": "clearinghouseState unavailable"}, []
    orders = src.info({"type": "frontendOpenOrders", "user": a}, key=a)
    orders_ok = isinstance(orders, list)
    rep, findings = audit_account(a, ch, markets, opts, label, kp, orders if orders_ok else None, wallet=True)
    rep["open_orders"] = len(orders) if orders_ok else None
    rep["trigger_orders"] = sum(1 for o in orders if o.get("isTrigger")) if orders_ok else None
    spot = src.info({"type": "spotClearinghouseState", "user": a}, key=a)
    rep["spot"] = parse_spot(spot) if isinstance(spot, dict) else None
    if not rep["positions"] and not rep["margin"]["account_value"] and not rep["spot"]:
        findings.append(bc.Finding("INFO", "WALLET_EMPTY", "%s has no perp account value, positions or spot balances" % label,
                                   key=kp + ":EMPTY"))
    return rep, findings


def vault_drawdown(portfolio):
    """Peak-to-current account-value drawdown per window (includes deposits/withdrawals, so it is an upper bound)."""
    out = {}
    for item in portfolio or []:
        if not (isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict)):
            continue
        hist = [fnum(v[1]) for v in item[1].get("accountValueHistory") or [] if isinstance(v, list) and len(v) == 2]
        hist = [h for h in hist if h is not None]
        if not hist:
            continue
        peak, cur = max(hist), hist[-1]
        pnl = [fnum(v[1]) for v in item[1].get("pnlHistory") or [] if isinstance(v, list) and len(v) == 2]
        out[item[0]] = {"peak": peak, "current": cur, "drawdown_pct": (peak - cur) / peak * 100.0 if peak > 0 else 0.0,
                        "pnl": pnl[-1] if pnl and pnl[-1] is not None else None}
    return out


def audit_vault(src, addr, markets, opts):
    a = addr.lower()
    kp = "v:" + a
    vd = src.info({"type": "vaultDetails", "vaultAddress": a}, key=a)
    if vd is _MISSING:
        return {"address": a, "error": "vaultDetails unavailable"}, []
    if not isinstance(vd, dict) or not (vd.get("vaultAddress") or vd.get("name")):  # live API returns null
        return {"address": a, "error": "not a vault"}, [bc.Finding(
            "LOW", "VAULT_NOT_FOUND", "vault %s: vaultDetails returned no vault for this address" % short_addr(a),
            key=kp + ":NOT_FOUND")]
    name = vd.get("name") or short_addr(a)
    label = "vault %s" % name
    protocol = a in PROTOCOL_VAULTS
    rel = vd.get("relationship") or {}
    children = [c.lower() for c in ((rel.get("data") or {}).get("childAddresses") or []) if isinstance(c, str) and ADDR_RE.match(c)]
    rep = {"address": a, "name": name, "leader": vd.get("leader"), "description": vd.get("description"),
           "apr_pct": (fnum(vd.get("apr"), 0.0) or 0.0) * 100.0, "leader_fraction": fnum(vd.get("leaderFraction")),
           "leader_commission": fnum(vd.get("leaderCommission")), "max_distributable": fnum(vd.get("maxDistributable")),
           "max_withdrawable": fnum(vd.get("maxWithdrawable")), "is_closed": bool(vd.get("isClosed")),
           "allow_deposits": bool(vd.get("allowDeposits", True)), "followers": len(vd.get("followers") or []),
           "protocol": protocol, "relationship": rel.get("type"), "children": children,
           "drawdown": vault_drawdown(vd.get("portfolio")), "accounts": []}
    findings = []
    if rep["is_closed"]:
        findings.append(bc.Finding("HIGH", "VAULT_CLOSED_OR_DEPOSITS_DISABLED", "%s is closed" % label, key=kp + ":STATUS"))
    elif not rep["allow_deposits"]:
        findings.append(bc.Finding("MEDIUM", "VAULT_CLOSED_OR_DEPOSITS_DISABLED", "%s does not accept deposits" % label,
                                   key=kp + ":STATUS"))
    lf = rep["leader_fraction"]
    if lf is not None and lf < 0.01 and not protocol:
        findings.append(bc.Finding("LOW", "VAULT_LOW_LEADER_SKIN", "%s leader owns only %.2f%% of the vault"
                                   % (label, lf * 100), {"leader_fraction": lf}, key=kp + ":LEADER_SKIN"))
    accts = [(a, label)] + [(c, "%s child %s" % (label, short_addr(c))) for c in children[:MAX_CHILD_ACCOUNTS]]
    for acct, alabel in accts:
        ch = src.info({"type": "clearinghouseState", "user": acct}, key=acct)
        if not isinstance(ch, dict):
            rep["accounts"].append({"address": acct, "error": "clearinghouseState unavailable"})
            continue
        r, fl = audit_account(acct, ch, markets, opts, alabel, "%s:%s" % (kp, acct))
        r["role"] = "vault" if acct == a else "child"
        rep["accounts"].append(r)
        findings += fl
    ok = [x for x in rep["accounts"] if "margin" in x]
    rep["tvl"] = sum(x["margin"]["account_value"] for x in ok)
    rep["total_ntl_pos"] = sum(x["margin"]["total_ntl_pos"] for x in ok)
    rep["positions_total"] = sum(len(x["positions"]) for x in ok)
    if len(children) > MAX_CHILD_ACCOUNTS:
        rep["children_skipped"] = len(children) - MAX_CHILD_ACCOUNTS
    return rep, findings


# ---------------------------------------------------------------- state + delta
def make_snapshot(wallets, vaults, markets_sel, findings):
    def pos_map(ps):
        return {p["coin"]: {"side": p["side"], "szi": p["szi"], "liq_distance_pct": p["liq_distance_pct"],
                            "position_value": p["position_value"]} for p in ps}

    snap = {"wallets": {}, "vaults": {}, "markets": {}, "findings": [f.to_dict() for f in findings]}
    for w in wallets:
        if "margin" in w:
            snap["wallets"][w["address"]] = {"margin_util_pct": w["margin"]["margin_util_pct"],
                                             "account_value": w["margin"]["account_value"], "positions": pos_map(w["positions"])}
    for v in vaults:
        for a in v.get("accounts") or []:
            if "margin" in a:
                snap["vaults"]["%s:%s" % (v["address"], a["address"])] = {
                    "margin_util_pct": a["margin"]["margin_util_pct"], "account_value": a["margin"]["account_value"],
                    "positions": pos_map(a["positions"])}
    for m in markets_sel:
        snap["markets"][m["coin"]] = {"funding_apr": m["funding_apr"], "basis_bps": m["basis_bps"]}
    return snap


def _liq_events(prefix, label, old_p, new_p, opts):
    out = []
    for coin in sorted(set(old_p) & set(new_p)):
        o, n = old_p[coin], new_p[coin]
        od, nd = o.get("liq_distance_pct"), n.get("liq_distance_pct")
        if od is None or nd is None or o.get("side") != n.get("side") or nd >= od:
            continue
        drop = od - nd
        crit, warn = opts["liq_crit_pct"], opts["liq_warn_pct"]
        if nd < crit <= od:
            sev = "CRITICAL"
        elif nd < warn <= od or (drop >= LIQ_TIGHTEN_PP and nd < 2 * warn):  # far-away liq prices just wobble
            sev = "HIGH"
        else:
            continue
        out.append(bc.Finding(sev, "LIQ_DISTANCE_TIGHTENED", "%s %s %s liquidation distance %.2f%% -> %.2f%% (-%.2f pp)"
                              % (label, n["side"], coin, od, nd, drop),
                              {"coin": coin, "old_pct": round(od, 4), "new_pct": round(nd, 4)},
                              key="%s:%s:LIQ_TIGHTENED" % (prefix, coin)))
    return out


def _margin_event(prefix, label, old, new):
    ou, nu = old.get("margin_util_pct"), new.get("margin_util_pct")
    if ou is None or nu is None or nu - ou < MARGIN_SPIKE_PP:
        return []
    return [bc.Finding("HIGH", "MARGIN_UTIL_SPIKE", "%s margin utilisation %.1f%% -> %.1f%% (+%.1f pp)" % (label, ou, nu, nu - ou),
                       {"old_pct": round(ou, 4), "new_pct": round(nu, 4)}, key=prefix + ":MARGIN_SPIKE")]


def _position_events(prefix, label, old_p, new_p):
    out = []
    for coin in sorted(set(new_p) - set(old_p)):
        n = new_p[coin]
        out.append(bc.Finding("LOW", "POSITION_OPENED", "%s opened %s %s size %g (%s)" % (label, n["side"], coin, n["szi"], fmt_usd(n["position_value"])),
                              {"coin": coin, "szi": n["szi"]}, key="%s:%s:OPENED" % (prefix, coin)))
    for coin in sorted(set(old_p) - set(new_p)):
        o = old_p[coin]
        out.append(bc.Finding("INFO", "POSITION_CLOSED", "%s closed %s %s (was size %g)" % (label, o["side"], coin, o["szi"]),
                              {"coin": coin, "szi": o["szi"]}, key="%s:%s:CLOSED" % (prefix, coin)))
    for coin in sorted(set(old_p) & set(new_p)):
        o, n = old_p[coin], new_p[coin]
        if o["side"] != n["side"]:
            out.append(bc.Finding("MEDIUM", "POSITION_FLIPPED", "%s %s flipped %s -> %s (size %g -> %g)"
                                  % (label, coin, o["side"], n["side"], o["szi"], n["szi"]),
                                  {"coin": coin, "old_szi": o["szi"], "new_szi": n["szi"]}, key="%s:%s:FLIPPED" % (prefix, coin)))
        elif o["szi"] and abs(n["szi"] - o["szi"]) / abs(o["szi"]) >= SIZE_CHANGE_REL:
            out.append(bc.Finding("INFO", "POSITION_SIZE_CHANGED", "%s %s %s size %g -> %g (%+.1f%%)"
                                  % (label, n["side"], coin, o["szi"], n["szi"], (abs(n["szi"]) / abs(o["szi"]) - 1) * 100),
                                  {"coin": coin, "old_szi": o["szi"], "new_szi": n["szi"]}, key="%s:%s:SIZE" % (prefix, coin)))
    return out


def compute_events(prev, snap, opts):
    ev = []
    for a, n in sorted(snap["wallets"].items()):
        o = (prev.get("wallets") or {}).get(a)
        if not o:
            continue
        label, prefix = "wallet " + short_addr(a), "d:w:" + a
        ev += _margin_event(prefix, label, o, n)
        ev += _liq_events(prefix, label, o.get("positions") or {}, n["positions"], opts)
        ev += _position_events(prefix, label, o.get("positions") or {}, n["positions"])
    for k, n in sorted(snap["vaults"].items()):
        o = (prev.get("vaults") or {}).get(k)
        if not o:
            continue
        label, prefix = "vault account " + short_addr(k.split(":")[1]), "d:v:" + k
        ev += _margin_event(prefix, label, o, n)
        ev += _liq_events(prefix, label, o.get("positions") or {}, n["positions"], opts)
    for coin, n in sorted(snap["markets"].items()):
        o = (prev.get("markets") or {}).get(coin)
        if not o:
            continue
        oa, na = o.get("funding_apr"), n.get("funding_apr")
        if oa is not None and na is not None:
            flip = (oa > 0 > na) or (oa < 0 < na)
            if flip or abs(na - oa) >= FUNDING_SHIFT_APR:
                ev.append(bc.Finding("MEDIUM", "FUNDING_REGIME_SHIFT", "%s funding APR %s -> %s%s"
                                     % (coin, fmt_pct(oa, 1, True), fmt_pct(na, 1, True), " (sign flip)" if flip else ""),
                                     {"coin": coin, "old_apr": round(oa, 4), "new_apr": round(na, 4), "sign_flip": flip},
                                     key="d:m:%s:FUNDING_SHIFT" % coin))
        ob, nb = o.get("basis_bps"), n.get("basis_bps")
        if ob is not None and nb is not None and abs(ob) < opts["basis_warn_bps"] <= abs(nb):
            ev.append(bc.Finding("HIGH" if abs(nb) >= max(100.0, opts["basis_warn_bps"]) else "MEDIUM", "BASIS_DISLOCATED",
                                 "%s mark-oracle basis %+.1f -> %+.1f bps (crossed %.0f bps)" % (coin, ob, nb, opts["basis_warn_bps"]),
                                 {"coin": coin, "old_bps": round(ob, 3), "new_bps": round(nb, 3)}, key="d:m:%s:BASIS" % coin))
    return ev


# ---------------------------------------------------------------- rendering
_COLORS = {"CRITICAL": "\033[1;31m", "HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[36m", "INFO": "\033[2m"}


def _venue_cell(m, v):
    d = m["venues"].get(v)
    if not d:
        return "n/a"
    s = "%s (%s/%gh)" % (fmt_pct(d["apr"], 1, True), fmt_pct(d["rate"] * 100, 4, True), d["interval_h"])
    if d.get("sign_flip"):
        s += " FLIP"
    return s


def _pos_row(p, coins):
    star = "*" if coins and p["coin"].lower() in coins else ""
    return [star + p["coin"], p["side"], fmt_size(p["szi"]), fmt_usd(p["position_value"]), fmt_px(p["entry_px"]),
            fmt_px(p["mark"]), fmt_usd(p["unrealized_pnl"]), fmt_pct(p["roe_pct"], 1, True),
            "%s %s" % (p["leverage_type"], "n/a" if p["leverage_setting"] is None else "%gx" % p["leverage_setting"]),
            "n/a" if p["effective_leverage"] is None else "%.2fx" % p["effective_leverage"],
            fmt_px(p["liquidation_px"]),
            "n/a" if p["liq_distance_pct"] is None else "%s (%s)" % (fmt_pct(p["liq_distance_pct"]), fmt_usd(p["liq_distance_usd"], 2)),
            fmt_usd(p["cum_funding_since_open"], 2), fmt_usd(p["cum_funding_all_time"], 2)]


POS_HEAD = ["coin", "side", "size", "notional", "entry", "mark", "uPnL", "ROE", "leverage", "eff.lev", "liq px",
            "liq distance", "funding since open", "funding all-time"]
MKT_HEAD = ["coin", "mark", "oracle", "24h", "funding 1h", "8h", "APR", "basis bps", "mid bps", "OI USD", "24h vol",
            "vol/OI", "Binance pred.", "Bybit pred."]


def _mkt_row(m, coins):
    star = "*" if coins and m["coin"].lower() in coins else ""
    return [star + m["coin"], fmt_px(m["mark"]), fmt_px(m["oracle"]), fmt_pct(m["change_24h_pct"], 2, True),
            fmt_pct(m["funding_1h_pct"], 4, True), fmt_pct(m["funding_8h_pct"], 4, True), fmt_pct(m["funding_apr"], 1, True),
            "n/a" if m["basis_bps"] is None else "%+.1f" % m["basis_bps"],
            "n/a" if m["mid_spread_bps"] is None else "%+.1f" % m["mid_spread_bps"],
            fmt_usd(m["oi_usd"]), fmt_usd(m["volume_24h"]), fmt_num(m["turnover"]),
            _venue_cell(m, "BinPerp"), _venue_cell(m, "BybitPerp")]


def _table_text(head, rows):
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)] if rows else [len(h) for h in head]
    fmt = "  " + "  ".join("%%-%ds" % n for n in w)
    return [fmt % tuple(head)] + [fmt % tuple(r) for r in rows]


def _table_md(head, rows):
    esc = lambda s: str(s).replace("|", "\\|")  # noqa: E731
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]


def _margin_line(ms):
    return ("account value %s | total notional %s | raw USD %s | margin used %s | withdrawable %s | leverage %s | "
            "margin utilisation %s" % (fmt_usd(ms["account_value"], 2), fmt_usd(ms["total_ntl_pos"], 2),
                                       fmt_usd(ms["total_raw_usd"], 2), fmt_usd(ms["total_margin_used"], 2),
                                       fmt_usd(ms["withdrawable"], 2),
                                       "n/a" if ms["leverage"] is None else "%.2fx" % ms["leverage"], fmt_pct(ms["margin_util_pct"])))


def render(report, findings, delta, code, degraded, header, fmt, color=False):
    md = fmt == "markdown"
    table = _table_md if md else _table_text
    coins = set(c.lower() for c in report["coins"])
    top = report["opts"]["top"]
    L = []
    if md:
        L += ["# Hyperliquid Perps, Funding & Liquidation Risk Monitor", "", "```", header, "```", ""]
    else:
        L += [header, ""]

    def h(title):
        L.extend(["## " + title, ""] if md else [title.upper(), "-" * len(title)])

    mk = report.get("markets")
    if mk is not None:
        h("Market scan (%s)" % ("requested coins" if report["coins"] else "top %d by open interest" % top))
        if mk.get("error"):
            L += [mk["error"], ""]
        else:
            L += ["%d live perp markets; total open interest %s; 24h notional volume %s" % (
                mk["count"], fmt_usd(mk["total_oi_usd"]), fmt_usd(mk["total_volume_24h"])), ""]
            L += table(MKT_HEAD, [_mkt_row(m, coins) for m in mk["selected"]]) + [""]
            if mk.get("unknown"):
                L += ["not listed / delisted: %s" % ", ".join(mk["unknown"]), ""]
            if mk["extremes"]:
                L += ["Funding extremes (OI >= %s):" % fmt_usd(EXTREMES_MIN_OI_USD), ""]
                L += table(["coin", "APR", "funding 1h", "basis bps", "OI USD"],
                           [[m["coin"], fmt_pct(m["funding_apr"], 1, True), fmt_pct(m["funding_1h_pct"], 4, True),
                             "n/a" if m["basis_bps"] is None else "%+.1f" % m["basis_bps"], fmt_usd(m["oi_usd"])]
                            for m in mk["extremes"]]) + [""]
            if not mk["predicted_ok"]:
                L += ["predictedFundings unavailable: cross-venue columns are empty", ""]
            L += ["Predicted funding is per venue interval (Hyperliquid 1h, Binance / Bybit usually 4h or 8h) and "
                  "annualised as rate / interval_hours * 8760.", ""]
    for w in report["wallets"]:
        h("Wallet %s" % w["address"])
        if w.get("error"):
            L += ["error: %s" % w["error"], ""]
            continue
        L += [_margin_line(w["margin"]), ""]
        if w["positions"]:
            rows = [_pos_row(p, coins) + ["%d SL / %d TP / %d loose" % (p.get("sl_orders", 0), p.get("tp_orders", 0), p.get("non_reduce_only", 0))
                                          if "sl_orders" in p else "n/a"] for p in w["positions"]]
            L += table(POS_HEAD + ["triggers"], rows) + [""]
        else:
            L += ["no open perp positions", ""]
        L += ["open orders: %s (trigger orders: %s)" % ("n/a" if w["open_orders"] is None else w["open_orders"],
                                                        "n/a" if w["trigger_orders"] is None else w["trigger_orders"]), ""]
        if w["spot"] is None:
            L += ["spot balances: unavailable", ""]
        elif w["spot"]:
            L += ["Spot balances (HIP-1):", ""]
            L += table(["coin", "total", "hold", "available", "entry notional"],
                       [[s["coin"], fmt_num(s["total"], 6), fmt_num(s["hold"], 6), fmt_num(s["available"], 6), fmt_usd(s["entry_ntl"], 2)]
                        for s in w["spot"]]) + [""]
        else:
            L += ["spot balances: none", ""]
    for v in report["vaults"]:
        h("Vault %s" % (v.get("name") or v["address"]))
        if v.get("error"):
            L += ["%s: %s" % (v["address"], v["error"]), ""]
            continue
        lf = v["leader_fraction"]
        rows = [["address", v["address"]], ["leader", v["leader"]],
                ["type", ("protocol vault" if v["protocol"] else "user vault") + (" (parent of %d child sub-vaults)" % len(v["children"]) if v["children"] else "")],
                ["APR", fmt_pct(v["apr_pct"])], ["TVL (vault + children account value)", fmt_usd(v["tvl"], 2)],
                ["total notional", fmt_usd(v["total_ntl_pos"], 2)], ["open positions", v["positions_total"]],
                ["maxDistributable", fmt_usd(v["max_distributable"], 2)], ["maxWithdrawable", fmt_usd(v["max_withdrawable"], 2)],
                ["leader fraction", "n/a" if lf is None else fmt_pct(lf * 100, 3)],
                ["leader commission", "n/a" if v["leader_commission"] is None else fmt_pct(v["leader_commission"] * 100)],
                ["allowDeposits / isClosed", "%s / %s" % (v["allow_deposits"], v["is_closed"])],
                ["followers (as returned)", v["followers"]]]
        for win in ("month", "allTime"):
            dd = v["drawdown"].get(win)
            if dd:
                rows.append(["%s peak-to-current drawdown" % win, "%s (peak %s, now %s, pnl %s)" % (
                    fmt_pct(dd["drawdown_pct"]), fmt_usd(dd["peak"]), fmt_usd(dd["current"]), fmt_usd(dd["pnl"]))])
        L += table(["field", "value"], rows) + [""]
        L += ["Drawdown is measured on account value and includes deposits / withdrawals.", ""]
        if v.get("children_skipped"):
            L += ["%d further child account(s) not inspected (cap %d)" % (v["children_skipped"], MAX_CHILD_ACCOUNTS), ""]
        arows = [[a["address"], a.get("role", "?"), "error: " + a["error"]] + [""] * 4 if a.get("error") else
                 [a["address"], a["role"], fmt_usd(a["margin"]["account_value"]), fmt_usd(a["margin"]["total_ntl_pos"]),
                  fmt_pct(a["margin"]["margin_util_pct"]), "n/a" if a["margin"]["leverage"] is None else "%.2fx" % a["margin"]["leverage"],
                  len(a["positions"])] for a in v["accounts"]]
        L += table(["account", "role", "account value", "notional", "margin util", "leverage", "positions"], arows) + [""]
        allp = sorted([p for a in v["accounts"] if "positions" in a for p in a["positions"]],
                      key=lambda p: (-p["position_value"], p["coin"]))
        if allp:
            L += ["Top %d open positions by notional (of %d):" % (min(top, len(allp)), len(allp)), ""]
            L += table(["account"] + POS_HEAD, [[short_addr(p["account"])] + _pos_row(p, coins) for p in allp[:top]]) + [""]
    h("Findings")
    shown = bc.sort_findings(findings)
    if md:
        L += _table_md(["severity", "code", "detail"], [[f.sev, f.code, f.msg] for f in shown]) if shown else ["(no findings)"]
    else:
        for f in shown:
            sev = "%-8s" % f.sev
            if color:
                sev = _COLORS[f.sev] + sev + "\033[0m"
            L.append("  [%s] %s: %s" % (sev, f.code, f.msg))
        if not shown:
            L.append("  (no findings)")
    L.append("")
    if delta is not None:
        h("Delta")
        if delta["baseline"]:
            L.append("baseline run: no prior state; recorded %d finding(s)" % len(delta["new"]))
        rows = [(lab, f) for lab, items in (("EVENT", delta["events"]), ("NEW", delta["new"]), ("CHANGED", delta["changed"]),
                                             ("RESOLVED", delta["resolved"])) for f in items]
        for lab, f in rows:
            L.append(("- **%s** [%s] %s: %s" if md else "  %-8s [%s] %s: %s") % (lab, f.sev, f.code, f.msg))
        if not rows:
            L.append("(no changes)")
        L.append("")
    if degraded:
        L += ["DEGRADED: data sources failed: %s (result may be incomplete; state not updated)" % ", ".join(degraded), ""]
    L += ["exit_code %d" % code, "", ("> " if md else "") + SCOPE_NOTE]
    return "\n".join(L)


def report_json(report):
    return json.loads(json.dumps(report, sort_keys=True, default=str))


# ---------------------------------------------------------------- CLI
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser():
    p = _Parser(prog="hyperliquid_monitor.py",
                description="Read-only Hyperliquid perps, funding & liquidation risk monitor (public Info API only)")
    p.add_argument("targets", nargs="*", metavar="TARGET", help="0x wallet address, coin ticker (BTC, ETH, ...) or 'hlp'")
    p.add_argument("--wallet", action="append", default=[], metavar="0xADDR")
    p.add_argument("--vault", action="append", default=[], metavar="0xADDR|hlp")
    p.add_argument("--hlp", action="store_true", help="inspect the HLP protocol vault")
    p.add_argument("--markets", action="store_true")
    p.add_argument("--coins", action="append", default=[], metavar="BTC,ETH,...")
    p.add_argument("--top", type=int, default=15, metavar="N")
    p.add_argument("--liq-crit-pct", type=float, default=5.0)
    p.add_argument("--liq-warn-pct", type=float, default=10.0)
    p.add_argument("--margin-util-warn", type=float, default=70.0)
    p.add_argument("--funding-apr-warn", type=float, default=50.0)
    p.add_argument("--basis-warn-bps", type=float, default=50.0)
    p.add_argument("--state", metavar="PATH")
    p.add_argument("--delta", action="store_true")
    p.add_argument("--format", choices=["text", "markdown", "md", "json"], default="text")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", metavar="PATH")
    p.add_argument("--fail-on", choices=FAIL_ON, default="medium")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--offline", metavar="PATH")
    p.add_argument("--no-color", action="store_true")
    return p


def _addr(v, what):
    if v.lower() == "hlp" and what == "vault":
        return HLP_VAULT
    if not ADDR_RE.match(v):
        raise UsageError("invalid %s address %r (need 0x + 40 hex chars)" % (what, v[:12]))
    return v.lower()


def parse_targets(args):
    wallets, vaults, coins = [], [], []

    def add(lst, x):
        if x not in lst:
            lst.append(x)

    for t in split_tokens(args.targets):
        if t.lower() == "hlp":
            add(vaults, HLP_VAULT)
        elif t.lower().startswith("0x"):
            add(wallets, _addr(t, "wallet"))
        elif TICKER_RE.match(t):
            add(coins, t.upper() if t.islower() else t)
        else:
            raise UsageError("unrecognised target %r (expected 0x address, coin ticker or 'hlp')" % t[:12])
    for w in split_tokens(args.wallet):
        add(wallets, _addr(w, "wallet"))
    for v in split_tokens(args.vault):
        add(vaults, _addr(v, "vault"))
    if args.hlp:
        add(vaults, HLP_VAULT)
    for c in split_tokens(args.coins):
        if not TICKER_RE.match(c):
            raise UsageError("invalid coin ticker %r" % c[:12])
        add(coins, c.upper() if c.islower() else c)
    return wallets, vaults, coins


def run(argv, out=None, now=None, err=None):
    out, err = out or sys.stdout, err or sys.stderr
    kind = detect_refusal(argv)
    if kind:
        print("%s (detected: %s)" % (REFUSAL, kind), file=err)
        return bc.EXIT_USAGE
    try:
        args = build_parser().parse_args(argv)
        if args.delta and not args.state:
            raise UsageError("--delta requires --state PATH")
        if args.timeout <= 0:
            raise UsageError("--timeout must be positive")
        if args.top < 1:
            raise UsageError("--top must be >= 1")
        for name in ("liq_crit_pct", "liq_warn_pct", "margin_util_warn", "funding_apr_warn", "basis_warn_bps"):
            if getattr(args, name) <= 0:
                raise UsageError("--%s must be positive" % name.replace("_", "-"))
        if args.liq_crit_pct > args.liq_warn_pct:
            raise UsageError("--liq-crit-pct must be <= --liq-warn-pct")
        wallets, vaults, coins = parse_targets(args)
        fx = None
        if args.offline:
            try:
                with open(args.offline, "r", encoding="utf-8") as fh:
                    fx = json.load(fh)
            except (OSError, ValueError) as e:
                raise UsageError("cannot read --offline fixture: %s" % e) from None
            if not isinstance(fx, dict):
                raise UsageError("--offline fixture must be a JSON object")
    except UsageError as e:
        print("error: %s" % e, file=err)
        return bc.EXIT_USAGE
    except SystemExit as e:  # --help
        return int(e.code or 0)

    fmt = "json" if args.json else ("markdown" if args.format == "md" else args.format)
    now = now or bc.utc_now()
    opts = {"liq_crit_pct": args.liq_crit_pct, "liq_warn_pct": args.liq_warn_pct, "margin_util_warn": args.margin_util_warn,
            "funding_apr_warn": args.funding_apr_warn, "basis_warn_bps": args.basis_warn_bps, "top": args.top}
    do_markets = args.markets or not (wallets or vaults)
    src = Source(timeout=args.timeout, offline=fx)
    findings = []

    raw = src.info({"type": "metaAndAssetCtxs"})
    markets = parse_markets(raw) if raw is not _MISSING else None
    if raw is not _MISSING and markets is None:
        src.degraded.add("metaAndAssetCtxs (unexpected shape)")
    report = {"tool": TOOL, "coins": coins, "opts": opts, "markets": None, "wallets": [], "vaults": []}
    selected = []
    if do_markets:
        if markets is None:
            report["markets"] = {"error": "metaAndAssetCtxs unavailable: market scan skipped"}
        else:
            pf = src.info({"type": "predictedFundings"})
            predicted_ok = attach_predicted(markets, pf) if pf is not _MISSING else False
            if pf is not _MISSING and not predicted_ok:
                src.degraded.add("predictedFundings (unexpected shape)")
            sel, unknown = select_markets(markets, coins, args.top)
            selected = [markets[c] for c in sel]
            for m in selected:
                findings += market_findings(m, opts)
            for c in unknown:
                findings.append(bc.Finding("INFO", "COIN_NOT_LISTED", "%s is not a live Hyperliquid perp market" % c,
                                           key="mkt:%s:UNLISTED" % c))
            report["markets"] = {"count": len(markets), "selected": selected, "unknown": unknown, "predicted_ok": predicted_ok,
                                 "extremes": [markets[c] for c in funding_extremes(markets)],
                                 "total_oi_usd": sum(m["oi_usd"] or 0 for m in markets.values()),
                                 "total_volume_24h": sum(m["volume_24h"] or 0 for m in markets.values())}
    for w in wallets:
        r, fl = audit_wallet(src, w, markets, opts)
        report["wallets"].append(r)
        findings += fl
    for v in vaults:
        r, fl = audit_vault(src, v, markets, opts)
        report["vaults"].append(r)
        findings += fl

    degraded = sorted(src.degraded)
    snap = make_snapshot(report["wallets"], report["vaults"], selected, findings)
    key_src = "|".join(["w:" + ",".join(sorted(wallets)), "v:" + ",".join(sorted(vaults)),
                        "m:%s" % do_markets, "c:" + ",".join(sorted(c.lower() for c in coins))])
    sk = "hl:" + hashlib.sha1(key_src.encode()).hexdigest()[:12]
    store = bc.StateStore(args.state) if args.state else None
    prev = store.get(sk) if store else None
    events, delta = [], None
    if args.delta:
        if prev is None:
            delta = {"baseline": True, "events": [], "new": list(bc.sort_findings(findings)), "changed": [], "resolved": []}
        else:
            events = compute_events(prev, snap, opts) if not degraded else []
            dd = bc.diff_findings(prev.get("findings", []), findings)
            delta = {"baseline": False, "events": events, "new": dd["NEW"], "changed": dd["CHANGED"], "resolved": dd["RESOLVED"]}
    if store and not degraded:
        store.put(sk, snap)

    all_f = findings + events
    code = bc.exit_code([] if args.fail_on == "none" else all_f, bool(degraded),
                        "medium" if args.fail_on == "none" else args.fail_on)
    endpoints = src.endpoints if fx is None else ["offline:" + os.path.basename(args.offline)]
    header = bc.snapshot_header(TOOL, endpoints, None, now=now)
    if fmt == "json":
        payload = {"tool": TOOL, "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "scope_note": SCOPE_NOTE,
                   "degraded_sources": degraded, "report": report_json(report),
                   "findings": [f.to_dict() for f in bc.sort_findings(all_f)],
                   "delta": None if delta is None else {k: (v if k == "baseline" else [f.to_dict() for f in v]) for k, v in delta.items()},
                   "exit_code": code}
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    else:
        color = (fmt == "text" and not args.out and not args.no_color and not os.environ.get("NO_COLOR")
                 and getattr(out, "isatty", lambda: False)())
        text = render(report, findings, delta, code, degraded, header, fmt, color)
    if args.out:
        try:
            d = os.path.dirname(os.path.abspath(args.out))
            os.makedirs(d, exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as e:
            print("error: cannot write --out: %s" % e, file=err)
            return bc.EXIT_USAGE
        print("wrote %s (exit %d)" % (args.out, code), file=err)
    else:
        print(text, file=out)
    return code


def main():
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
