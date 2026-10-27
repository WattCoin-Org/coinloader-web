#!/usr/bin/env python3
"""Bitcoin Wallet & UTXO Privacy / Fee Hygiene Auditor (strictly read-only, stdlib + bot_common).

Validates one or more Bitcoin mainnet addresses (Base58Check, Bech32 BIP-173, Bech32m BIP-350), reads their
public state from the Mempool.space REST API (fallback Blockstream Esplora) or an --offline fixture, and reports
UTXO fragmentation / dust / stranded inputs, a consolidation cost-vs-savings matrix, address-reuse and
Common-Input-Ownership (CIOH) privacy exposure, dusting-attack suspects and Ordinals-inscription protection.
It prints coin-control commands for the owner to run themselves; it never signs, builds or broadcasts anything and
refuses private keys, seed phrases, extended private keys and PSBTs.  Exit codes: 0 clean, 1 MEDIUM, 2 HIGH,
3 CRITICAL, 10 bad input / refusal, 11 degraded data sources.

Offline fixture (JSON): {"fees": {...}, "mempool_blocks": [...], "blockstream_fees": {"1": 9.1, ...},
"prices": {"USD": 100000}, "addresses": {addr: {"stats": {...}, "utxos": [...] | null, "txs": [...]}},
"txs": {txid: <esplora tx>}} using the same shapes as the Esplora / Mempool.space endpoints.
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

TOOL = "btc-utxo-hygiene"
SCOPE_NOTE = ("SCOPE_NOTE: Strictly read-only: only public Mempool.space / Blockstream Esplora REST GET endpoints "
              "(address stats, UTXO set, recent transactions, fee estimates, prices) or an --offline fixture. Never "
              "accepts or asks for private keys, WIF, xprv/yprv/zprv, seed phrases or PSBTs; no transaction is built, "
              "signed or broadcast by the tool; coin-control commands are displayed for the owner to run in their own "
              "wallet. Heuristics (CIOH, change detection, dusting, inscription envelopes) are probabilistic, cover "
              "only the recent transactions and small UTXOs it states it checked, and \"no findings\" never means "
              "\"private\" or \"safe to sweep\". P3... addresses are assumed to be nested SegWit (P2SH-P2WPKH). "
              "No financial, legal or tax advice. Refuses: targeting third-party wallets for exploitation or "
              "deanonymisation, ranking wallets by balance, or building dust-attack target lists.")

MEMPOOL = "https://mempool.space/api"
BLOCKSTREAM = "https://blockstream.info/api"
APIS = [MEMPOOL, BLOCKSTREAM]

# type -> input spend vB, output vB, dust limit (sats)
SCRIPT = {
    "P2PKH": {"in_vb": 148.0, "out_vb": 34, "dust": 546},
    "P2SH-P2WPKH": {"in_vb": 91.0, "out_vb": 32, "dust": 540},
    "P2WPKH": {"in_vb": 68.0, "out_vb": 31, "dust": 294},
    "P2WSH": {"in_vb": 104.5, "out_vb": 43, "dust": 330},
    "P2TR": {"in_vb": 57.5, "out_vb": 43, "dust": 330},
}
ENVELOPE_HEX = "0063036f7264"        # OP_0 OP_IF PUSH3 "ord"
HARD_DUST = 546
SMALL_LOOKUP_MAX = 10000
DUSTING_MAX = 1000
DUSTING_WALLET_MIN = 100000
ROUND_UNIT = 10000
REF_RATES = (5, 10, 20, 50, 100)
WINDOW_RATES = (1, 5, 10, 20)
FUTURE_RATES = (50, 100)
MAX_TX_VB = 100000
MAX_ADDRESSES = 25
FEE_NAMES = ("fastestFee", "halfHourFee", "hourFee", "economyFee", "minimumFee")
BUCKETS = (("<=546 (hard dust / inscription-suspect)", 0, 546), ("547-1,000 (sub-1k micro)", 547, 1000),
           ("1,001-5,000", 1001, 5000), ("5,001-100,000", 5001, 100000), (">100,000", 100001, 10 ** 18))
SCORE_PENALTY = {"INFO": 0, "LOW": 3, "MEDIUM": 8, "HIGH": 15, "CRITICAL": 30}
OUT_TYPES = ("P2WPKH", "P2TR")
ESPLORA_TYPES = {"p2pkh": "P2PKH", "p2sh": "P2SH-P2WPKH", "v0_p2wpkh": "P2WPKH", "v0_p2wsh": "P2WSH", "v1_p2tr": "P2TR"}


# ---------------------------------------------------------------- address validation
class AddressError(ValueError):
    pass


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_CONST = 1
BECH32M_CONST = 0x2bc830a3


def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def b58check_decode(s):
    """Base58Check -> (version byte, payload). Raises AddressError on bad characters or checksum."""
    n = 0
    for ch in s:
        i = B58.find(ch)
        if i < 0:
            raise AddressError("invalid Base58 character")
        n = n * 58 + i
    raw = b"\x00" * (len(s) - len(s.lstrip("1"))) + n.to_bytes((n.bit_length() + 7) // 8, "big")
    if len(raw) < 5:
        raise AddressError("Base58 payload too short")
    body, chk = raw[:-4], raw[-4:]
    if sha256d(body)[:4] != chk:
        raise AddressError("bad Base58Check checksum")
    return body[0], body[1:]


def bech32_polymod(values):
    gen = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            if (b >> i) & 1:
                chk ^= gen[i]
    return chk


def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_decode(s):
    """-> (hrp, data5 without checksum, 'bech32' | 'bech32m'). Raises AddressError."""
    if any(ord(c) < 33 or ord(c) > 126 for c in s):
        raise AddressError("invalid character in Bech32 string")
    if s.lower() != s and s.upper() != s:
        raise AddressError("mixed-case Bech32 string")
    s = s.lower()
    pos = s.rfind("1")
    if pos < 1 or pos + 7 > len(s) or len(s) > 90:
        raise AddressError("bad Bech32 length or separator")
    hrp = s[:pos]
    try:
        data = [BECH32_CHARSET.index(c) for c in s[pos + 1:]]
    except ValueError:
        raise AddressError("invalid Bech32 data character") from None
    const = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if const == BECH32_CONST:
        return hrp, data[:-6], "bech32"
    if const == BECH32M_CONST:
        return hrp, data[:-6], "bech32m"
    raise AddressError("bad Bech32/Bech32m checksum")


def convertbits(data, frombits, tobits, pad=True):
    acc, bits, ret, maxv = 0, 0, [], (1 << tobits) - 1
    for v in data:
        if v < 0 or v >> frombits:
            return None
        acc = (acc << frombits) | v
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def _parse_segwit(a):
    hrp, data, spec = bech32_decode(a)
    if hrp != "bc":
        raise AddressError("wrong human-readable part %r (mainnet 'bc' only)" % hrp[:8])
    if not data:
        raise AddressError("empty witness data")
    ver = data[0]
    prog = convertbits(data[1:], 5, 8, False)
    if ver > 16 or prog is None or not 2 <= len(prog) <= 40:
        raise AddressError("invalid witness program")
    program = bytes(prog)
    if ver == 0:
        if spec != "bech32":
            raise AddressError("witness v0 must use Bech32 (BIP-173), not Bech32m")
        if len(program) == 20:
            typ = "P2WPKH"
        elif len(program) == 32:
            typ = "P2WSH"
        else:
            raise AddressError("witness v0 program must be 20 or 32 bytes")
    elif ver == 1:
        if spec != "bech32m":
            raise AddressError("witness v1 must use Bech32m (BIP-350), not Bech32")
        if len(program) != 32:
            raise AddressError("witness v1 (Taproot) program must be 32 bytes")
        typ = "P2TR"
    else:
        raise AddressError("unsupported witness version %d" % ver)
    return {"address": a.lower(), "type": typ, "witness_version": ver, "program": program.hex(), "checksum": spec}


def parse_address(raw):
    """Validate a Bitcoin mainnet address. Returns {address, type, ...} or raises AddressError."""
    a = (raw or "").strip()
    if not a:
        raise AddressError("empty address")
    low = a.lower()
    if low.startswith(("tb1", "bcrt1")) or a[0] in "mn2":
        raise AddressError("testnet/regtest address rejected (mainnet only)")
    if low.startswith("bc1"):
        return _parse_segwit(a)
    if a[0] in "13":
        if not 26 <= len(a) <= 35:
            raise AddressError("bad legacy address length")
        ver, payload = b58check_decode(a)
        if ver in (0x6f, 0xc4):
            raise AddressError("testnet address rejected (mainnet only)")
        if ver == 0x00 and a[0] == "1":
            typ = "P2PKH"
        elif ver == 0x05 and a[0] == "3":
            typ = "P2SH-P2WPKH"
        else:
            raise AddressError("unsupported Base58 version byte 0x%02x" % ver)
        if len(payload) != 20:
            raise AddressError("legacy payload must be 20 bytes")
        return {"address": a, "type": typ, "witness_version": None, "program": payload.hex(), "checksum": "base58check"}
    raise AddressError("unrecognised address format")


def split_tokens(values):
    return [t for v in values for t in re.split(r"[,\s]+", v) if t]


# ---------------------------------------------------------------- secret / signing refusal
_WIF_CHARS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
_XPRV_PREFIXES = ("xprv", "yprv", "zprv", "Yprv", "Zprv", "tprv", "uprv", "vprv", "Uprv", "Vprv")
_REFUSED_FLAGS = ("--sign", "--psbt", "--wif", "--seed", "--mnemonic", "--privkey", "--private-key", "--xprv",
                  "--broadcast", "--passphrase", "--key")
REFUSAL = ("REFUSED: this tool is strictly read-only and never accepts private keys, WIF, extended private keys "
           "(xprv/yprv/zprv), seed phrases or PSBTs, and never signs or broadcasts anything. Pass public addresses "
           "only. The rejected input was not stored or echoed; if it was a real secret, treat it as exposed (it may "
           "sit in your shell history) and move the funds to a fresh wallet.")


def detect_secret(token):
    """Names the kind of secret a token looks like (never returns the token itself), else None."""
    t = token.strip()
    if t.startswith(_XPRV_PREFIXES) and len(t) >= 8 and _WIF_CHARS.match(t):
        return "extended private key"
    if _WIF_CHARS.match(t) and ((len(t) == 51 and t[0] in "59") or (len(t) == 52 and t[0] in "KLc")):
        return "WIF private key"
    if re.fullmatch(r"[0-9a-fA-F]{64}", t):
        return "raw 32-byte hex (possible private key)"
    if t.startswith("cHNidP8") or t.lower().startswith("70736274ff"):
        return "PSBT"
    return None


def detect_refusal(argv):
    """Scans raw argv; returns a kind string when the invocation must be refused."""
    for a in argv:
        if a.split("=", 1)[0] in _REFUSED_FLAGS:
            return "signing/secret option"
    words = []
    for a in argv:
        if a.startswith("-") and not a.startswith("--") and len(a) < 3:
            continue
        for t in split_tokens([a]):
            kind = detect_secret(t)
            if kind:
                return kind
            if re.fullmatch(r"[a-z]{3,8}", t):
                words.append(t)
    if len(words) >= 11:
        return "seed phrase"
    return None


# ---------------------------------------------------------------- weights, dust, buckets
def tx_vsize(types_, out_vb):
    """vsize = 10.5 + sum(input vB) + output vB (SegWit/Taproot/mixed); 10 + ... when every input is legacy P2PKH."""
    overhead = 10.0 if types_ and all(t == "P2PKH" for t in types_) else 10.5
    return overhead + sum(SCRIPT[t]["in_vb"] for t in types_) + out_vb


def fee_for(vsize, rate):
    return int(math.ceil(round(vsize * rate, 6)))


def bucket_of(value):
    for label, lo, hi in BUCKETS:
        if lo <= value <= hi:
            return label
    return BUCKETS[-1][0]


def is_round(v):
    return v >= ROUND_UNIT and v % ROUND_UNIT == 0


def stranded_at(utxos, rate, mult):
    strict = [u for u in utxos if u["value"] <= u["in_vb"] * rate]
    cons = [u for u in utxos if u["value"] <= u["in_vb"] * rate * mult]
    return {"rate": rate, "strict_count": len(strict), "strict_sats": sum(u["value"] for u in strict),
            "conservative_count": len(cons), "conservative_sats": sum(u["value"] for u in cons)}


def batches_of(inputs, out_vb):
    """Greedy canonical-order batches whose vsize stays <= MAX_TX_VB."""
    out, cur = [], []
    for u in inputs:
        if cur and tx_vsize([x["type"] for x in cur] + [u["type"]], out_vb) > MAX_TX_VB:
            out.append(cur)
            cur = []
        cur.append(u)
    if cur:
        out.append(cur)
    return out


def plan_consolidation(utxos, rate, out_type, mult, price=None):
    """Consolidate every economical, non-protected UTXO (value > input_vB*rate*mult) into one output per batch."""
    out_vb = SCRIPT[out_type]["out_vb"]
    eligible = [u for u in utxos if not u["protect"] and u["value"] > u["in_vb"] * rate * mult]
    plan = {"out_type": out_type, "rate": rate, "eligible": len(eligible), "inputs": eligible, "batches": [],
            "tx_count": 0, "vsize": 0.0, "fee_sats": 0, "fee_usd": None, "input_sats": 0, "output_sats": 0,
            "viable": False, "sum_in_vb": 0.0, "future": {}, "breakeven_rate": None}
    if len(eligible) < 2:
        return plan
    bs = batches_of(eligible, out_vb)
    vsize = sum(tx_vsize([u["type"] for u in b], out_vb) for b in bs)
    fee = sum(fee_for(tx_vsize([u["type"] for u in b], out_vb), rate) for b in bs)
    total = sum(u["value"] for u in eligible)
    sum_in_vb = sum(u["in_vb"] for u in eligible)
    cons_in_vb = SCRIPT[out_type]["in_vb"] * len(bs)
    saved_vb = sum_in_vb - cons_in_vb
    plan.update(batches=bs, tx_count=len(bs), vsize=vsize, fee_sats=fee, fee_usd=usd(fee, price), input_sats=total,
                output_sats=total - fee, sum_in_vb=sum_in_vb,
                viable=(total - fee) > SCRIPT[out_type]["dust"] and saved_vb > 0)
    for fr in FUTURE_RATES:
        frag, cons = int(math.ceil(sum_in_vb * fr)), int(math.ceil(cons_in_vb * fr))
        plan["future"][str(fr)] = {"fragmented_sats": frag, "consolidated_sats": cons, "net_savings_sats": frag - cons - fee,
                                   "net_savings_usd": usd(frag - cons - fee, price)}
    plan["breakeven_rate"] = round(fee / saved_vb, 2) if saved_vb > 0 else None
    return plan


def usd(sats, price):
    return None if price is None else round(sats / 1e8 * price, 2)


def hygiene_score(findings):
    return max(0, 100 - sum(SCORE_PENALTY[f.sev] for f in findings))


# ---------------------------------------------------------------- data source
def _valid_json(data):
    return data is not None and not (isinstance(data, dict) and set(data) <= {"_raw", "_error"} and data)


def _nearest(est, target):
    keys = []
    for k, v in (est or {}).items():
        try:
            keys.append((abs(int(k) - target), int(k), float(v)))
        except (TypeError, ValueError):
            continue
    return min(keys)[2] if keys else None


def fees_from_blockstream(est):
    out = {"fastestFee": _nearest(est, 1), "halfHourFee": _nearest(est, 3), "hourFee": _nearest(est, 6),
           "economyFee": _nearest(est, 144), "minimumFee": _nearest(est, 504)}
    return out if all(v is not None for v in out.values()) else None


class Source:
    """Mempool.space first, Blockstream second; or a deterministic --offline fixture."""

    def __init__(self, timeout=20, offline=None):
        self.timeout, self.fx = timeout, offline
        self.degraded, self.endpoints, self.fallbacks, self.notes = set(), set(), [], []
        self.too_many = set()
        self._bs_fees = None

    def _get(self, path, bases=APIS):
        for n, base in enumerate(bases):
            res = bc.http_json(base + path, retries=1, timeout=self.timeout)
            if res.status == 200 and _valid_json(res.data):
                self.endpoints.add(base)
                if n:
                    fb = "%s failed -> %s" % (bases[0], base)
                    if fb not in self.fallbacks:
                        self.fallbacks.append(fb)
                return res.data
            if "too many" in json.dumps(res.data).lower():
                self.too_many.add(path)
        return None

    def _fx_addr(self, addr, key):
        return ((self.fx or {}).get("addresses") or {}).get(addr, {}).get(key)

    def address_stats(self, addr):
        d = self._fx_addr(addr, "stats") if self.fx is not None else self._get("/address/%s" % addr)
        return d if isinstance(d, dict) else None

    def utxos(self, addr):
        d = self._fx_addr(addr, "utxos") if self.fx is not None else self._get("/address/%s/utxo" % addr)
        return d if isinstance(d, list) else None

    def txs(self, addr):
        d = self._fx_addr(addr, "txs") if self.fx is not None else self._get("/address/%s/txs" % addr)
        return d if isinstance(d, list) else None

    def blockstream_fees(self):
        if self._bs_fees is None:
            d = (self.fx or {}).get("blockstream_fees") if self.fx is not None else self._get("/fee-estimates", [BLOCKSTREAM])
            self._bs_fees = d if isinstance(d, dict) else {}
        return self._bs_fees or None

    def fees(self):
        """-> (recommended dict | None, source label)."""
        d = (self.fx or {}).get("fees") if self.fx is not None else self._get("/v1/fees/recommended", [MEMPOOL])
        if isinstance(d, dict) and all(isinstance(d.get(k), (int, float)) for k in FEE_NAMES):
            return {k: d[k] for k in FEE_NAMES}, "mempool.space"
        derived = fees_from_blockstream(self.blockstream_fees())
        if derived:
            if self.fx is None:
                self.fallbacks.append("fees: mempool.space recommended failed -> blockstream fee-estimates")
            return derived, "blockstream-derived"
        return None, None

    def mempool_blocks(self):
        d = (self.fx or {}).get("mempool_blocks") if self.fx is not None else self._get("/v1/fees/mempool-blocks", [MEMPOOL])
        return d if isinstance(d, list) else None

    def price_usd(self):
        d = (self.fx or {}).get("prices") if self.fx is not None else self._get("/v1/prices", [MEMPOOL])
        v = d.get("USD") if isinstance(d, dict) else None
        return float(v) if isinstance(v, (int, float)) and v > 0 else None

    def tx(self, txid):
        if self.fx is not None:
            d = ((self.fx.get("txs") or {}).get(txid))
        else:
            d = self._get("/tx/%s" % txid)
        return d if isinstance(d, dict) else None

    def envelope(self, txid):
        """True / False when the creating tx's witnesses were inspected, None when the lookup failed."""
        t = self.tx(txid)
        if not t or not isinstance(t.get("vin"), list):
            return None
        for vin in t["vin"]:
            for w in (vin.get("witness") or []) if isinstance(vin, dict) else []:
                if isinstance(w, str) and ENVELOPE_HEX in w.lower():
                    return True
        return False


