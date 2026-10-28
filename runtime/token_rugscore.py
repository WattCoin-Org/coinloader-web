#!/usr/bin/env python3
"""Cross-Chain Token RugScore (read-only, 100% Python 3 stdlib).

Deterministic 0-100 heuristic score for a Solana SPL / Token-2022 mint or an EVM token/contract
(Ethereum, Base, Arbitrum).  Only public, unauthenticated, read-only endpoints are queried:
Solana JSON-RPC + DexScreener, EVM JSON-RPC + Sourcify v2 + Blockscout v2.  No keys, no signing.

    token_rugscore.py --mint <SOL_MINT> [--json]
    token_rugscore.py --contract 0x... --chain base [--json]
    token_rugscore.py --batch-file targets.txt --json
"""
import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION = "1.0.0"
TOOL = "token-rugscore"
SCHEMA = "token-rugscore/1"
USER_AGENT = "TokenRugScore/1.0 (https://coinloader.com)"
RECEIPT_ENGINE_DIR = "/workspace/social-hub"

DISCLAIMER = ("Deterministic on-chain heuristic score; not financial advice or a guarantee of safety. "
              "A low score does not prove a token is safe and a high score does not prove malicious intent. "
              "Covers only mint/contract state, public holder data, source verification and indexed DEX pairs; "
              "it does not cover the team, off-chain activity, liquidity-lock status or code audits.")

TIMEOUT_SEC = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_BATCH = 20
LIQ_MIN_USD = 10_000.0

SOLANA_RPCS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{addr}"
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

