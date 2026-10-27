#!/usr/bin/env python3
"""EVM & L2 Token Approval & Spender Exposure Auditor (read-only, stdlib + bot_common).

Reads the *current* ERC-20 allowance and Permit2 sub-allowance state of one or more owner
wallets on Ethereum, Base and Arbitrum One over curated + discovered tokens and spenders,
classifies each active spender (EOA / unknown / unverified / curated / proxy), and prints exact
revoke / Permit2-lockdown call-data for the owner to submit themselves.  Optional delta mode
alerts on new, increased, unlimited and revoked approvals.  Exit codes: 0 clean, 1 MEDIUM,
2 HIGH, 3 CRITICAL, 10 bad input, 11 degraded data sources.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bot_common as bc  # noqa: E402

TOOL = "evm-approval-auditor"
SCOPE_NOTE = ("SCOPE_NOTE: Read-only: only eth_blockNumber, eth_call, eth_getCode, eth_getStorageAt and eth_getLogs, "
              "plus public Sourcify/Blockscout lookups. Never asks for private keys or seed phrases; no signing, no "
              "transaction is built for or broadcast by the tool; revoke (approve(spender, 0)) and Permit2 lockdown "
              "call-data is displayed for the owner to submit themselves. Reports current allowance state for the "
              "tokens and spenders it checked and states its coverage window; \"no findings\" never means \"no "
              "approvals exist\" (NFT setApprovalForAll and unlisted tokens/spenders are outside v1 unless supplied). "
              "Spender labels come from a curated list and Sourcify/Blockscout; an unlabeled spender is unknown, not "
              "malicious. No financial, legal or tax advice. Refuses: scanning to target third-party wallets for "
              "exploitation, ranking wallets by balance, or building phishing/drainer lists.")

CHAINS = {
    "eth": {"id": 1, "rpcs": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"]},
    "base": {"id": 8453, "rpcs": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"]},
    "arb": {"id": 42161, "rpcs": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"]},
}

# address -> (symbol, decimals)
CORE_TOKENS = {
    "eth": {
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
        "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
        "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18),
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", 18),
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("WBTC", 8),
        "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": ("stETH", 18),
    },
    "base": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ("USDC", 6),
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": ("USDbC", 6),
        "0x4200000000000000000000000000000000000006": ("WETH", 18),
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": ("cbETH", 18),
        "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": ("DAI", 18),
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": ("cbBTC", 8),
    },
    "arb": {
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": ("USDC", 6),
        "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": ("USDC.e", 6),
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": ("USDT", 6),
        "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": ("DAI", 18),
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": ("WETH", 18),
        "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f": ("WBTC", 8),
        "0x912ce59144191c1204e64559fe8253a0e49e6548": ("ARB", 18),
    },
}

PERMIT2_ADDR = "0x000000000022d473030f116ddee9f6b43ac78ba3"
KNOWN_SPENDERS = {
    PERMIT2_ADDR: "Uniswap Permit2 (canonical)",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router02",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap SwapRouter02",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch v5 Router",
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch v6 Router",
    "0xc92e8bdf79f0507f65a392b0ab4667716bfe0110": "CoW Protocol GPv2VaultRelayer",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x ExchangeProxy",
    "0x6a000f20005980200259b80c5102003040001068": "ParaSwap AugustusV6",
    "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho Blue",
}
AAVE_V3_POOL = {
    "eth": "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",
    "base": "0xa238dd80c259a72e81d7e4664a9801593f98d1c5",
    "arb": "0x794a61358d6845594f94dc1db02a252b5b4814ad",
}

SEL_BALANCE_OF = "0x70a08231"
SEL_ALLOWANCE = "0xdd62ed3e"
SEL_SYMBOL = "0x95d89b41"
SEL_DECIMALS = "0x313ce567"
SEL_APPROVE = "0x095ea7b3"
SEL_P2_ALLOWANCE = "0x927da105"
SEL_P2_LOCKDOWN = "0xcc53287f"

SLOT_IMPL_1967 = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
TOPIC_APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"

SOURCIFY_URL = "https://sourcify.dev/server/v2/contract/{cid}/{addr}?fields=abi,proxyResolution,compilation"
BLOCKSCOUT_URL = "https://eth.blockscout.com/api/v2/smart-contracts/{addr}"
BLOCKSCOUT_TOKENS_URL = "https://eth.blockscout.com/api/v2/addresses/{owner}/tokens?type=ERC-20"

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ZERO_ADDR = "0x" + "0" * 40

BATCH = 50
UNLIMITED_ERC20 = 2 ** 255
UNLIMITED_P2 = 2 ** 159
UNLIMITED_ABS = 10 ** 30
LONG_EXPIRY_SECS = 30 * 86400
LOG_CHUNK_START = 10000
LOG_CHUNK_MIN = 500
LOG_CHUNK_CAP = {"eth": 10000, "base": 50000, "arb": 30000}
MAX_LOG_REQUESTS = 60
MAX_BLOCKSCOUT_TOKENS = 30


# ---------------------------------------------------------------- keccak-256 (stdlib has only NIST sha3)
def _keccak_tables():
    rcs, r = [], 1
    for _ in range(24):
        rc = 0
        for j in range(7):
            r = ((r << 1) ^ ((r >> 7) * 0x71)) % 256
            if r & 2:
                rc ^= 1 << ((1 << j) - 1)
        rcs.append(rc)
    rot = [[0] * 5 for _ in range(5)]
    x, y = 1, 0
    for t in range(24):
        rot[x][y] = ((t + 1) * (t + 2) // 2) % 64
        x, y = y, (2 * x + 3 * y) % 5
    return rcs, rot


_RCS, _ROT = _keccak_tables()
_M64 = (1 << 64) - 1


def _rol(v, n):
    n %= 64
    return ((v << n) | (v >> (64 - n))) & _M64 if n else v


def _keccak_f(a):
    for rc in _RCS:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
        a = [[b[x][y] ^ (~b[(x + 1) % 5][y] & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data):
    rate = 136
    msg = bytearray(data)
    msg.append(0x01)
    while len(msg) % rate:
        msg.append(0)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(msg[off + 8 * i: off + 8 * i + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def to_checksum(addr):
    low = addr[2:].lower()
    h = keccak256(low.encode("ascii")).hex()
    return "0x" + "".join(ch.upper() if int(h[i], 16) >= 8 else ch for i, ch in enumerate(low))


def checksum_ok(addr):
    """True when the address is single-case or its mixed case matches EIP-55."""
    body = addr[2:]
    if body == body.lower() or body == body.upper():
        return True
    return addr == to_checksum(addr)


def event_topic(sig):
    return "0x" + keccak256(sig.encode("ascii")).hex()


TOPIC_P2_APPROVAL = event_topic("Approval(address,address,address,uint160,uint48)")
TOPIC_P2_PERMIT = event_topic("Permit(address,address,address,uint160,uint48,uint48)")


# ---------------------------------------------------------------- ABI encoding / decoding
def pad32(addr):
    """Left-pad an address to a 32-byte word (64 hex chars, no 0x)."""
    return addr[2:].lower().rjust(64, "0")


def pad32_uint(n):
    return format(int(n), "064x")


def topic_addr(addr):
    return "0x" + pad32(addr)


def encode_erc20_approve(spender, amount_raw=0):
    return SEL_APPROVE + pad32(spender) + pad32_uint(amount_raw)


def encode_permit2_lockdown(pairs):
    """Permit2.lockdown(TokenSpenderPair[]): dynamic array of (address token, address spender) tuples."""
    return SEL_P2_LOCKDOWN + pad32_uint(32) + pad32_uint(len(pairs)) + "".join(pad32(tok) + pad32(sp) for tok, sp in pairs)


def encode_balance_of(owner):
    return SEL_BALANCE_OF + pad32(owner)


def encode_allowance(owner, spender):
    return SEL_ALLOWANCE + pad32(owner) + pad32(spender)


def encode_p2_allowance(owner, token, spender):
    return SEL_P2_ALLOWANCE + pad32(owner) + pad32(token) + pad32(spender)


def decode_uint(h):
    if not isinstance(h, str) or len(h) < 66:
        return None
    try:
        return int(h[2:66], 16)
    except ValueError:
        return None


def decode_permit2_allowance(h):
    """(uint160 amount, uint48 expiration, uint48 nonce) -> dict, or None when malformed."""
    if not isinstance(h, str) or len(h) < 2 + 192:
        return None
    try:
        return {"amount": int(h[2:66], 16), "expiration": int(h[66:130], 16), "nonce": int(h[130:194], 16)}
    except ValueError:
        return None


_PRINTABLE = re.compile(r"[^\x20-\x7e]")


def _clean_text(raw):
    s = _PRINTABLE.sub("", raw.decode("utf-8", errors="replace")).strip()
    return s[:32] or None


def decode_symbol(h):
    """symbol() as ABI `string` or legacy `bytes32` (e.g. MKR). Control characters are stripped."""
    if not isinstance(h, str) or len(h) < 66:
        return None
    data = h[2:]
    try:
        if len(data) >= 128:
            off = int(data[:64], 16) * 2
            if off + 64 <= len(data):
                ln = int(data[off:off + 64], 16)
                if ln <= 256 and len(data) >= off + 64 + 2 * ln:
                    return _clean_text(bytes.fromhex(data[off + 64: off + 64 + 2 * ln]))
        return _clean_text(bytes.fromhex(data[:64]).rstrip(b"\x00"))
    except ValueError:
        return None


def decode_decimals(h):
    v = decode_uint(h)
    return v if v is not None and v <= 77 else None


def word_addr(w):
    """Storage word -> address (last 20 bytes) or None when empty."""
    if not isinstance(w, str) or len(w) < 3:
        return None
    try:
        if int(w, 16) == 0:
            return None
    except ValueError:
        return None
    return "0x" + w[2:].rjust(64, "0")[-40:].lower()


def format_units(raw, decimals):
    if raw is None:
        return "?"
    if decimals is None:
        return "%d (raw)" % raw
    if decimals == 0:
        return str(raw)
    whole, frac = divmod(raw, 10 ** decimals)
    frac_s = str(frac).rjust(decimals, "0").rstrip("0")
    return "%d.%s" % (whole, frac_s) if frac_s else str(whole)


def is_unlimited_erc20(raw):
    return raw >= UNLIMITED_ERC20 or raw >= UNLIMITED_ABS


def is_unlimited_p2(amount):
    return amount >= UNLIMITED_P2 or amount >= UNLIMITED_ABS


def known_spenders(chain):
    d = dict(KNOWN_SPENDERS)
    d[AAVE_V3_POOL[chain]] = "Aave V3 Pool"
    return d


def _utc(epoch):
    try:
        return datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return "never (max)"


# ---------------------------------------------------------------- RPC
class RpcError(Exception):
    pass


class Ctx:
    def __init__(self, timeout=20):
        self.timeout = timeout
        self.degraded = set()
        self.endpoints = set()
        self.fallbacks = []
        self.ver_cache = {}


_REVERT_HINTS = ("revert", "execution", "invalid opcode", "out of gas", "stack")


def _soft_error(err):
    if not isinstance(err, dict):
        return False
    if err.get("code") == 3:
        return True
    msg = str(err.get("message", "")).lower()
    return any(h in msg for h in _REVERT_HINTS)


def _extract(res, n, single, soft):
    if res.status != 200:
        return None
    items = [res.data] if single else res.data
    if not isinstance(items, list) or len(items) != n:
        return None
    by_id = {}
    for it in items:
        if not isinstance(it, dict):
            return None
        by_id[it.get("id")] = it
    out = []
    for i in range(n):
        it = by_id.get(i)
        if it is None:
            return None
        if it.get("error"):
            if soft and _soft_error(it["error"]):
                out.append(None)
                continue
            return None
        if it.get("result") is None:
            return None
        out.append(it["result"])
    return out


def rpc_batch(ctx, chain, calls, soft=False):
    """calls: [(method, params)]. HTTP 200 alone is not trusted: JSON-RPC errors/missing results fall through.

    soft=True lets eth_call reverts yield None instead of failing over.
    """
    single = len(calls) == 1
    reqs = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
    urls = CHAINS[chain]["rpcs"]
    for n, url in enumerate(urls):
        res = bc.http_json(url, body=reqs[0] if single else reqs, retries=1, timeout=ctx.timeout)
        out = _extract(res, len(calls), single, soft)
        if out is not None:
            ctx.endpoints.add(url)
            if n:
                fb = "%s: %s failed -> %s" % (chain, urls[0], url)
                if fb not in ctx.fallbacks:
                    ctx.fallbacks.append(fb)
            return out
    raise RpcError("all %s RPCs failed for %s" % (chain, calls[0][0]))


def rpc_call(ctx, chain, method, params, soft=False):
    return rpc_batch(ctx, chain, [(method, params)], soft=soft)[0]


def rpc_chunked(ctx, chain, calls, soft=False):
    """rpc_batch in JSON-RPC batches of <= BATCH requests."""
    out = []
    for i in range(0, len(calls), BATCH):
        out.extend(rpc_batch(ctx, chain, calls[i:i + BATCH], soft=soft))
    return out


def eth_call_many(ctx, chain, pairs):
    """pairs: [(to, data)] -> [result hex or None on revert]."""
    return rpc_chunked(ctx, chain, [("eth_call", [{"to": to, "data": d}, "latest"]) for to, d in pairs], soft=True)


# ---------------------------------------------------------------- bounded log discovery
_RANGE_HINTS = ("range", "spans", "too many", "too large", "more than", "exceed", "max block", "maximum block",
                "block limit", "response size")


def _log_error_kind(err):
    if not isinstance(err, dict):
        return "malformed response"
    msg = str(err.get("message", "")).lower()
    if "rate" in msg or "request limit" in msg:
        return "rate-limited: %s" % err.get("message")
    if err.get("code") in (-32602, -32005) or any(h in msg for h in _RANGE_HINTS):
        return "range"
    return "rpc error %s: %s" % (err.get("code"), err.get("message"))


def get_logs(ctx, chain, flt):
    """Returns (logs, None) or (None, reason). reason == 'range' when any endpoint rejected the span."""
    req = {"jsonrpc": "2.0", "id": 0, "method": "eth_getLogs", "params": [flt]}
    reasons = []
    for url in CHAINS[chain]["rpcs"]:
        res = bc.http_json(url, body=req, retries=1, timeout=ctx.timeout)
        if res.status == 200 and isinstance(res.data, dict):
            if isinstance(res.data.get("result"), list):
                ctx.endpoints.add(url)
                return res.data["result"], None
            reasons.append(_log_error_kind(res.data.get("error")))
        else:
            reasons.append(res.error or "HTTP %d" % res.status)
    return None, ("range" if "range" in reasons else "; ".join(str(r) for r in reasons))


def _topic_to_addr(t):
    if not isinstance(t, str) or len(t) != 66:
        return None
    a = "0x" + t[-40:].lower()
    return a if ADDR_RE.match(a) else None


def discover_logs(ctx, chain, owner, tokens, lookback, latest):
    """Walk backwards from `latest` over at most `lookback` blocks with adaptive chunking.

    Returns (coverage, erc20_hits {(token, spender): last_block}, permit2_hits {(token, spender): last_block}).
    Never raises: rejected ranges shrink the chunk, other failures stop the walk and mark coverage partial.
    """
    cov = {"status": "disabled", "requested_from": None, "from_block": None, "to_block": None,
           "blocks": 0, "chunks": 0, "note": None}
    erc20_hits, p2_hits = {}, {}
    if lookback <= 0:
        cov["note"] = "--lookback-blocks 0"
        return cov, erc20_hits, p2_hits
    if latest is None:
        cov.update(status="skipped", note="eth_blockNumber unavailable")
        return cov, erc20_hits, p2_hits
    lo = max(0, latest - lookback + 1)
    cov.update(requested_from=lo, to_block=latest)
    chunk = max(1, min(LOG_CHUNK_START, LOG_CHUNK_CAP.get(chain, LOG_CHUNK_START), lookback))
    hi, covered_from, requests, note = latest, None, 0, None
    otopic = topic_addr(owner)
    while hi >= lo:
        frm = max(lo, hi - chunk + 1)
        filters = []
        if tokens:
            filters.append(("erc20", {"fromBlock": hex(frm), "toBlock": hex(hi), "address": sorted(tokens),
                                      "topics": [TOPIC_APPROVAL, otopic]}))
        filters.append(("permit2", {"fromBlock": hex(frm), "toBlock": hex(hi), "address": PERMIT2_ADDR,
                                    "topics": [[TOPIC_P2_APPROVAL, TOPIC_P2_PERMIT], otopic]}))
        got, reason = {}, None
        for kind, flt in filters:
            if requests >= MAX_LOG_REQUESTS:
                reason = "request budget (%d) exhausted" % MAX_LOG_REQUESTS
                break
            requests += 1
            logs, reason = get_logs(ctx, chain, flt)
            if logs is None:
                break
            got[kind] = logs
        if len(got) != len(filters):
            if reason == "range" and chunk > LOG_CHUNK_MIN:
                chunk = max(LOG_CHUNK_MIN, chunk // 2)
                continue
            note = "block range rejected even at %d blocks" % chunk if reason == "range" else reason
            break
        for lg in got.get("erc20", []):
            tp = lg.get("topics") or [] if isinstance(lg, dict) else []
            if len(tp) != 3 or str(tp[0]).lower() != TOPIC_APPROVAL:
                continue
            tok, sp = str(lg.get("address", "")).lower(), _topic_to_addr(tp[2])
            if sp and ADDR_RE.match(tok):
                erc20_hits[(tok, sp)] = max(erc20_hits.get((tok, sp), 0), _hexint(lg.get("blockNumber")))
        for lg in got.get("permit2", []):
            tp = lg.get("topics") or [] if isinstance(lg, dict) else []
            if len(tp) != 4:
                continue
            tok, sp = _topic_to_addr(tp[2]), _topic_to_addr(tp[3])
            if tok and sp:
                p2_hits[(tok, sp)] = max(p2_hits.get((tok, sp), 0), _hexint(lg.get("blockNumber")))
        covered_from = frm
        cov["chunks"] += 1
        hi = frm - 1
    cov["from_block"] = covered_from
    cov["blocks"] = 0 if covered_from is None else latest - covered_from + 1
    if covered_from is None:
        cov["status"] = "skipped"
    elif covered_from == lo:
        cov["status"] = "full"
    else:
        cov["status"] = "partial"
    cov["note"] = note
    return cov, erc20_hits, p2_hits


def _hexint(v):
    try:
        return int(v, 16)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- token discovery
def discover_blockscout_tokens(ctx, owner):
    """Best-effort ERC-20 holdings on Ethereum. Failures are coverage notes, never ctx.degraded."""
    res = bc.http_json(BLOCKSCOUT_TOKENS_URL.format(owner=owner.lower()), retries=0, timeout=min(ctx.timeout, 5))
    if res.status != 200 or not isinstance(res.data, dict) or not isinstance(res.data.get("items"), list):
        return {}, "unavailable (%s)" % (res.error or "HTTP %d" % res.status)
    found = {}
    for it in res.data["items"]:
        tok = it.get("token") if isinstance(it, dict) else None
        if not isinstance(tok, dict):
            continue
        addr = str(tok.get("address_hash") or tok.get("address") or "")
        if not ADDR_RE.match(addr) or (tok.get("type") and tok.get("type") != "ERC-20"):
            continue
        try:
            dec = int(tok.get("decimals"))
            dec = dec if 0 <= dec <= 77 else None
        except (TypeError, ValueError):
            dec = None
        sym = tok.get("symbol")
        sym = _clean_text(sym.encode("utf-8")) if isinstance(sym, str) else None
        found[addr.lower()] = (sym, dec)
    keep = sorted(found)[:MAX_BLOCKSCOUT_TOKENS]
    note = "ok (%d token(s)%s)" % (len(keep), ", capped at %d" % MAX_BLOCKSCOUT_TOKENS if len(found) > len(keep) else "")
    return {a: found[a] for a in keep}, note


def fetch_token_meta(ctx, chain, addrs):
    """symbol()/decimals() via eth_call for tokens with unknown metadata. Returns {addr: (symbol, decimals)}."""
    addrs = sorted(addrs)
    if not addrs:
        return {}
    res = eth_call_many(ctx, chain, [(a, s) for a in addrs for s in (SEL_SYMBOL, SEL_DECIMALS)])
    return {a: (decode_symbol(res[2 * i]), decode_decimals(res[2 * i + 1])) for i, a in enumerate(addrs)}


# ---------------------------------------------------------------- verification / spender classification
def lookup_verification(ctx, chain, addr):
    """Sourcify v2 first (404 = unverified, not degraded); Blockscout fallback on Ethereum."""
    a = addr.lower()
    ck = (chain, a)
    if ck in ctx.ver_cache:
        return ctx.ver_cache[ck]
    info = {"verified": None, "source": None, "match": None, "name": None}
    res = bc.http_json(SOURCIFY_URL.format(cid=CHAINS[chain]["id"], addr=a), retries=1, timeout=ctx.timeout)
    if res.status == 200 and isinstance(res.data, dict):
        d = res.data
        info.update(verified=bool(d.get("match")), source="sourcify", match=d.get("match"),
                    name=(d.get("compilation") or {}).get("name"))
    elif res.status == 404:
        info.update(verified=False, source="sourcify")
    else:
        ctx.degraded.add("sourcify")
    if info["verified"] is not True and chain == "eth":
        bs = bc.http_json(BLOCKSCOUT_URL.format(addr=a), retries=1, timeout=ctx.timeout)
        if bs.status == 200 and isinstance(bs.data, dict):
            d = bs.data
            if d.get("is_verified") or d.get("is_fully_verified") or d.get("is_partially_verified") or d.get("source_code"):
                info.update(verified=True, source="blockscout", match="blockscout", name=d.get("name") or info["name"])
            else:
                info["verified"] = False
                info["source"] = info["source"] or "blockscout"
        elif bs.status == 404:
            if info["verified"] is None:
                info.update(verified=False, source="blockscout")
        else:
            ctx.degraded.add("blockscout")
    ctx.ver_cache[ck] = info
    return info


def classify_spenders(ctx, chain, spenders):
    """eth_getCode + EIP-1967 implementation slot + verification for each active spender."""
    spenders = sorted(spenders)
    if not spenders:
        return {}
    calls = [("eth_getCode", [s, "latest"]) for s in spenders] + \
            [("eth_getStorageAt", [s, SLOT_IMPL_1967, "latest"]) for s in spenders]
    res = rpc_chunked(ctx, chain, calls)
    known = known_spenders(chain)
    out = {}
    for i, s in enumerate(spenders):
        code = (res[i] or "0x").lower()
        nbytes = max(0, (len(code) - 2) // 2)
        delegated = nbytes == 23 and code.startswith("0xef0100")    # EIP-7702 delegated EOA
        info = {"address": s, "label": known.get(s), "known": s in known, "code_bytes": nbytes,
                "eoa": nbytes == 0 or delegated, "eip7702_delegate": ("0x" + code[8:48]) if delegated else None,
                "implementation": None, "verification": None, "impl_verification": None}
        if nbytes and not delegated:
            info["implementation"] = word_addr(res[len(spenders) + i])
            info["verification"] = lookup_verification(ctx, chain, s)
            if info["implementation"]:
                info["impl_verification"] = lookup_verification(ctx, chain, info["implementation"])
        out[s] = info
    return out


# ---------------------------------------------------------------- per-owner audit
def _spender_desc(info):
    if info["label"]:
        return "%s [%s]" % (info["address"], info["label"])
    return "%s [unlabeled]" % info["address"]


def erc20_finding(sp, unlimited, var_raw):
    """(severity, code, action) for an active ERC-20 allowance."""
    if sp["eoa"]:
        return "CRITICAL", "EOA_SPENDER", "REVOKE"
    if not sp["known"]:
        v = (sp["verification"] or {}).get("verified")
        if v is False:
            return ("CRITICAL" if unlimited or var_raw > 0 else "HIGH"), "UNVERIFIED_SPENDER", "REVOKE"
        if v is True:
            return ("HIGH", "UNKNOWN_VERIFIED_SPENDER", "REVOKE") if unlimited else ("MEDIUM", "UNKNOWN_VERIFIED_SPENDER", "REVIEW")
        return ("HIGH", "UNCLASSIFIED_SPENDER", "REVOKE") if unlimited else ("MEDIUM", "UNCLASSIFIED_SPENDER", "REVIEW")
    if unlimited:
        return "MEDIUM", "UNLIMITED_KNOWN_SPENDER", "REDUCE"
    return "LOW", "BOUNDED_KNOWN_SPENDER", "KEEP"


def permit2_finding(sp, unlimited, expiration, now_epoch):
    if expiration <= now_epoch:
        return "LOW", "PERMIT2_EXPIRED_SUBALLOWANCE", "REVOKE"
    v = (sp["verification"] or {}).get("verified")
    if sp["eoa"] or (not sp["known"] and v is False):
        return "CRITICAL", "PERMIT2_ACTIVE_SUBALLOWANCE", "REVOKE"
    if not sp["known"]:
        return "HIGH", "PERMIT2_ACTIVE_SUBALLOWANCE", "REVOKE"
    if unlimited or expiration - now_epoch > LONG_EXPIRY_SECS:
        return "MEDIUM", "PERMIT2_ACTIVE_SUBALLOWANCE", "REDUCE"
    return "LOW", "PERMIT2_ACTIVE_SUBALLOWANCE", "KEEP"


def audit_owner(ctx, chain, owner, opts, now_epoch, label=None, prev=None):
    """Returns (report_dict, findings). Raises RpcError when on-chain state cannot be read."""
    o = owner.lower()
    findings = []

    def add(sev, code, msg, suffix, **ev):
        findings.append(bc.Finding(sev, code, msg, ev, key="%s:%s:%s:%s" % (chain, o, suffix, code)))

    prev = prev or {}
    known = known_spenders(chain)

    # --- token set
    tokens, tsrc = {}, {}

    def add_token(a, meta, src):
        a = a.lower()
        if a not in tokens or tokens[a] == (None, None):
            tokens[a] = meta
        tsrc.setdefault(a, set()).add(src)

    for a, meta in CORE_TOKENS[chain].items():
        add_token(a, meta, "curated")
    bs_note = None
    if chain == "eth":
        bs_tokens, bs_note = discover_blockscout_tokens(ctx, o)
        for a, meta in bs_tokens.items():
            add_token(a, meta, "blockscout")
    for a in opts.get("tokens", []):
        add_token(a, (None, None), "user")
    prev_pairs = [k.split(":") for k in list(prev.get("allowances", {})) + list(prev.get("permit2", {}))]
    for tok, _ in prev_pairs:
        add_token(tok, (None, None), "state")

    # --- spender set
    spenders, ssrc = set(), {}

    def add_spender(a, src):
        a = a.lower()
        spenders.add(a)
        ssrc.setdefault(a, set()).add(src)

    for a in known:
        add_spender(a, "curated")
    for a in opts.get("spenders", []):
        add_spender(a, "user")
    for _, sp in prev_pairs:
        add_spender(sp, "state")

    # --- bounded log discovery (bonus; never fails the audit)
    lookback = opts.get("lookback", 20000)
    latest = None
    if lookback > 0:
        try:
            latest = _hexint(rpc_call(ctx, chain, "eth_blockNumber", [])) or None
        except RpcError:
            latest = None
    log_cov, erc20_hits, p2_hits = discover_logs(ctx, chain, o, list(tokens), lookback, latest)
    for (tok, sp) in erc20_hits:
        add_spender(sp, "logs")
    for (tok, sp) in p2_hits:
        add_token(tok, (None, None), "logs")
        add_spender(sp, "logs")
    p2_forced = set(p2_hits) | {tuple(k.split(":")) for k in prev.get("permit2", {})}

    # --- token metadata for unknown symbol/decimals
    missing = [a for a, (s, d) in tokens.items() if s is None or d is None]
    for a, (s, d) in fetch_token_meta(ctx, chain, missing).items():
        os_, od = tokens[a]
        tokens[a] = (os_ or s, od if od is not None else d)

    tok_list, sp_list = sorted(tokens), sorted(spenders)

    # --- balances + ERC-20 allowances
    calls = [(t, encode_balance_of(o)) for t in tok_list] + [(t, encode_allowance(o, s)) for t in tok_list for s in sp_list]
    res = eth_call_many(ctx, chain, calls)
    bal = {t: decode_uint(res[i]) or 0 for i, t in enumerate(tok_list)}
    allow = {}
    idx = len(tok_list)
    for t in tok_list:
        for s in sp_list:
            allow[(t, s)] = decode_uint(res[idx]) or 0
            idx += 1

    # --- Permit2 sub-allowances
    user_sp = sorted({a.lower() for a in opts.get("spenders", [])} - {PERMIT2_ADDR})
    p2_tokens = [t for t in tok_list if allow.get((t, PERMIT2_ADDR), 0) > 0]
    p2_pairs = {(t, s) for t in p2_tokens for s in sp_list if s != PERMIT2_ADDR}
    p2_pairs |= {(t, s) for t in tok_list for s in user_sp}
    p2_pairs |= {p for p in p2_forced if p[0] in tokens and p[1] != PERMIT2_ADDR}
    p2_pairs = sorted(p2_pairs)
    p2 = {}
    if p2_pairs:
        res = eth_call_many(ctx, chain, [(PERMIT2_ADDR, encode_p2_allowance(o, t, s)) for t, s in p2_pairs])
        for pair, r in zip(p2_pairs, res):
            p2[pair] = decode_permit2_allowance(r) or {"amount": 0, "expiration": 0, "nonce": 0}

    # --- classify active spenders
    active = {s for (t, s), v in allow.items() if v > 0} | {s for (t, s), v in p2.items() if v["amount"] > 0}
    sp_info = classify_spenders(ctx, chain, active)

    def tok_meta(t):
        sym, dec = tokens[t]
        return sym or t[:10], dec

    # --- ERC-20 approval records + findings
    approvals = []
    for (t, s), raw in sorted(allow.items()):
        if raw == 0 and not opts.get("include_zero"):
            continue
        sym, dec = tok_meta(t)
        unlimited = is_unlimited_erc20(raw)
        var_raw = min(bal[t], raw)
        rec = {"kind": "erc20", "token": t, "symbol": sym, "decimals": dec, "spender": s, "spender_label": known.get(s),
               "spender_sources": sorted(ssrc.get(s, ())), "allowance_raw": raw,
               "allowance": "UNLIMITED" if unlimited else format_units(raw, dec), "unlimited": unlimited,
               "balance_raw": bal[t], "balance": format_units(bal[t], dec), "value_at_risk_raw": var_raw,
               "value_at_risk": format_units(var_raw, dec), "last_log_block": erc20_hits.get((t, s)),
               "severity": None, "action": None, "finding": None}
        if raw > 0:
            sp = sp_info[s]
            sev, code, action = erc20_finding(sp, unlimited, var_raw)
            tx = {"to": t, "data": encode_erc20_approve(s, 0), "function": "approve(%s, 0)" % s}
            rec.update(severity=sev, action=action, finding=code, revoke_tx=tx)
            why = {"EOA_SPENDER": "spender has no contract code (EOA%s): whoever holds that key can pull the tokens"
                   % (", EIP-7702 delegated" if sp["eip7702_delegate"] else ""),
                   "UNVERIFIED_SPENDER": "unlabeled contract (%d bytes) with no verified source" % sp["code_bytes"],
                   "UNKNOWN_VERIFIED_SPENDER": "unlabeled contract (%d bytes), source-verified%s"
                   % (sp["code_bytes"], " as %s" % sp["verification"]["name"] if (sp["verification"] or {}).get("name") else ""),
                   "UNCLASSIFIED_SPENDER": "unlabeled contract (%d bytes); verification lookup failed" % sp["code_bytes"],
                   "UNLIMITED_KNOWN_SPENDER": "curated spender; consider an exact-amount approval instead of unlimited",
                   "BOUNDED_KNOWN_SPENDER": "curated spender with a bounded allowance"}[code]
            add(sev, code, "%s allowance %s to %s; balance %s, at risk %s %s; %s"
                % (sym, rec["allowance"], _spender_desc(sp), rec["balance"], rec["value_at_risk"], sym, why),
                "%s:%s" % (t, s), chain=chain, owner=o, token=t, symbol=sym, spender=s, spender_label=known.get(s),
                allowance_raw=raw, unlimited=unlimited, balance_raw=bal[t], value_at_risk_raw=var_raw,
                value_at_risk=rec["value_at_risk"], action=action, tx=tx)
        approvals.append(rec)

    # --- Permit2 records + findings
    permit2, lockdown_pairs = [], []
    for (t, s), v in sorted(p2.items()):
        if v["amount"] == 0 and not opts.get("include_zero"):
            continue
        sym, dec = tok_meta(t)
        unlimited = is_unlimited_p2(v["amount"])
        p2_cap = min(v["amount"], allow.get((t, PERMIT2_ADDR), 0))
        expired = v["expiration"] <= now_epoch
        var_raw = 0 if expired else min(bal[t], p2_cap)
        rec = {"kind": "permit2", "token": t, "symbol": sym, "decimals": dec, "spender": s, "spender_label": known.get(s),
               "spender_sources": sorted(ssrc.get(s, ())), "amount_raw": v["amount"],
               "amount": "UNLIMITED" if unlimited else format_units(v["amount"], dec), "unlimited": unlimited,
               "expiration": v["expiration"], "expiration_utc": _utc(v["expiration"]), "expired": expired,
               "nonce": v["nonce"], "erc20_allowance_to_permit2_raw": allow.get((t, PERMIT2_ADDR), 0),
               "balance_raw": bal[t], "value_at_risk_raw": var_raw, "value_at_risk": format_units(var_raw, dec),
               "last_log_block": p2_hits.get((t, s)), "severity": None, "action": None, "finding": None}
        if v["amount"] > 0:
            sp = sp_info[s]
            sev, code, action = permit2_finding(sp, unlimited, v["expiration"], now_epoch)
            tx = {"to": PERMIT2_ADDR, "data": encode_permit2_lockdown([(t, s)]), "function": "lockdown([(%s, %s)])" % (t, s)}
            rec.update(severity=sev, action=action, finding=code, revoke_tx=tx)
            if action != "KEEP":
                lockdown_pairs.append((t, s))
            state = "expired %s" % rec["expiration_utc"] if expired else "expires %s" % rec["expiration_utc"]
            add(sev, code, "Permit2 sub-allowance %s %s to %s (%s); spendable now %s %s"
                % (sym, rec["amount"], _spender_desc(sp), state, rec["value_at_risk"], sym),
                "permit2:%s:%s" % (t, s), chain=chain, owner=o, token=t, symbol=sym, spender=s, spender_label=known.get(s),
                amount_raw=v["amount"], expiration=v["expiration"], unlimited=unlimited, value_at_risk_raw=var_raw,
                value_at_risk=rec["value_at_risk"], action=action, tx=tx)
        permit2.append(rec)

    # --- proxy spenders
    for s, sp in sorted(sp_info.items()):
        if sp["implementation"]:
            iv = (sp["impl_verification"] or {}).get("verified")
            add("MEDIUM" if iv is False else "INFO", "PROXY_SPENDER",
                "spender %s is an EIP-1967 proxy -> implementation %s (verified=%s): its logic can be upgraded"
                % (_spender_desc(sp), sp["implementation"], _yn(iv)), s,
                chain=chain, owner=o, spender=s, implementation=sp["implementation"], impl_verified=iv,
                action="REVIEW")

    report = {
        "chain": chain, "owner": o, "label": label,
        "coverage": {
            "tokens_checked": len(tok_list), "spenders_checked": len(sp_list), "pairs_checked": len(allow),
            "permit2_pairs_checked": len(p2_pairs),
            "token_sources": _count_sources(tsrc), "spender_sources": _count_sources(ssrc),
            "logs": log_cov, "blockscout_tokens": bs_note,
        },
        "tokens": [{"address": t, "symbol": tokens[t][0], "decimals": tokens[t][1], "sources": sorted(tsrc[t]),
                    "balance_raw": bal[t], "balance": format_units(bal[t], tokens[t][1])} for t in tok_list],
        "approvals": approvals,
        "permit2": permit2,
        "spenders": {s: sp_info[s] for s in sorted(sp_info)},
        "permit2_lockdown_all": {"to": PERMIT2_ADDR, "data": encode_permit2_lockdown(sorted(lockdown_pairs)),
                                 "pairs": [list(p) for p in sorted(lockdown_pairs)]} if lockdown_pairs else None,
        "snapshot": {
            "allowances": {"%s:%s" % k: v for k, v in sorted(allow.items()) if v > 0},
            "permit2": {"%s:%s" % k: {"amount": v["amount"], "expiration": v["expiration"]}
                        for k, v in sorted(p2.items()) if v["amount"] > 0},
            "checked": ["%s:%s" % k for k in sorted(allow)],
            "permit2_checked": ["%s:%s" % k for k in p2_pairs],
        },
    }
    return report, findings


def _count_sources(src):
    out = {}
    for s in src.values():
        for x in s:
            out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def _yn(v):
    return "unknown" if v is None else ("yes" if v else "NO")


# ---------------------------------------------------------------- delta
def compute_events(prev, snap, chain, owner):
    """Approval-state events between two snapshots (key chain:owner:[permit2:]token:spender:CODE)."""
    ev = []
    known = known_spenders(chain)

    def add(sev, code, msg, pair_key, **evid):
        ev.append(bc.Finding(sev, code, msg, evid, key="%s:%s:%s:%s" % (chain, owner, pair_key, code)))

    p2_amt = lambda m: {k: int((v or {}).get("amount", 0)) for k, v in (m or {}).items()}  # noqa: E731
    for kind, cur, old_m, checked, unl in (
            ("erc20", snap.get("allowances", {}), prev.get("allowances") or {}, set(snap.get("checked", [])), is_unlimited_erc20),
            ("permit2", p2_amt(snap.get("permit2")), p2_amt(prev.get("permit2")), set(snap.get("permit2_checked", [])), is_unlimited_p2)):
        prefix = "permit2:" if kind == "permit2" else ""
        what = "Permit2 sub-allowance" if kind == "permit2" else "allowance"
        for pair, raw in sorted(cur.items()):
            raw, old = int(raw), int(old_m.get(pair) or 0)
            if raw <= old:
                continue
            tok, sp = pair.split(":")
            is_known = sp in known
            evid = {"token": tok, "spender": sp, "spender_label": known.get(sp), "old_raw": old, "new_raw": raw, "kind": kind}
            if unl(raw) and not unl(old):
                add("MEDIUM" if is_known else "HIGH", "UNLIMITED_GRANTED",
                    "UNLIMITED %s granted on %s to %s%s" % (what, tok, sp, " [%s]" % known[sp] if is_known else " [unlabeled]"),
                    prefix + pair, **evid)
            elif old == 0:
                add("LOW" if is_known else "MEDIUM", "NEW_APPROVAL",
                    "new %s %d on %s to %s%s" % (what, raw, tok, sp, " [%s]" % known[sp] if is_known else " [unlabeled]"),
                    prefix + pair, **evid)
            else:
                add("LOW" if is_known else "MEDIUM", "ALLOWANCE_INCREASED",
                    "%s on %s to %s increased %d -> %d" % (what, tok, sp, old, raw), prefix + pair, **evid)
        for pair, old in sorted(old_m.items()):
            if int(old or 0) > 0 and pair not in cur and pair in checked:
                tok, sp = pair.split(":")
                add("INFO", "APPROVAL_REVOKED", "%s on %s to %s is now zero (was %d)" % (what, tok, sp, int(old)),
                    prefix + pair, token=tok, spender=sp, old_raw=int(old), new_raw=0, kind=kind)
    return ev


def merge_state(prev, snap):
    """Carry forward prior non-zero pairs that were not re-checked this run (never silently forget an approval)."""
    out = {"allowances": dict(snap["allowances"]), "permit2": dict(snap["permit2"])}
    checked, p2_checked = set(snap["checked"]), set(snap["permit2_checked"])
    for k, v in (prev or {}).get("allowances", {}).items():
        if k not in checked and k not in out["allowances"]:
            out["allowances"][k] = v
    for k, v in (prev or {}).get("permit2", {}).items():
        if k not in p2_checked and k not in out["permit2"]:
            out["permit2"][k] = v
    return out


# ---------------------------------------------------------------- rendering
_COLORS = {"CRITICAL": "\033[1;31m", "HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[36m", "INFO": "\033[2m"}


def fmt_finding(f, color=False):
    sev = "%-8s" % f.sev
    if color:
        sev = _COLORS[f.sev] + sev + "\033[0m"
    lines = ["  [%s] %s: %s" % (sev, f.code, f.msg)]
    tx = f.evidence.get("tx")
    if tx:
        lines.append("             action=%s  to=%s  %s" % (f.evidence.get("action"), tx["to"], tx["function"]))
        lines.append("             data=%s" % tx["data"])
    return "\n".join(lines)


def _fmt_logs(c):
    st = c["status"]
    if st == "disabled":
        return "disabled (%s)" % c["note"]
    if st == "skipped":
        return "skipped (%s)" % c["note"]
    s = "%s [%d..%d] %d block(s), %d chunk(s)" % (st, c["from_block"], c["to_block"], c["blocks"], c["chunks"])
    if st == "partial":
        s += "; requested from %d, cut short: %s" % (c["requested_from"], c["note"])
    return s


def render_audit(r):
    lines = ["owner     %s:%s%s" % (r["chain"], r["owner"], "  (%s)" % r["label"] if r.get("label") else "")]
    if r.get("error"):
        return lines + ["error     %s" % r["error"]]
    cv = r["coverage"]
    src = lambda d: ", ".join("%s %d" % kv for kv in d.items())  # noqa: E731
    lines.append("coverage  tokens=%d (%s)  spenders=%d (%s)  erc20_pairs=%d  permit2_pairs=%d"
                 % (cv["tokens_checked"], src(cv["token_sources"]), cv["spenders_checked"], src(cv["spender_sources"]),
                    cv["pairs_checked"], cv["permit2_pairs_checked"]))
    lines.append("logs      %s" % _fmt_logs(cv["logs"]))
    if cv["blockscout_tokens"]:
        lines.append("holdings  blockscout %s" % cv["blockscout_tokens"])
    active = [a for a in r["approvals"] if a["allowance_raw"] > 0]
    for a in r["approvals"]:
        lines.append("approval  %-7s -> %s [%s]  allowance=%s  balance=%s  at_risk=%s  %s"
                     % (a["symbol"], a["spender"], a["spender_label"] or "unlabeled", a["allowance"], a["balance"],
                        a["value_at_risk"], "%s/%s" % (a["severity"], a["action"]) if a["severity"] else "zero"))
    if not active:
        lines.append("approval  (no non-zero ERC-20 allowances among the %d token x spender pairs checked)" % cv["pairs_checked"])
    for p in r["permit2"]:
        lines.append("permit2   %-7s -> %s [%s]  amount=%s  %s %s  at_risk=%s  %s"
                     % (p["symbol"], p["spender"], p["spender_label"] or "unlabeled", p["amount"],
                        "expired" if p["expired"] else "expires", p["expiration_utc"], p["value_at_risk"],
                        "%s/%s" % (p["severity"], p["action"]) if p["severity"] else "zero"))
    for s, sp in r["spenders"].items():
        kind = "EOA" + (" (EIP-7702 -> %s)" % sp["eip7702_delegate"] if sp["eip7702_delegate"] else "") if sp["eoa"] \
            else "contract %dB verified=%s" % (sp["code_bytes"], _yn((sp["verification"] or {}).get("verified")))
        if sp["implementation"]:
            kind += " proxy impl=%s verified=%s" % (sp["implementation"], _yn((sp["impl_verification"] or {}).get("verified")))
        lines.append("spender   %s [%s] %s" % (s, sp["label"] or "unlabeled", kind))
    if r["permit2_lockdown_all"]:
        lk = r["permit2_lockdown_all"]
        lines.append("lockdown  Permit2 lockdown for %d pair(s): to=%s" % (len(lk["pairs"]), lk["to"]))
        lines.append("          data=%s" % lk["data"])
    return lines


def report_json(r):
    out = {k: v for k, v in r.items() if k != "snapshot"}
    if "snapshot" in r:
        out["snapshot"] = {k: r["snapshot"][k] for k in ("allowances", "permit2")}
    return json.loads(json.dumps(out, sort_keys=True))


# ---------------------------------------------------------------- CLI
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser():
    p = _Parser(prog="evm_approval_auditor.py", description="Read-only EVM token approval & spender exposure auditor")
    p.add_argument("owners", nargs="+", metavar="OWNER")
    p.add_argument("--chain", choices=sorted(CHAINS))
    p.add_argument("--all-chains", action="store_true")
    p.add_argument("--tokens", "--token", dest="tokens", action="append", default=[], metavar="ADDR[,ADDR...]")
    p.add_argument("--spenders", "--spender", dest="spenders", action="append", default=[], metavar="ADDR[,ADDR...]")
    p.add_argument("--lookback-blocks", type=int, default=20000, metavar="N")
    p.add_argument("--include-zero", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--state", metavar="PATH")
    p.add_argument("--delta", action="store_true")
    p.add_argument("--watch-label", metavar="NAME")
    p.add_argument("--fail-on", choices=["medium", "high", "critical"], default="medium")
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument("--no-color", action="store_true")
    return p


def _addr_list(values, what):
    out, seen = [], set()
    for v in values:
        for a in v.split(","):
            a = a.strip()
            if not a:
                continue
            if not ADDR_RE.match(a):
                raise UsageError("invalid %s address %r (need 0x + 40 hex chars)" % (what, a))
            if a.lower() not in seen:
                seen.add(a.lower())
                out.append(a.lower())
    return out


def run(argv, out=None, now=None):
    out = out or sys.stdout
    try:
        args = build_parser().parse_args(argv)
        if not args.all_chains and not args.chain:
            raise UsageError("--chain is required (or use --all-chains)")
        if args.delta and not args.state:
            raise UsageError("--delta requires --state PATH")
        if args.timeout <= 0:
            raise UsageError("--timeout must be positive")
        if args.lookback_blocks < 0:
            raise UsageError("--lookback-blocks must be >= 0")
        owners, seen = [], set()
        for a in args.owners:
            if not ADDR_RE.match(a):
                raise UsageError("invalid owner address %r (need 0x + 40 hex chars)" % a)
            if a.lower() not in seen:
                seen.add(a.lower())
                owners.append(a)
        opts = {"tokens": _addr_list(args.tokens, "token"), "spenders": _addr_list(args.spenders, "spender"),
                "lookback": args.lookback_blocks, "include_zero": args.include_zero}
    except UsageError as e:
        print("error: %s" % e, file=sys.stderr)
        return bc.EXIT_USAGE
    except SystemExit as e:  # --help
        return int(e.code or 0)

    now = now or bc.utc_now()
    now_epoch = int(now.timestamp())
    chains = sorted(CHAINS) if args.all_chains else [args.chain]
    ctx = Ctx(timeout=args.timeout)
    store = bc.StateStore(args.state) if args.state else None
    findings, reports, events = [], [], []
    standing_by_key, prior_standing, baseline = {}, {}, {}
    for a in owners:
        if not checksum_ok(a):
            findings.append(bc.Finding("LOW", "NON_EIP55_CHECKSUM", "%s is mixed-case but fails the EIP-55 checksum (expected %s)" % (a, to_checksum(a)),
                                       {"address": a, "expected": to_checksum(a)}, key="addr:%s:NON_EIP55_CHECKSUM" % a.lower()))
        for ch in chains:
            sk = "%s:%s" % (ch, a.lower())
            prev = store.get(sk) if store else None
            try:
                r, fl = audit_owner(ctx, ch, a, opts, now_epoch, label=args.watch_label, prev=prev)
            except RpcError as e:
                ctx.degraded.add("rpc:" + ch)
                reports.append({"chain": ch, "owner": a.lower(), "label": args.watch_label, "error": str(e)})
                continue
            reports.append(r)
            findings.extend(fl)
            snap = r["snapshot"]
            if store:
                standing_by_key[sk] = [f.to_dict() for f in fl]
                if args.delta:
                    if prev is None:
                        baseline[sk] = True
                    else:
                        events.extend(compute_events(prev, snap, ch, a.lower()))
                        prior_standing[sk] = prev.get("findings", [])
                state = merge_state(prev, snap)
                state["checked"], state["permit2_checked"] = snap["checked"], snap["permit2_checked"]
                state["findings"] = standing_by_key[sk]
                state["label"] = args.watch_label
                store.put(sk, state)

    delta = None
    if args.delta:
        d = {"baseline": bool(baseline) and not prior_standing, "events": events, "new": [], "changed": [], "resolved": []}
        old = [x for v in prior_standing.values() for x in v]
        cur = [bc.Finding.from_dict(x) for k, v in standing_by_key.items() if k in prior_standing for x in v]
        base_new = [bc.Finding.from_dict(x) for k, v in standing_by_key.items() if k in baseline for x in v]
        dd = bc.diff_findings(old, cur)
        d["new"], d["changed"], d["resolved"] = dd["NEW"] + base_new, dd["CHANGED"], dd["RESOLVED"]
        delta = d

    all_f = findings + events
    degraded = sorted(ctx.degraded)
    code = bc.exit_code(all_f, bool(degraded), args.fail_on)
    scored = bc.sort_findings(all_f)
    reports.sort(key=lambda r: (r["chain"], r["owner"]))

    if args.json:
        payload = {
            "tool": TOOL,
            "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope_note": SCOPE_NOTE,
            "degraded_sources": degraded,
            "audits": [report_json(r) for r in reports],
            "findings": [f.to_dict() for f in scored],
            "delta": None if delta is None else {
                "baseline": delta["baseline"],
                "events": [f.to_dict() for f in delta["events"]],
                "new": [f.to_dict() for f in delta["new"]],
                "changed": [f.to_dict() for f in delta["changed"]],
                "resolved": [f.to_dict() for f in delta["resolved"]],
            },
            "exit_code": code,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), file=out)
        return code

    color = not args.no_color and not os.environ.get("NO_COLOR") and getattr(out, "isatty", lambda: False)()
    lines = [bc.snapshot_header(TOOL, ctx.endpoints, ctx.fallbacks, now=now), ""]
    for r in reports:
        lines += render_audit(r) + [""]
    if degraded:
        lines += ["DEGRADED  data sources failed: %s (result may be incomplete)" % ", ".join(degraded), ""]
    lines.append("findings")
    lines += [fmt_finding(f, color) for f in scored if f not in events] or ["  (no findings)"]
    if delta is not None:
        lines += ["", "delta"]
        if delta["baseline"]:
            lines.append("  baseline run: no prior state for these owners; recorded %d finding(s)" % len(delta["new"]))
        for label, items in (("EVENT", delta["events"]), ("NEW", delta["new"]), ("CHANGED", delta["changed"]), ("RESOLVED", delta["resolved"])):
            for f in items:
                lines.append("  %-8s [%s] %s: %s" % (label, f.sev, f.code, f.msg))
        if not (delta["events"] or delta["new"] or delta["changed"] or delta["resolved"]):
            lines.append("  (no changes)")
    lines += ["", "exit_code %d" % code, SCOPE_NOTE]
    print("\n".join(lines), file=out)
    return code


def main():
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