# ---------------------------------------------------------------- per-address collection
def normalize_utxos(raw, info):
    out = []
    for u in raw or []:
        if not (isinstance(u, dict) and isinstance(u.get("txid"), str) and isinstance(u.get("vout"), int)
                and isinstance(u.get("value"), int) and not isinstance(u.get("value"), bool)):
            continue
        st = u.get("status") if isinstance(u.get("status"), dict) else {}
        sc = SCRIPT[info["type"]]
        out.append({"address": info["address"], "type": info["type"], "txid": u["txid"].lower(), "vout": u["vout"],
                    "value": u["value"], "confirmed": bool(st.get("confirmed")), "height": st.get("block_height"),
                    "in_vb": sc["in_vb"], "dust_limit": sc["dust"], "protect": [], "envelope": None})
    return sorted(out, key=lambda u: (u["value"], u["txid"], u["vout"]))


def stat_totals(stats):
    cs, ms = (stats or {}).get("chain_stats") or {}, (stats or {}).get("mempool_stats") or {}
    g = lambda d, k: int(d.get(k) or 0)  # noqa: E731
    return {"funded_txo_count": g(cs, "funded_txo_count") + g(ms, "funded_txo_count"),
            "funded_txo_sum": g(cs, "funded_txo_sum") + g(ms, "funded_txo_sum"),
            "spent_txo_count": g(cs, "spent_txo_count") + g(ms, "spent_txo_count"),
            "spent_txo_sum": g(cs, "spent_txo_sum") + g(ms, "spent_txo_sum"),
            "tx_count": g(cs, "tx_count") + g(ms, "tx_count"),
            "chain_tx_count": g(cs, "tx_count"), "mempool_tx_count": g(ms, "tx_count")}