CHAINS = {
    "ethereum": {"id": 1, "dex": "ethereum", "blockscout": "https://eth.blockscout.com",
                 "rpcs": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"]},
    "base": {"id": 8453, "dex": "base", "blockscout": "https://base.blockscout.com",
             "rpcs": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"]},
    "arbitrum": {"id": 42161, "dex": "arbitrum", "blockscout": "https://arbitrum.blockscout.com",
                 "rpcs": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"]},
}
CHAIN_ALIASES = {"ethereum": "ethereum", "eth": "ethereum", "base": "base", "arbitrum": "arbitrum", "arb": "arbitrum"}
SOURCIFY_URL = "https://sourcify.dev/server/v2/contract/{cid}/{addr}?fields=abi,proxyResolution,compilation"

ALLOWED_HOSTS = {
    "api.mainnet-beta.solana.com", "solana-rpc.publicnode.com", "api.dexscreener.com", "sourcify.dev",
    "eth.blockscout.com", "base.blockscout.com", "arbitrum.blockscout.com",
    "ethereum-rpc.publicnode.com", "eth.llamarpc.com", "mainnet.base.org", "base-rpc.publicnode.com",
    "arb1.arbitrum.io", "arbitrum-one-rpc.publicnode.com",
}

SLOTS = [
    ("impl1967", "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"),
    ("admin1967", "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"),
    ("beacon", "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"),
    ("uups1822", "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"),
    ("zos_impl", "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"),
    ("zos_admin", "0x10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b"),
]
SEL_IMPLEMENTATION, SEL_OWNER = "0x5c60da1b", "0x8da5cb5b"
SEL_GET_THRESHOLD, SEL_GET_OWNERS = "0xe75235b8", "0xa0e67e2b"
SEL_GET_MIN_DELAY, SEL_DELAY = "0xf27a0c92", "0x6a42b8f8"
CLONE_PREFIX, CLONE_SUFFIX = "363d3d373d3d3d363d73", "5af43d82803e903d91602b57fd5bf3"
OP_SELFDESTRUCT, OP_DELEGATECALL = 0xFF, 0xF4

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MINT_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")

DANGEROUS_EXTS = ("permanentDelegate", "transferHook", "transferFeeConfig", "defaultAccountState")


class AssessmentError(Exception):
    """A target could not be assessed (bad input, missing account, all upstreams down)."""


# --------------------------------------------------------------------------- validation
def b58decode(s):
    n = 0
    for ch in s:
        idx = B58_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError("invalid_base58_character")
        n = n * 58 + idx
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + body


def is_valid_mint(s):
    if not isinstance(s, str) or MINT_RE.fullmatch(s) is None:
        return False
    try:
        return len(b58decode(s)) == 32
    except ValueError:
        return False


def is_valid_evm_address(s):
    return isinstance(s, str) and ADDR_RE.fullmatch(s) is not None


def normalize_chain(chain):
    c = CHAIN_ALIASES.get(str(chain or "").strip().lower())
    if not c:
        raise AssessmentError("chain must be one of ethereum|eth|base|arbitrum|arb")
    return c


# --------------------------------------------------------------------------- HTTP (allow-listed, size-capped)
def http_json(url, payload=None, timeout=TIMEOUT_SEC):
    """Return (parsed_json_or_None, status).  Raises on network failure.  HTTPS + host allowlist only."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or (u.hostname or "").lower() not in ALLOWED_HOSTS:
        raise ValueError("host_not_allowed")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            status = resp.status
    except urllib.error.HTTPError as e:
        return None, e.code
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("response_too_large")
    try:
        return json.loads(raw.decode("utf-8")), status
    except ValueError:
        return None, status


def _rpc(urls, method, params, gaps, soft=False):
    """JSON-RPC with endpoint failover.  Returns the `result` (None on total failure; appends a gap)."""
    last = "unknown"
    for url in urls:
        try:
            body, status = http_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        except Exception as e:  # noqa: BLE001 - any transport failure falls through to the next endpoint
            last = f"network_error:{type(e).__name__}"
            continue
        if status != 200 or not isinstance(body, dict):
            last = f"http_{status}"
            continue
        if body.get("error"):
            last = "rpc_error"
            if soft:
                return None
            continue
        if "result" in body:
            return body["result"]
        last = "no_result"
    gaps.append({"source": f"rpc_{method}", "reason": last})
    return None


# --------------------------------------------------------------------------- scoring helpers
def finding(rule_id, title, status, points, detail, evidence=None):
    return {"rule_id": rule_id, "title": title, "status": status, "points": points,
            "detail": detail, "evidence": evidence or {}}


def tier_for(score):
    if score >= 60:
        return "HIGH RISK", "CRITICAL"
    if score >= 25:
        return "MEDIUM RISK", "WARN"
    return "LOW RISK", "PASS"


def seal(target, chain, findings, facts, gaps):
    """Build the deterministic payload, cap the score at 100 and compute the canonical audit hash."""
    score = min(100, sum(f["points"] for f in findings))
    tier, status = tier_for(score)
    core = {"schema": SCHEMA, "tool": TOOL, "version": VERSION, "target": target, "chain": chain,
            "rug_score": score, "score_max": 100, "risk_tier": tier, "risk_status": status,
            "findings": findings, "facts": facts, "gaps": sorted(gaps, key=lambda g: (g["source"], g["reason"])),
            "disclaimer": DISCLAIMER}
    out = dict(core)
    out["generated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # run metadata: not part of the hash
    out["audit_sha256"] = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return out


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) < 1e30 else None


def fetch_dex(addr, dex_chain, gaps):
    """DexScreener pairs for `addr` on one chain: (pair_count, best_liquidity_usd) or (None, None) on failure."""
    try:
        body, status = http_json(DEXSCREENER_URL.format(addr=addr))
    except Exception as e:  # noqa: BLE001
        gaps.append({"source": "dexscreener_tokens", "reason": f"network_error:{type(e).__name__}"})
        return None, None
    if body is None:
        gaps.append({"source": "dexscreener_tokens", "reason": f"http_{status}"})
        return None, None
    pairs = [p for p in (body.get("pairs") or []) if isinstance(p, dict) and str(p.get("chainId", "")).lower() == dex_chain]
    liqs = [(_num((p.get("liquidity") or {}).get("usd")) or 0.0) for p in pairs]
    return len(pairs), round(max(liqs), 2) if liqs else 0.0


# --------------------------------------------------------------------------- Solana
def assess_solana(mint):
    if not is_valid_mint(mint):
        raise AssessmentError("mint must be a base58 32-byte Solana address")
    gaps = []
    res = _rpc(SOLANA_RPCS, "getAccountInfo", [mint, {"encoding": "jsonParsed"}], gaps)
    value = res.get("value") if isinstance(res, dict) else None
    if res is None:
        raise AssessmentError("Solana RPC unavailable: " + (gaps[-1]["reason"] if gaps else "unknown"))
    parsed = ((value or {}).get("data") or {}).get("parsed") if isinstance((value or {}).get("data"), dict) else None
    program = (value or {}).get("owner")
    if not isinstance(parsed, dict) or parsed.get("type") != "mint" or program not in (SPL_TOKEN_PROGRAM, TOKEN_2022_PROGRAM):
        raise AssessmentError("address is not an SPL / Token-2022 mint account")
    info = parsed.get("info") or {}
    try:
        decimals, supply = int(info.get("decimals")), int(info.get("supply"))
    except (TypeError, ValueError):
        raise AssessmentError("mint account has an unparseable decimals/supply") from None
    mint_auth, freeze_auth = info.get("mintAuthority"), info.get("freezeAuthority")
    exts = {}
    for ext in (info.get("extensions") or [])[:40]:
        if isinstance(ext, dict) and ext.get("extension"):
            exts[str(ext["extension"])] = ext.get("state") if isinstance(ext.get("state"), dict) else {}

    # holder concentration: exact integer math over the RPC's 20 largest token accounts
    top10_pct, la_ok = None, False
    la = _rpc(SOLANA_RPCS, "getTokenLargestAccounts", [mint], gaps)
    if isinstance(la, dict) and supply > 0:
        amts = sorted((int(a["amount"]) for a in (la.get("value") or []) if isinstance(a, dict) and str(a.get("amount", "")).isdigit()),
                      reverse=True)
        if amts:
            la_ok, top10_pct = True, round(sum(amts[:10]) * 100 / supply, 2)
    pair_count, best_liq = fetch_dex(mint, "solana", gaps)

    fs = []
    if mint_auth:
        fs.append(finding("RS-SOL-01", "Mint Authority", "WARN", 30,
                          "Mint authority is ACTIVE: the holder can create additional supply.", {"mint_authority": mint_auth}))
    else:
        fs.append(finding("RS-SOL-01", "Mint Authority", "PASS", 0, "Mint authority is revoked.", {"mint_authority": None}))
    if freeze_auth:
        fs.append(finding("RS-SOL-02", "Freeze Authority", "WARN", 20,
                          "Freeze authority is ACTIVE: the holder can freeze individual token accounts.", {"freeze_authority": freeze_auth}))
    else:
        fs.append(finding("RS-SOL-02", "Freeze Authority", "PASS", 0, "Freeze authority is revoked.", {"freeze_authority": None}))

    present = []
    for name in DANGEROUS_EXTS:
        st = exts.get(name)
        if st is None:
            continue
        if name == "transferFeeConfig":
            bps = [int(f.get("transferFeeBasisPoints") or 0) for f in (st.get("olderTransferFee"), st.get("newerTransferFee"))
                   if isinstance(f, dict) and str(f.get("transferFeeBasisPoints", "0")).isdigit()]
            if not any(bps):
                continue
        if name == "defaultAccountState" and str(st.get("accountState") or st.get("state") or "").lower() != "frozen":
            continue
        present.append(name)
    if program != TOKEN_2022_PROGRAM:
        fs.append(finding("RS-SOL-03", "Token-2022 Dangerous Extensions", "PASS", 0,
                          "Legacy SPL Token program: no extension support (no transfer hooks, permanent delegate or transfer fees).",
                          {"owner_program": program, "dangerous_extensions": []}))
    elif present:
        fs.append(finding("RS-SOL-03", "Token-2022 Dangerous Extensions", "CRITICAL", 35,
                          "Dangerous Token-2022 extension(s) present: " + ", ".join(present) + ".",
                          {"owner_program": program, "dangerous_extensions": present}))
    else:
        fs.append(finding("RS-SOL-03", "Token-2022 Dangerous Extensions", "PASS", 0,
                          "Token-2022 mint without PermanentDelegate, TransferHook, non-zero TransferFee or frozen default state.",
                          {"owner_program": program, "dangerous_extensions": []}))

    if not la_ok:
        fs.append(finding("RS-SOL-04", "Top-10 Holder Concentration", "INFO", 0,
                          "getTokenLargestAccounts was unavailable or empty; concentration not assessed (disclosed gap).", {"top10_pct": None}))
    elif top10_pct > 80:
        fs.append(finding("RS-SOL-04", "Top-10 Holder Concentration", "CRITICAL", 30,
                          f"Top-10 token accounts hold {top10_pct}% of supply (>80%).", {"top10_pct": top10_pct}))
    elif top10_pct > 50:
        fs.append(finding("RS-SOL-04", "Top-10 Holder Concentration", "WARN", 20,
                          f"Top-10 token accounts hold {top10_pct}% of supply (>50%).", {"top10_pct": top10_pct}))
    else:
        fs.append(finding("RS-SOL-04", "Top-10 Holder Concentration", "PASS", 0,
                          f"Top-10 token accounts hold {top10_pct}% of supply.", {"top10_pct": top10_pct}))

    if pair_count is None:
        fs.append(finding("RS-SOL-05", "DEX Liquidity & Pair Depth", "INFO", 0,
                          "DexScreener unavailable; liquidity not assessed (disclosed gap).", {"pairs": None, "best_liquidity_usd": None}))
    elif pair_count == 0 or best_liq < LIQ_MIN_USD:
        fs.append(finding("RS-SOL-05", "DEX Liquidity & Pair Depth", "WARN", 15,
                          f"{pair_count} indexed pair(s); deepest liquidity ${best_liq:,.2f} (<$10,000).",
                          {"pairs": pair_count, "best_liquidity_usd": best_liq}))
    else:
        fs.append(finding("RS-SOL-05", "DEX Liquidity & Pair Depth", "PASS", 0,
                          f"{pair_count} indexed pair(s); deepest liquidity ${best_liq:,.2f}.",
                          {"pairs": pair_count, "best_liquidity_usd": best_liq}))
    facts = {"owner_program": program, "decimals": decimals, "supply_raw": str(supply),
             "extensions": sorted(exts), "top10_pct": top10_pct, "dex_pairs": pair_count, "best_liquidity_usd": best_liq}
    return seal(mint, "solana", fs, facts, gaps)


# --------------------------------------------------------------------------- EVM
def hex_to_bytes(h):
    h = (h or "0x")[2:]
    return bytes.fromhex(h if len(h) % 2 == 0 else "0" + h)


def strip_metadata(code):
    if len(code) >= 2:
        ln = int.from_bytes(code[-2:], "big")
        start = len(code) - 2 - ln
        if ln >= 1 and start >= 0 and 0xA1 <= code[start] <= 0xA6:
            return code[:start]
    return code


def scan_opcodes(code):
    """Set of real opcodes; PUSH1..PUSH32 immediates are skipped."""
    ops, i, n = set(), 0, len(code)
    while i < n:
        op = code[i]
        if 0x60 <= op <= 0x7F:
            i += op - 0x5F
        else:
            ops.add(op)
        i += 1
    return ops


def opcode_flags(code_hex):
    ops = scan_opcodes(strip_metadata(hex_to_bytes(code_hex)))
    return {"selfdestruct": OP_SELFDESTRUCT in ops, "delegatecall": OP_DELEGATECALL in ops}


def word_addr(w):
    if not isinstance(w, str) or len(w) < 3:
        return None
    try:
        if int(w, 16) == 0:
            return None
    except ValueError:
        return None
    return "0x" + w[2:].rjust(64, "0")[-40:].lower()


def decode_uint(h):
    try:
        return int(h, 16) if isinstance(h, str) and len(h) > 2 else None
    except ValueError:
        return None


def clone_impl(code_hex):
    c = (code_hex or "")[2:].lower()
    if c.startswith(CLONE_PREFIX) and c[len(CLONE_PREFIX) + 40:].startswith(CLONE_SUFFIX):
        return "0x" + c[len(CLONE_PREFIX):len(CLONE_PREFIX) + 40]
    return None


class _Evm:
    def __init__(self, chain):
        self.chain, self.cfg, self.gaps = chain, CHAINS[chain], []

    def rpc(self, method, params, soft=False):
        return _rpc(self.cfg["rpcs"], method, params, self.gaps, soft=soft)

    def code(self, addr):
        r = self.rpc("eth_getCode", [addr, "latest"])
        return r.lower() if isinstance(r, str) else None

    def call(self, to, sel):
        r = self.rpc("eth_call", [{"to": to, "data": sel}, "latest"], soft=True)
        return r if isinstance(r, str) else None

    def verification(self, addr):
        """{'verified': True|False|None, 'source': ..., 'implementations': [...]}.  None = both sources unreachable."""
        info = {"verified": None, "source": None, "implementations": []}
        try:
            body, status = http_json(SOURCIFY_URL.format(cid=self.cfg["id"], addr=addr))
            if status == 200 and isinstance(body, dict):
                info.update(verified=bool(body.get("match")), source="sourcify")
                pr = body.get("proxyResolution") or {}
                if pr.get("isProxy"):
                    info["implementations"] = sorted({i["address"].lower() for i in (pr.get("implementations") or [])
                                                      if isinstance(i, dict) and ADDR_RE.fullmatch(str(i.get("address", "")))})
            elif status == 404:
                info.update(verified=False, source="sourcify")
        except Exception:  # noqa: BLE001
            pass
        if info["verified"] is not True:
            try:
                body, status = http_json(f"{self.cfg['blockscout']}/api/v2/smart-contracts/{addr}")
                if status == 200 and isinstance(body, dict):
                    if body.get("is_verified") or body.get("is_fully_verified") or body.get("is_partially_verified") or body.get("source_code"):
                        info.update(verified=True, source="blockscout")
                    elif info["verified"] is None:
                        info.update(verified=False, source="blockscout")
                elif status == 404 and info["verified"] is None:
                    info.update(verified=False, source="blockscout")
            except Exception:  # noqa: BLE001
                pass
        if info["verified"] is None:
            self.gaps.append({"source": "sourcify_blockscout", "reason": "unreachable"})
        return info

    def classify_admin(self, addr, depth=0):
        """EOA | safe | timelock | contract (follows owner() up to 2 hops)."""
        code = self.code(addr)
        if code in (None, "0x", "0x0", ""):
            return {"address": addr, "kind": "EOA" if code is not None else "UNKNOWN"}
        thr, owners = decode_uint(self.call(addr, SEL_GET_THRESHOLD)), self.call(addr, SEL_GET_OWNERS)
        if thr and owners:
            return {"address": addr, "kind": "safe", "threshold": thr}
        delay = decode_uint(self.call(addr, SEL_GET_MIN_DELAY))
        if delay is None:
            delay = decode_uint(self.call(addr, SEL_DELAY))
        if delay is not None:
            return {"address": addr, "kind": "timelock", "delay_seconds": delay}
        owner = word_addr(self.call(addr, SEL_OWNER))
        if owner and depth < 2:
            return {"address": addr, "kind": "contract", "owner": self.classify_admin(owner, depth + 1)}
        return {"address": addr, "kind": "contract"}


def _admin_chain(adm):
    """Flatten an admin tree to its kinds, outermost first."""
    kinds = []
    while adm:
        kinds.append(adm["kind"])
        adm = adm.get("owner")
    return kinds


def assess_evm(contract, chain):
    chain = normalize_chain(chain)
    if not is_valid_evm_address(contract):
        raise AssessmentError("contract must be 0x + 40 hex characters")
    addr = contract.lower()
    ev = _Evm(chain)
    code = ev.code(addr)
    if code is None:
        raise AssessmentError(f"{chain} RPC unavailable")
    if code in ("0x", "0x0", ""):
        raise AssessmentError(f"no contract code at {addr} on {chain} (EOA, self-destructed or wrong chain)")

    words = dict(zip([n for n, _ in SLOTS], [ev.rpc("eth_getStorageAt", [addr, s, "latest"], soft=True) for _, s in SLOTS]))
    ptype, impl = None, None
    ci = clone_impl(code)
    if ci:
        ptype, impl = "EIP-1167 minimal proxy", ci
    elif word_addr(words["impl1967"]):
        ptype, impl = "EIP-1967", word_addr(words["impl1967"])
    elif word_addr(words["beacon"]):
        ptype = "EIP-1967 beacon"
        impl = word_addr(ev.call(word_addr(words["beacon"]), SEL_IMPLEMENTATION))
    elif word_addr(words["uups1822"]):
        ptype, impl = "EIP-1822 proxiable", word_addr(words["uups1822"])
    elif word_addr(words["zos_impl"]):
        ptype, impl = "ZeppelinOS legacy", word_addr(words["zos_impl"])
    admin_slot = word_addr(words["admin1967"]) or word_addr(words["zos_admin"])

    ver = ev.verification(addr)
    if not impl and ver["implementations"]:
        impl, ptype = ver["implementations"][0], ptype or "proxy (per sourcify)"
    is_proxy = ptype is not None
    impl_code = ev.code(impl) if impl else None
    impl_ver = ev.verification(impl) if impl and impl_code not in (None, "0x", "") else None

    # --- RS-EVM-01 source verification
    unver = [n for n, v in (("target", ver), ("implementation", impl_ver)) if v is not None and v["verified"] is False]
    if unver:
        fs = [finding("RS-EVM-01", "Source Code Verification", "CRITICAL", 35,
                      "Source code is NOT verified on Sourcify/Blockscout for the " + " and ".join(unver) + ".",
                      {"target_verified": ver["verified"], "implementation_verified": impl_ver["verified"] if impl_ver else None})]
    elif ver["verified"] is None or (impl_ver is not None and impl_ver["verified"] is None):
        fs = [finding("RS-EVM-01", "Source Code Verification", "INFO", 0,
                      "Verification sources unreachable; verification not assessed (disclosed gap).",
                      {"target_verified": ver["verified"], "implementation_verified": impl_ver["verified"] if impl_ver else None})]
    else:
        fs = [finding("RS-EVM-01", "Source Code Verification", "PASS", 0,
                      f"Source verified via {ver['source']}" + (" (implementation verified too)." if impl_ver else "."),
                      {"target_verified": True, "implementation_verified": True if impl_ver else None, "source": ver["source"]})]

    # --- RS-EVM-02 upgradeability & admin control
    admin, controller = None, admin_slot
    if is_proxy:
        if not controller:
            controller = word_addr(ev.call(addr, SEL_OWNER)) or (word_addr(ev.call(impl, SEL_OWNER)) if impl else None)
        admin = ev.classify_admin(controller) if controller else None
        kinds = _admin_chain(admin)
        if "timelock" in kinds:
            fs.append(finding("RS-EVM-02", "Upgradeable Proxy & Admin Control", "PASS", 0,
                              f"{ptype} proxy, but upgrades are gated by a timelock.", {"proxy_type": ptype, "admin": admin}))
        elif kinds and kinds[0] == "EOA":
            fs.append(finding("RS-EVM-02", "Upgradeable Proxy & Admin Control", "CRITICAL", 30,
                              f"{ptype} proxy upgradeable by a single EOA ({controller}) without a timelock.", {"proxy_type": ptype, "admin": admin}))
        else:
            what = "admin could not be resolved (upgrade authority may sit inside the implementation)" if not admin else \
                   "admin is a " + ("Safe multisig" if kinds[0] == "safe" else "contract") + " without a timelock"
            fs.append(finding("RS-EVM-02", "Upgradeable Proxy & Admin Control", "WARN", 30,
                              f"{ptype} proxy upgradeable without a timelock: {what}.", {"proxy_type": ptype, "admin": admin}))
    else:
        fs.append(finding("RS-EVM-02", "Upgradeable Proxy & Admin Control", "PASS", 0,
                          "No proxy pattern detected (EIP-1967/1822/1167/beacon/ZeppelinOS); treated as immutable.", {"proxy_type": None, "admin": None}))

    # --- RS-EVM-03 dangerous opcodes (proxy DELEGATECALL is expected; implementation / non-proxy DELEGATECALL is not)
    tgt = opcode_flags(code)
    imp = opcode_flags(impl_code) if impl_code not in (None, "0x", "") and impl else {"selfdestruct": False, "delegatecall": False}
    hits = []
    if tgt["selfdestruct"]:
        hits.append("SELFDESTRUCT in target")
    if imp["selfdestruct"]:
        hits.append("SELFDESTRUCT in implementation")
    if tgt["delegatecall"] and not is_proxy:
        hits.append("DELEGATECALL in non-proxy target")
    if imp["delegatecall"]:
        hits.append("DELEGATECALL in implementation")
    ev_op = {"target": tgt, "implementation": imp if impl else None}
    if hits:
        fs.append(finding("RS-EVM-03", "Dangerous Bytecode Opcodes", "CRITICAL", 25,
                          "Byte-level heuristic hit: " + "; ".join(hits) + ".", ev_op))
    else:
        fs.append(finding("RS-EVM-03", "Dangerous Bytecode Opcodes", "PASS", 0, "No SELFDESTRUCT or unexpected DELEGATECALL found.", ev_op))

    # --- RS-EVM-04 DEX liquidity (informational, never adds points)
    pair_count, best_liq = fetch_dex(addr, ev.cfg["dex"], ev.gaps)
    if pair_count is None:
        fs.append(finding("RS-EVM-04", "DEX Liquidity / Pair Check", "INFO", 0, "DexScreener unavailable; liquidity not assessed (disclosed gap).",
                          {"pairs": None, "best_liquidity_usd": None}))
    elif pair_count and best_liq >= LIQ_MIN_USD:
        fs.append(finding("RS-EVM-04", "DEX Liquidity / Pair Check", "PASS", 0,
                          f"{pair_count} indexed pair(s); deepest liquidity ${best_liq:,.2f}.", {"pairs": pair_count, "best_liquidity_usd": best_liq}))
    else:
        fs.append(finding("RS-EVM-04", "DEX Liquidity / Pair Check", "INFO", 0,
                          f"{pair_count} indexed pair(s); deepest liquidity ${best_liq:,.2f} (<$10,000 or none; informational only).",
                          {"pairs": pair_count, "best_liquidity_usd": best_liq}))
    facts = {"chain_id": ev.cfg["id"], "bytecode_bytes": (len(code) - 2) // 2, "proxy_type": ptype, "implementation": impl,
             "dex_pairs": pair_count, "best_liquidity_usd": best_liq}
    return seal(addr, chain, fs, facts, ev.gaps)


# --------------------------------------------------------------------------- batch / dispatch
def parse_batch_file(path):
    """One target per line: a Solana mint or `chain:0x...`.  Blank lines and # comments are skipped."""
    targets = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" in line:
                chain, _, addr = line.partition(":")
                targets.append(("evm", addr.strip(), chain.strip()))
            else:
                targets.append(("sol", line, None))
    if len(targets) > MAX_BATCH:
        raise AssessmentError(f"batch file has {len(targets)} targets; max is {MAX_BATCH}")
    return targets


def assess_target(kind, addr, chain=None):
    return assess_solana(addr) if kind == "sol" else assess_evm(addr, chain)


def assess_many(targets):
    results = []
    for kind, addr, chain in targets:
        try:
            results.append(assess_target(kind, addr, chain))
        except AssessmentError as e:
            results.append({"schema": SCHEMA, "tool": TOOL, "target": addr, "chain": chain or "solana", "error": str(e)})
    core = {"schema": SCHEMA + "-batch", "tool": TOOL, "version": VERSION, "results": results, "disclaimer": DISCLAIMER}
    core["audit_sha256"] = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return core


# --------------------------------------------------------------------------- output
def render_markdown(r):
    if "results" in r:
        return "\n\n---\n\n".join(render_markdown(x) for x in r["results"]) + f"\n\nBatch audit_sha256: `{r['audit_sha256']}`\n"
    if "error" in r:
        return f"# Token RugScore: `{r['target']}`\n\nERROR: {r['error']}\n"
    lines = [f"# Token RugScore: `{r['target']}` ({r['chain']})", "",
             f"**RUGSCORE: {r['rug_score']}/100 ({r['risk_tier']})** [{r['risk_status']}]", "",
             "| Rule | Check | Status | Points | Detail |", "|---|---|---|---|---|"]
    for f in r["findings"]:
        lines.append(f"| {f['rule_id']} | {f['title']} | {f['status']} | +{f['points']} | {f['detail'].replace('|', '/')} |")
    if r["gaps"]:
        lines += ["", "**Disclosed data gaps:** " + ", ".join(f"`{g['source']}` ({g['reason']})" for g in r["gaps"])]
    lines += ["", f"audit_sha256: `{r['audit_sha256']}`", "", f"> {r['disclaimer']}", ""]
    return "\n".join(lines)


def write_receipt(result, png_path):
    """Render the live receipt card via the social-hub engine if it is installed; returns True when written."""
    if not os.path.isfile(os.path.join(RECEIPT_ENGINE_DIR, "render_receipt.py")):
        print("receipt engine not found at " + RECEIPT_ENGINE_DIR + "; skipping --receipt-out", file=sys.stderr)
        return False
    sys.path.insert(0, RECEIPT_ENGINE_DIR)
    try:
        import render_receipt as rr
        receipt, text = rr.from_token_rugscore_json(result)
        rr.render_receipt_png(receipt, png_path)
    except Exception as e:  # noqa: BLE001
        print(f"receipt render failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    print(f"receipt: {png_path}", file=sys.stderr)
    print(f"post: {text}", file=sys.stderr)
    return True


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        sys.exit(2)


def build_parser():
    p = _Parser(prog="token_rugscore.py", description="Read-only cross-chain token RugScore (0-100 deterministic heuristic)")
    p.add_argument("--version", action="version", version=f"token_rugscore {VERSION}")
    p.add_argument("--mint", metavar="SOL_MINT", help="Solana SPL / Token-2022 mint address")
    p.add_argument("--contract", metavar="0x_ADDR", help="EVM token/contract address (needs --chain)")
    p.add_argument("--chain", help="ethereum|base|arbitrum|eth|arb")
    p.add_argument("--batch-file", metavar="PATH", help="one mint or chain:0x... per line")
    p.add_argument("--json", action="store_true", help="emit deterministic JSON")
    p.add_argument("--markdown", action="store_true", help="emit Markdown (default without --json)")
    p.add_argument("--receipt-out", metavar="PNG", help="also render a 1200x675 receipt card")
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    modes = [bool(a.mint), bool(a.contract), bool(a.batch_file)]
    if sum(modes) != 1:
        p.error("exactly one of --mint, --contract or --batch-file is required")
    if a.contract and not a.chain:
        p.error("--contract requires --chain")
    if a.json and a.markdown:
        p.error("choose --json or --markdown, not both")
    try:
        if a.batch_file:
            result = assess_many(parse_batch_file(a.batch_file))
        elif a.mint:
            result = assess_solana(a.mint)
        else:
            result = assess_evm(a.contract, a.chain)
    except (AssessmentError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if a.receipt_out:
        first = next((x for x in result.get("results", [result]) if "error" not in x), None)
        if first:
            write_receipt(first, a.receipt_out)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) if a.json else render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