def analyze_txs(addrs, txs):
    """CIOH co-spends, cross-address links, round-number change and script-type mismatch over recent txs."""
    addrs = set(addrs)
    per = {a: {"spend_txs": 0, "co_addrs": set(), "cospend_txids": [], "round_txids": [], "mismatch_txids": []}
           for a in addrs}
    cross, seen = {}, set()
    for tx in txs:
        if not isinstance(tx, dict) or not isinstance(tx.get("txid"), str) or tx["txid"] in seen:
            continue
        seen.add(tx["txid"])
        vin = [v for v in tx.get("vin") or [] if isinstance(v, dict) and isinstance(v.get("prevout"), dict)]
        in_addrs = [v["prevout"].get("scriptpubkey_address") for v in vin]
        ours = sorted({a for a in in_addrs if a in addrs})
        if not ours:
            continue
        txid = tx["txid"]
        distinct = {a for a in in_addrs if a}
        vouts = [o for o in tx.get("vout") or [] if isinstance(o, dict) and o.get("scriptpubkey_type") != "op_return"]
        for a in ours:
            per[a]["spend_txs"] += 1
        if len(vin) >= 2 and len(distinct) >= 2:
            for a in ours:
                per[a]["co_addrs"] |= distinct - {a}
                per[a]["cospend_txids"].append(txid)
        if len(ours) >= 2:
            cross[txid] = ours
        if len(vouts) == 2:
            if sum(1 for o in vouts if is_round(o.get("value") or 0)) == 1:
                for a in ours:
                    per[a]["round_txids"].append(txid)
            in_types = {v["prevout"].get("scriptpubkey_type") for v in vin}
            if len(in_types) == 1:
                t = next(iter(in_types))
                if sum(1 for o in vouts if o.get("scriptpubkey_type") == t) == 1:
                    for a in ours:
                        per[a]["mismatch_txids"].append(txid)
    return {"per_address": per, "cross": cross, "txs_seen": len(seen)}


def _sev_count(n, lo, mid, hi=None, crit=None):
    if crit is not None and n >= crit:
        return "CRITICAL"
    if hi is not None and n >= hi:
        return "HIGH"
    return "MEDIUM" if n >= mid else "LOW" if n >= lo else None


# ---------------------------------------------------------------- wallet audit
def audit_wallet(src, infos, opts):
    """Returns (report, findings). Never raises on data-source failures: they are recorded in src.degraded."""
    mult, protect_user = opts["mult"], set(opts.get("protect", []))
    price = src.price_usd()
    fees, fee_src = src.fees()
    if fees is None:
        src.degraded.add("fees")
    bs_floor = (src.blockstream_fees() or {}).get("504")
    mblocks = src.mempool_blocks()

    addr_reports, all_utxos, all_txs = [], [], []
    for info in infos:
        a = info["address"]
        stats = src.address_stats(a)
        if stats is None:
            src.degraded.add("stats:" + a)
        raw_utxos = src.utxos(a)
        utxos = normalize_utxos(raw_utxos, info)
        st = stat_totals(stats)
        expected = max(0, st["funded_txo_count"] - st["spent_txo_count"]) if stats else None
        complete = raw_utxos is not None
        if complete and expected is not None and len(utxos) < expected and expected > 500:
            complete = False
        if not complete:
            src.degraded.add("utxo:" + a)
        txs = src.txs(a)
        if txs is None:
            src.degraded.add("txs:" + a)
        txs = (txs or [])[:opts["max_txs"]]
        all_txs.extend(txs)
        all_utxos.extend(utxos)
        addr_reports.append({"address": a, "type": info["type"], "stats": st, "stats_ok": stats is not None,
                             "utxo_count": len(utxos), "expected_utxos": expected, "utxo_complete": complete,
                             "balance_sats": sum(u["value"] for u in utxos), "txs_analyzed": len(txs)})
    all_utxos.sort(key=lambda u: (u["value"], u["txid"], u["vout"]))
    total_sats = sum(u["value"] for u in all_utxos)

    # --- creating-tx witness scan on small UTXOs (canonical order, distinct txids, capped)
    seen, capped = {}, 0
    for u in all_utxos:
        if u["value"] > SMALL_LOOKUP_MAX:
            break
        if u["txid"] not in seen:
            if len(seen) >= opts["max_lookups"]:
                capped += 1
                u["envelope"], u["lookup"] = None, "capped"
                continue
            seen[u["txid"]] = src.envelope(u["txid"])
        u["envelope"] = seen[u["txid"]]
        u["lookup"] = "ok" if u["envelope"] is not None else "failed"
    failed = sum(1 for v in seen.values() if v is None)
    if failed:
        src.degraded.add("tx-lookups")
    for u in all_utxos:
        if u["envelope"] is True:
            u["protect"].append("ENVELOPE")
        if u["value"] <= SMALL_LOOKUP_MAX and u["envelope"] is None:
            u["protect"].append("UNVERIFIED")
        if u["value"] <= HARD_DUST:
            u["protect"].append("DUST")
        if "%s:%d" % (u["txid"], u["vout"]) in protect_user:
            u["protect"].append("USER")
        u["protect"] = ["PROTECTED:" + p for p in u["protect"]]
        if total_sats > DUSTING_WALLET_MIN and u["value"] <= DUSTING_MAX and "PROTECTED:ENVELOPE" not in u["protect"]:
            u["protect"].append("PROTECTED:DUSTING")      # suspected dust attack: freeze, never sweep
    scan = {"checked_txids": len(seen), "envelope_hits": sum(1 for u in all_utxos if u["envelope"] is True),
            "lookup_failures": failed, "unchecked_capped": capped, "cap": opts["max_lookups"],
            "small_utxos": sum(1 for u in all_utxos if u["value"] <= SMALL_LOOKUP_MAX)}

    # --- rates, stranded table
    rates = []
    for n in FEE_NAMES:
        if fees:
            rates.append((n, float(fees[n])))
    rates += [("ref %d" % r, float(r)) for r in REF_RATES]
    stranded = [dict(stranded_at(all_utxos, r, mult), name=n) for n, r in rates]

    # --- consolidation plan + matrix
    if opts.get("target_fee") is not None:
        plan_rate, plan_src = float(opts["target_fee"]), "--target-fee"
    elif fees:
        plan_rate, plan_src = float(fees["economyFee"]), "economyFee"
    else:
        plan_rate, plan_src = 1.0, "default (fees unavailable)"
    main_plan = plan_consolidation(all_utxos, plan_rate, opts["consolidate_to"], mult, price)
    scenarios = []
    if fees:
        scenarios += [("fastestFee", float(fees["fastestFee"])), ("economyFee", float(fees["economyFee"]))]
    if opts.get("target_fee") is not None:
        scenarios.append(("target-fee", float(opts["target_fee"])))
    scenarios += [("window %d" % w, float(w)) for w in WINDOW_RATES]
    matrix = []
    for ot in OUT_TYPES:
        for name, r in scenarios:
            p = plan_consolidation(all_utxos, r, ot, mult, price)
            matrix.append({"out_type": ot, "scenario": name, "rate": r, "eligible": p["eligible"], "tx_count": p["tx_count"],
                           "vsize": p["vsize"], "fee_sats": p["fee_sats"], "fee_usd": p["fee_usd"], "viable": p["viable"],
                           "future": p["future"], "breakeven_rate": p["breakeven_rate"]})
    econ = float(fees["economyFee"]) if fees else None
    n50 = (main_plan["future"].get("50") or {}).get("net_savings_sats", 0)
    window_open = bool(econ is not None and econ <= opts["window_rate"] and main_plan["viable"] and n50 > 0)

    # --- privacy
    txa = analyze_txs([i["address"] for i in infos], all_txs)

    # --- coin control
    freeze_list = [u for u in all_utxos if u["protect"]]
    freeze_keys = {(u["txid"], u["vout"]) for u in freeze_list}
    cons_keys = {(u["txid"], u["vout"]) for u in main_plan["inputs"]}
    leave = [u for u in all_utxos if (u["txid"], u["vout"]) not in freeze_keys | cons_keys]

    report = {
        "addresses": addr_reports, "price_usd": price,
        "totals": {"utxos": len(all_utxos), "confirmed": sum(1 for u in all_utxos if u["confirmed"]),
                   "unconfirmed": sum(1 for u in all_utxos if not u["confirmed"]), "sats": total_sats,
                   "btc": round(total_sats / 1e8, 8), "usd": usd(total_sats, price)},
        "fees": {"recommended": fees, "source": fee_src, "blockstream_504_floor": bs_floor},
        "mempool_blocks": [{"nTx": b.get("nTx"), "medianFee": b.get("medianFee"), "feeRange": b.get("feeRange")}
                           for b in (mblocks or [])[:3] if isinstance(b, dict)],
        "buckets": [{"label": l, "count": sum(1 for u in all_utxos if lo <= u["value"] <= hi),
                     "sats": sum(u["value"] for u in all_utxos if lo <= u["value"] <= hi)} for l, lo, hi in BUCKETS],
        "by_type": {t: sum(1 for u in all_utxos if u["type"] == t) for t in SCRIPT if any(u["type"] == t for u in all_utxos)},
        "min_value_multiple": mult, "stranded": stranded, "inscription_scan": scan,
        "consolidation": {"rate": plan_rate, "rate_source": plan_src, "out_type": opts["consolidate_to"],
                          "eligible": main_plan["eligible"], "tx_count": main_plan["tx_count"],
                          "vsize": main_plan["vsize"], "fee_sats": main_plan["fee_sats"], "fee_usd": main_plan["fee_usd"],
                          "input_sats": main_plan["input_sats"], "output_sats": main_plan["output_sats"],
                          "viable": main_plan["viable"], "future": main_plan["future"],
                          "breakeven_rate": main_plan["breakeven_rate"], "window_open": window_open,
                          "window_rate": opts["window_rate"], "protected": len(freeze_list),
                          "batches": [[_op(u) for u in b] for b in main_plan["batches"]], "matrix": matrix},
        "privacy": {"txs_analyzed": txa["txs_seen"],
                    "per_address": {a: {"spend_txs": v["spend_txs"], "co_addresses": sorted(v["co_addrs"]),
                                        "cospend_txids": sorted(set(v["cospend_txids"])),
                                        "round_txids": sorted(set(v["round_txids"])),
                                        "mismatch_txids": sorted(set(v["mismatch_txids"]))} for a, v in sorted(txa["per_address"].items())},
                    "cross_links": {t: v for t, v in sorted(txa["cross"].items())}},
        "coin_control": {"freeze": [dict(_op(u), value=u["value"], address=u["address"], reasons=list(u["protect"]))
                                    for u in freeze_list],
                         "consolidate": [_op(u) for u in main_plan["inputs"]], "leave_count": len(leave)},
        "utxos": [{k: u[k] for k in ("address", "type", "txid", "vout", "value", "confirmed", "height", "protect", "envelope")}
                  for u in all_utxos],
    }
    findings = build_findings(report, addr_reports, all_utxos, txa, opts, total_sats)
    report["score"] = hygiene_score(findings)
    for ar in addr_reports:
        ar["score"] = hygiene_score([f for f in findings if f.evidence.get("address") == ar["address"]])
    return report, findings


def _op(u):
    return {"txid": u["txid"], "vout": u["vout"]}


def build_findings(report, addr_reports, utxos, txa, opts, total_sats):
    findings = []

    def add(sev, code, msg, a=None, suffix="", **ev):
        if a:
            ev["address"] = a
        findings.append(bc.Finding(sev, code, msg, ev, key="%s:%s%s" % (a or "wallet", code, suffix)))

    ref_rate = (report["fees"]["recommended"] or {}).get("economyFee", 1.0)
    for ar in addr_reports:
        a, t, st = ar["address"], ar["type"], ar["stats"]
        mine = [u for u in utxos if u["address"] == a]
        if not ar["utxo_complete"]:
            add("INFO", "UTXO_SET_INCOMPLETE", "UTXO set for %s could not be read in full (%d of ~%s); counts are lower bounds"
                % (a, ar["utxo_count"], ar["expected_utxos"] if ar["expected_utxos"] is not None else "?"), a)
        if t == "P2PKH" and (mine or st["funded_txo_count"]):
            add("LOW", "LEGACY_SCRIPT_TYPE", "%s is legacy P2PKH: each input costs %.0f vB vs %.0f vB for P2WPKH and %.1f vB for P2TR"
                % (a, SCRIPT["P2PKH"]["in_vb"], SCRIPT["P2WPKH"]["in_vb"], SCRIPT["P2TR"]["in_vb"]), a)
        n = st["funded_txo_count"]
        if n > 1:
            sev = "CRITICAL" if n >= 100 and ar["balance_sats"] > DUSTING_WALLET_MIN else "HIGH" if n >= 20 else "MEDIUM" if n >= 5 else "LOW"
            add(sev, "ADDRESS_REUSE", "%s received %d separate outputs (funded_txo=%d, spent_txo=%d): every receipt and spend is "
                "publicly linked to one address" % (a, n, n, st["spent_txo_count"]), a,
                funded_txo_count=n, spent_txo_count=st["spent_txo_count"])
        sev = _sev_count(len(mine), 10, 50, 200)
        if sev:
            add(sev, "UTXO_FRAGMENTATION", "%s holds %d UTXOs (%d sats): spending them costs far more than one consolidated input"
                % (a, len(mine), ar["balance_sats"]), a, utxo_count=len(mine))
        s = stranded_at(mine, ref_rate, opts["mult"])
        if s["strict_count"]:
            add("MEDIUM" if s["strict_count"] >= 10 else "LOW", "STRANDED_UTXOS",
                "%s has %d UTXO(s) (%d sats) that cost more than their value to spend at %.1f sat/vB (%d at the conservative %gx margin)"
                % (a, s["strict_count"], s["strict_sats"], ref_rate, s["conservative_count"], opts["mult"]), a,
                rate=ref_rate, **{k: s[k] for k in ("strict_count", "strict_sats", "conservative_count", "conservative_sats")})
        env = [u for u in mine if "PROTECTED:ENVELOPE" in u["protect"]]
        if env:
            add("INFO", "INSCRIPTION_PROTECTED", "%d UTXO(s) on %s carry an Ordinals envelope in their creating tx: excluded from consolidation, do not spend from a regular wallet"
                % (len(env), a), a, outpoints=["%s:%d" % (u["txid"], u["vout"]) for u in env])
        unv = [u for u in mine if "PROTECTED:UNVERIFIED" in u["protect"]]
        if unv:
            add("LOW", "INSCRIPTION_CHECK_INCOMPLETE", "%d small UTXO(s) on %s could not be checked for inscriptions (lookup failed or --max-lookups reached): excluded from consolidation"
                % (len(unv), a), a, outpoints=["%s:%d" % (u["txid"], u["vout"]) for u in unv])
        unc = [u for u in mine if not u["confirmed"]]
        if unc:
            add("INFO", "UNCONFIRMED_UTXOS", "%d unconfirmed UTXO(s) on %s" % (len(unc), a), a, count=len(unc))
        dust = [u for u in mine if u["value"] <= DUSTING_MAX and "PROTECTED:ENVELOPE" not in u["protect"]]
        if dust and total_sats > DUSTING_WALLET_MIN:
            hard = any(u["value"] <= HARD_DUST for u in dust)
            add("MEDIUM" if hard else "LOW", "DUSTING_ATTACK_SUSPECT",
                "%d tiny unsolicited UTXO(s) (<= %d sats) sit beside a %d-sat wallet on %s: freeze / do-not-spend them in Sparrow, Electrum or Bitcoin Core so they cannot link your main UTXOs"
                % (len(dust), DUSTING_MAX, total_sats, a), a, count=len(dust),
                outpoints=["%s:%d" % (u["txid"], u["vout"]) for u in dust], values=[u["value"] for u in dust])
        p = txa["per_address"].get(a)
        if p:
            sev = _sev_count(len(p["co_addrs"]), 1, 3, 10)
            if sev:
                add(sev, "CIOH_COSPEND_EXPOSURE", "%s was co-spent with %d other address(es) in %d recent multi-input tx(s): common-input-ownership clustering links them to one owner"
                    % (a, len(p["co_addrs"]), len(set(p["cospend_txids"]))), a, co_addresses=sorted(p["co_addrs"]),
                    txids=sorted(set(p["cospend_txids"])))
            for code, key, what in (("ROUND_NUMBER_CHANGE_LEAK", "round_txids", "a round-number payment next to a non-round output, which identifies the change"),
                                    ("SCRIPT_TYPE_MISMATCH_CHANGE", "mismatch_txids", "outputs of different script types, where the one matching the input type is identifiable as change")):
                ids = sorted(set(p[key]))
                sev = _sev_count(len(ids), 1, 3)
                if sev:
                    add(sev, code, "%s: %d recent spend(s) show %s" % (a, len(ids), what), a, txids=ids)
    for txid, group in txa["cross"].items():
        add("MEDIUM", "CIOH_CROSS_ADDRESS_LINK", "audited addresses %s were co-spent in tx %s: this permanently links them as one wallet on-chain"
            % (", ".join(group), txid), None, ":" + txid, addresses=group, txid=txid)
    if report["consolidation"]["window_open"]:
        c = report["consolidation"]
        add("INFO", "CONSOLIDATION_WINDOW_OPEN", "fees are low (%.1f sat/vB <= %.1f): consolidating %d UTXO(s) costs %d sats and breaks even above %s sat/vB"
            % (c["rate"], c["window_rate"], c["eligible"], c["fee_sats"], c["breakeven_rate"]), None)
    return findings


# ---------------------------------------------------------------- delta
def make_state(report, findings, sk_addrs):
    return {"addresses": sk_addrs, "utxo_count": report["totals"]["utxos"], "total_sats": report["totals"]["sats"],
            "outpoints": ["%s:%d" % (u["txid"], u["vout"]) for u in report["utxos"]],
            "dust": {"%s:%d" % (u["txid"], u["vout"]): u["value"] for u in report["utxos"]
                     if u["value"] <= DUSTING_MAX and "PROTECTED:ENVELOPE" not in u["protect"]},
            "window_open": report["consolidation"]["window_open"], "findings": [f.to_dict() for f in findings]}


def compute_events(prev, cur, sk):
    ev = []
    new_dust = {k: v for k, v in cur["dust"].items() if k not in (prev.get("dust") or {})}
    if new_dust:
        ev.append(bc.Finding("MEDIUM" if any(v <= HARD_DUST for v in new_dust.values()) else "LOW", "NEW_DUST",
                             "%d new tiny UTXO(s) (<= %d sats): %s" % (len(new_dust), DUSTING_MAX, ", ".join(sorted(new_dust))),
                             {"outpoints": sorted(new_dust), "values": [new_dust[k] for k in sorted(new_dust)]},
                             key="%s:NEW_DUST:%s" % (sk, hashlib.sha1(",".join(sorted(new_dust)).encode()).hexdigest()[:8])))
    if cur["utxo_count"] != prev.get("utxo_count"):
        ev.append(bc.Finding("INFO", "UTXO_COUNT_CHANGED", "UTXO count changed %s -> %d (balance %s -> %d sats)"
                             % (prev.get("utxo_count"), cur["utxo_count"], prev.get("total_sats"), cur["total_sats"]),
                             {"old": prev.get("utxo_count"), "new": cur["utxo_count"]},
                             key="%s:UTXO_COUNT_CHANGED:%s" % (sk, cur["utxo_count"])))
    if cur["window_open"] and not prev.get("window_open"):
        ev.append(bc.Finding("INFO", "CONSOLIDATION_WINDOW_OPEN", "fee window opened: consolidation is now economical",
                             {}, key="%s:CONSOLIDATION_WINDOW_OPEN:event" % sk))
    return ev


# ---------------------------------------------------------------- rendering
_COLORS = {"CRITICAL": "\033[1;31m", "HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[36m", "INFO": "\033[2m"}


def _n(x):
    return "{:,}".format(int(x))


def _usd(v):
    return "n/a" if v is None else "${:,.2f}".format(v)


def _rate(r):
    return ("%g" % r)


def fmt_finding(f, color=False):
    sev = "%-8s" % f.sev
    if color:
        sev = _COLORS[f.sev] + sev + "\033[0m"
    return "  [%s] %s: %s" % (sev, f.code, f.msg)


def _op_str(o):
    return "%s:%d" % (o["txid"], o["vout"])


def _lock_cmd(ops):
    return "bitcoin-cli lockunspent false '%s' true" % json.dumps([_op(o) for o in ops], separators=(",", ":"))


def _sendall_cmd(ops, rate, out_type):
    dest = "<YOUR_NEW_%s_ADDRESS>" % ("bc1p" if out_type == "P2TR" else "bc1q")
    opts = json.dumps({"inputs": [_op(o) for o in ops], "add_to_wallet": False, "psbt": True}, separators=(",", ":"))
    return "bitcoin-cli -named sendall recipients='[\"%s\"]' fee_rate=%s options='%s'" % (dest, _rate(rate), opts)


def _fee_line(r):
    f = r["fees"]["recommended"]
    if not f:
        return "fees      unavailable (degraded)"
    s = "fees      " + " ".join("%s=%s" % (k, _rate(f[k])) for k in FEE_NAMES) + " sat/vB (%s)" % r["fees"]["source"]
    if r["fees"]["blockstream_504_floor"] is not None:
        s += " | blockstream 504-block floor=%s" % _rate(r["fees"]["blockstream_504_floor"])
    return s


def render_text(r, findings, delta, code, degraded, header, color=False):
    t, c = r["totals"], r["consolidation"]
    lines = [header, ""]
    lines.append("wallet    %d address(es)  utxos=%d (confirmed %d / unconfirmed %d)  total=%s sats (%.8f BTC, %s)  hygiene_score=%d/100"
                 % (len(r["addresses"]), t["utxos"], t["confirmed"], t["unconfirmed"], _n(t["sats"]), t["btc"], _usd(t["usd"]), r["score"]))
    for a in r["addresses"]:
        s = a["stats"]
        lines.append("address   %s %-11s utxos=%d balance=%s funded_txo=%d spent_txo=%d tx_count=%d score=%d"
                     % (a["address"], a["type"], a["utxo_count"], _n(a["balance_sats"]), s["funded_txo_count"], s["spent_txo_count"], s["tx_count"], a["score"]))
    lines.append(_fee_line(r))
    for b in r["buckets"]:
        lines.append("  bucket %-42s count=%5d sum=%14s" % (b["label"], b["count"], _n(b["sats"])))
    lines.append("stranded  (strict: value <= input_vB*rate; conservative: x%g margin)" % r["min_value_multiple"])
    for s in r["stranded"]:
        lines.append("  %-12s %6s sat/vB  strict=%4d (%s sats)  conservative=%4d (%s sats)"
                     % (s["name"], _rate(s["rate"]), s["strict_count"], _n(s["strict_sats"]), s["conservative_count"], _n(s["conservative_sats"])))
    sc = r["inscription_scan"]
    lines.append("scan      creating-tx witness check on %d txid(s) (UTXOs <= %s sats, cap %d): envelope_hits=%d lookup_failures=%d unchecked=%d"
                 % (sc["checked_txids"], _n(SMALL_LOOKUP_MAX), sc["cap"], sc["envelope_hits"], sc["lookup_failures"], sc["unchecked_capped"]))
    lines.append("plan      consolidate %d UTXO(s) -> %s in %d tx(s) at %s sat/vB (%s): %.1f vB, fee %s sats (%s), out %s sats; protected/left untouched=%d; break-even future rate=%s sat/vB%s"
                 % (c["eligible"], c["out_type"], c["tx_count"], _rate(c["rate"]), c["rate_source"], c["vsize"], _n(c["fee_sats"]),
                    _usd(c["fee_usd"]), _n(c["output_sats"]), c["protected"], c["breakeven_rate"], "  [WINDOW OPEN]" if c["window_open"] else ""))
    for m in c["matrix"]:
        fu = m["future"]
        lines.append("  matrix  %-6s @ %-10s %6s sat/vB  n=%4d vB=%10.1f fee=%9s sats (%s)  net@50=%s net@100=%s%s"
                     % (m["out_type"], m["scenario"], _rate(m["rate"]), m["eligible"], m["vsize"], _n(m["fee_sats"]), _usd(m["fee_usd"]),
                        _n(fu["50"]["net_savings_sats"]) if fu else "-", _n(fu["100"]["net_savings_sats"]) if fu else "-",
                        "" if m["viable"] else "  (not viable)"))
    p = r["privacy"]
    for a, v in p["per_address"].items():
        lines.append("privacy   %s spend_txs=%d co_addresses=%d cospend_txs=%d round_change_txs=%d script_mismatch_txs=%d"
                     % (a, v["spend_txs"], len(v["co_addresses"]), len(v["cospend_txids"]), len(v["round_txids"]), len(v["mismatch_txids"])))
    cc = r["coin_control"]
    lines.append("coinctl   freeze=%d consolidate=%d leave=%d (use --format markdown for copy-paste commands)"
                 % (len(cc["freeze"]), len(cc["consolidate"]), cc["leave_count"]))
    if degraded:
        lines += ["", "DEGRADED  data sources failed: %s (result may be incomplete)" % ", ".join(degraded)]
    lines += ["", "findings"]
    lines += [fmt_finding(f, color) for f in bc.sort_findings(findings)] or ["  (no findings)"]
    lines += _delta_lines(delta)
    lines += ["", "exit_code %d" % code, SCOPE_NOTE]
    return "\n".join(lines)


def _delta_lines(delta):
    if delta is None:
        return []
    lines = ["", "delta"]
    if delta["baseline"]:
        lines.append("  baseline run: no prior state; recorded %d finding(s)" % len(delta["new"]))
    for label, items in (("EVENT", delta["events"]), ("NEW", delta["new"]), ("CHANGED", delta["changed"]), ("RESOLVED", delta["resolved"])):
        for f in items:
            lines.append("  %-8s [%s] %s: %s" % (label, f.sev, f.code, f.msg))
    if not (delta["events"] or delta["new"] or delta["changed"] or delta["resolved"]):
        lines.append("  (no changes)")
    return lines


def render_markdown(r, findings, delta, code, degraded, header, max_list=50):
    t, c = r["totals"], r["consolidation"]
    L = ["# Bitcoin UTXO Hygiene Report", "", "```", header, "```", "",
         "**Hygiene score: %d/100** | UTXOs: %d (%d confirmed, %d unconfirmed) | Total: %s sats (%.8f BTC, %s) | Exit code: %d"
         % (r["score"], t["utxos"], t["confirmed"], t["unconfirmed"], _n(t["sats"]), t["btc"], _usd(t["usd"]), code), ""]
    if degraded:
        L += ["> **DEGRADED** data sources: %s. Result may be incomplete." % ", ".join(degraded), ""]
    L += ["## Addresses", "", "| Address | Type | UTXOs | Balance (sats) | Funded TXO | Spent TXO | Txs | Score |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for a in r["addresses"]:
        s = a["stats"]
        L.append("| `%s` | %s | %d | %s | %d | %d | %d | %d |" % (a["address"], a["type"], a["utxo_count"], _n(a["balance_sats"]),
                                                                   s["funded_txo_count"], s["spent_txo_count"], s["tx_count"], a["score"]))
    L += ["", "## Fees", "", "`" + _fee_line(r).strip() + "`", ""]
    if r["mempool_blocks"]:
        L.append("Next mempool blocks (median / range sat/vB): " + "; ".join(
            "#%d %s / %s" % (i + 1, _rate(b["medianFee"]) if b["medianFee"] is not None else "?",
                             "-".join(_rate(x) for x in (b["feeRange"] or [])[:1] + (b["feeRange"] or [])[-1:]) if b["feeRange"] else "?")
            for i, b in enumerate(r["mempool_blocks"])))
        L.append("")
    L += ["## UTXO value buckets", "", "| Bucket (sats) | Count | Sum (sats) |", "|---|---:|---:|"]
    L += ["| %s | %d | %s |" % (b["label"], b["count"], _n(b["sats"])) for b in r["buckets"]]
    L += ["", "## Uneconomical / stranded UTXOs", "", "Strict: value <= input vB x rate. Conservative: also x%g margin." % r["min_value_multiple"], "",
          "| Rate | sat/vB | Strict # | Strict sats | Conservative # | Conservative sats |", "|---|---:|---:|---:|---:|---:|"]
    L += ["| %s | %s | %d | %s | %d | %s |" % (s["name"], _rate(s["rate"]), s["strict_count"], _n(s["strict_sats"]), s["conservative_count"], _n(s["conservative_sats"]))
          for s in r["stranded"]]
    sc = r["inscription_scan"]
    L += ["", "## Inscription / dust protection", "",
          "Creating-tx witness check on %d txid(s) (UTXOs <= %s sats, cap %d): **%d** envelope hit(s), %d lookup failure(s), %d unchecked."
          % (sc["checked_txids"], _n(SMALL_LOOKUP_MAX), sc["cap"], sc["envelope_hits"], sc["lookup_failures"], sc["unchecked_capped"]),
          "", "## Consolidation plan", "",
          "Consolidate **%d** UTXO(s) into one %s output per tx (%d tx) at **%s sat/vB** (%s): %.1f vB, fee **%s sats (%s)**, output %s sats. "
          "Break-even future fee rate: %s sat/vB.%s" % (c["eligible"], c["out_type"], c["tx_count"], _rate(c["rate"]), c["rate_source"], c["vsize"],
                                                       _n(c["fee_sats"]), _usd(c["fee_usd"]), _n(c["output_sats"]), c["breakeven_rate"],
                                                       " **Fee window is OPEN.**" if c["window_open"] else ""),
          "", "| Output | Now at | sat/vB | Inputs | vB | Fee (sats) | Fee USD | Net saving vs 50 sat/vB | Net saving vs 100 sat/vB | Break-even |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in c["matrix"]:
        fu = m["future"]
        L.append("| %s | %s | %s | %d | %.1f | %s | %s | %s | %s | %s |"
                 % (m["out_type"], m["scenario"], _rate(m["rate"]), m["eligible"], m["vsize"], _n(m["fee_sats"]), _usd(m["fee_usd"]),
                    _n(fu["50"]["net_savings_sats"]) if fu else "-", _n(fu["100"]["net_savings_sats"]) if fu else "-",
                    m["breakeven_rate"] if m["breakeven_rate"] is not None else "-"))
    p = r["privacy"]
    L += ["", "## Privacy (recent %d tx analysed)" % p["txs_analyzed"], "",
          "| Address | Spend txs | Co-spent addresses | CIOH txs | Round-change txs | Script-mismatch txs |", "|---|---:|---:|---:|---:|---:|"]
    L += ["| `%s` | %d | %d | %d | %d | %d |" % (a, v["spend_txs"], len(v["co_addresses"]), len(v["cospend_txids"]), len(v["round_txids"]), len(v["mismatch_txids"]))
          for a, v in p["per_address"].items()]
    L += ["", "## Findings", "", "| Severity | Code | Detail |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % (f.sev, f.code, f.msg.replace("|", "\\|")) for f in bc.sort_findings(findings)] or ["| - | - | no findings |"]
    cc = r["coin_control"]
    L += ["", "## Coin control (run these yourself; this tool never signs or broadcasts)", ""]
    fr = cc["freeze"]
    L += ["### Freeze / do-not-spend (%d outpoint(s))" % len(fr), ""]
    if fr:
        L += ["| Outpoint | Sats | Reasons |", "|---|---:|---|"]
        L += ["| `%s:%d` | %s | %s |" % (o["txid"], o["vout"], _n(o["value"]), ", ".join(o["reasons"])) for o in fr[:max_list]]
        if len(fr) > max_list:
            L.append("| ... %d more (see --format json) | | |" % (len(fr) - max_list))
        L += ["", "```", "# Bitcoin Core (persistent lock)" + (" - first %d of %d" % (max_list, len(fr)) if len(fr) > max_list else ""),
              _lock_cmd(fr[:max_list]), "# Sparrow: UTXOs tab -> select outpoints -> right-click -> Freeze UTXO",
              "# Electrum: Coins tab -> select outpoints -> right-click -> Freeze Coin", "```"]
    else:
        L.append("None.")
    co = cc["consolidate"]
    L += ["", "### Consolidate (%d outpoint(s), %d tx)" % (len(co), c["tx_count"]), ""]
    if c["viable"] and c["batches"]:
        b0 = c["batches"][0]
        L += ["```", "# Bitcoin Core: unsigned PSBT for batch 1 of %d (%d inputs)%s" % (len(c["batches"]), len(b0), " - first %d shown" % max_list if len(b0) > max_list else ""),
              _sendall_cmd(b0[:max_list], c["rate"], c["out_type"]), "# Sparrow / Electrum: select exactly these outpoints in Coins/UTXOs, Send -> one new address, fee %s sat/vB" % _rate(c["rate"]), "```", ""]
        L += ["Outpoints: " + ", ".join("`%s`" % _op_str(o) for o in co[:max_list]) + (" ... +%d more" % (len(co) - max_list) if len(co) > max_list else "")]
    else:
        L.append("No economical consolidation at %s sat/vB (need >= 2 eligible UTXOs with a positive net saving)." % _rate(c["rate"]))
    L += ["", "Left untouched (uneconomical now, not protected): %d UTXO(s)." % cc["leave_count"]]
    L += [l for l in _delta_lines(delta)]
    L += ["", "---", "", SCOPE_NOTE, ""]
    return "\n".join(L)


def report_json(r):
    return json.loads(json.dumps(r, sort_keys=True))


# ---------------------------------------------------------------- CLI
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("bad arguments")


def build_parser():
    p = _Parser(prog="btc_utxo_hygiene.py", description="Read-only Bitcoin UTXO privacy & fee hygiene auditor")
    p.add_argument("addresses", nargs="+", metavar="ADDRESS")
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--json", action="store_true")
    p.add_argument("--offline", metavar="FILE")
    p.add_argument("--state", metavar="PATH")
    p.add_argument("--delta", action="store_true")
    p.add_argument("--target-fee", "--target-feerate", dest="target_fee", type=float, metavar="SAT_VB")
    p.add_argument("--protect", action="append", default=[], metavar="TXID:VOUT[,TXID:VOUT...]")
    p.add_argument("--max-lookups", type=int, default=60, metavar="N")
    p.add_argument("--max-txs", type=int, default=50, metavar="N")
    p.add_argument("--max-list", type=int, default=50, metavar="N")
    p.add_argument("--min-value-multiple", type=float, default=3.0, metavar="X")
    p.add_argument("--window-rate", type=float, default=3.0, metavar="SAT_VB")
    p.add_argument("--consolidate-to", choices=["p2wpkh", "p2tr"], default="p2wpkh")
    p.add_argument("--fail-on", choices=["medium", "high", "critical"], default="medium")
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument("--no-color", action="store_true")
    return p


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
        if min(args.max_lookups, args.max_txs, args.max_list) < 0:
            raise UsageError("--max-lookups/--max-txs/--max-list must be >= 0")
        if args.min_value_multiple < 1:
            raise UsageError("--min-value-multiple must be >= 1")
        if args.target_fee is not None and args.target_fee <= 0:
            raise UsageError("--target-fee must be positive")
        infos, seen = [], set()
        for tok in split_tokens(args.addresses):
            try:
                info = parse_address(tok)
            except AddressError as e:
                raise UsageError("invalid Bitcoin address %s...: %s" % (tok[:6], e)) from None
            if info["address"] not in seen:
                seen.add(info["address"])
                infos.append(info)
        if not infos:
            raise UsageError("no addresses given")
        if len(infos) > MAX_ADDRESSES:
            raise UsageError("at most %d addresses per run" % MAX_ADDRESSES)
        protect = []
        for tok in split_tokens(args.protect):
            if not re.fullmatch(r"[0-9a-fA-F]{64}:\d+", tok):
                raise UsageError("--protect expects TXID:VOUT")
            protect.append(tok.lower())
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

    fmt = "json" if args.json else args.format
    now = now or bc.utc_now()
    src = Source(timeout=args.timeout, offline=fx)
    opts = {"mult": args.min_value_multiple, "protect": protect, "max_lookups": args.max_lookups, "max_txs": args.max_txs,
            "target_fee": args.target_fee, "consolidate_to": "P2TR" if args.consolidate_to == "p2tr" else "P2WPKH",
            "window_rate": args.window_rate}
    report, findings = audit_wallet(src, infos, opts)

    addrs = sorted(i["address"] for i in infos)
    sk = "btc:" + hashlib.sha1(",".join(addrs).encode()).hexdigest()[:12]
    store = bc.StateStore(args.state) if args.state else None
    incomplete = any(not a["utxo_complete"] for a in report["addresses"])
    state = make_state(report, findings, addrs)
    events, delta = [], None
    prev = store.get(sk) if store else None
    if args.delta:
        if prev is None:
            delta = {"baseline": True, "events": [], "new": list(findings), "changed": [], "resolved": []}
        else:
            if not incomplete:
                events = compute_events(prev, state, sk)
            dd = bc.diff_findings(prev.get("findings", []), findings)
            delta = {"baseline": False, "events": events, "new": [f for f in dd["NEW"] if f.code != "CONSOLIDATION_WINDOW_OPEN"],
                     "changed": dd["CHANGED"], "resolved": dd["RESOLVED"]}
    if store and not incomplete:
        store.put(sk, state)

    degraded = sorted(src.degraded)
    code = bc.exit_code(findings + events, bool(degraded), args.fail_on)
    header = bc.snapshot_header(TOOL, src.endpoints if fx is None else ["offline:" + os.path.basename(args.offline)], src.fallbacks, now=now)
    if fmt == "json":
        payload = {"tool": TOOL, "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "scope_note": SCOPE_NOTE,
                   "degraded_sources": degraded, "report": report_json(report),
                   "findings": [f.to_dict() for f in bc.sort_findings(findings + events)],
                   "delta": None if delta is None else {k: (v if k == "baseline" else [f.to_dict() for f in v]) for k, v in delta.items()},
                   "exit_code": code}
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), file=out)
    elif fmt == "markdown":
        print(render_markdown(report, findings, delta, code, degraded, header, args.max_list), file=out)
    else:
        color = not args.no_color and not os.environ.get("NO_COLOR") and getattr(out, "isatty", lambda: False)()
        print(render_text(report, findings, delta, code, degraded, header, color), file=out)
    return code


def main():
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
