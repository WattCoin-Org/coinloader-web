#!/usr/bin/env python3
"""EVM Smart Contract & Proxy Upgradeability Inspector (read-only, stdlib + bot_common).

Reads bytecode, proxy slots, admin/owner and verification state for contracts on Ethereum,
Base and Arbitrum One, classifies who can change the contract, and optionally diffs against
a previous snapshot (delta mode).  Exit codes: 0 clean, 1 MEDIUM, 2 HIGH, 3 CRITICAL,
10 bad input, 11 degraded data sources.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bot_common as bc  # noqa: E402

TOOL = "evm-contract-inspector"
SCOPE_NOTE = ("SCOPE_NOTE: Read-only on-chain and public-API inspection. No private keys, seed phrases or signing; "
              "no transaction is built or broadcast. Findings are heuristics with stated evidence, not verdicts, "
              "and are not tax, legal or investment advice. An EOA admin is not proof of weak custody "
              "(HSM/MPC keys look identical on-chain). Opcode scans are byte-level heuristics.")

CHAINS = {
    "eth": {"id": 1, "rpcs": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"]},
    "base": {"id": 8453, "rpcs": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"]},
    "arb": {"id": 42161, "rpcs": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"]},
}

SLOTS = [
    ("impl1967", "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"),
    ("admin1967", "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"),
    ("beacon", "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"),
    ("uups1822", "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"),
    ("zos_impl", "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"),
    ("zos_admin", "0x10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b"),
]

SEL_IMPLEMENTATION = "0x5c60da1b"
SEL_OWNER = "0x8da5cb5b"
SEL_GET_THRESHOLD = "0xe75235b8"
SEL_GET_OWNERS = "0xa0e67e2b"
SEL_GET_MIN_DELAY = "0xf27a0c92"
SEL_DELAY = "0x6a42b8f8"

SOURCIFY_URL = "https://sourcify.dev/server/v2/contract/{cid}/{addr}?fields=abi,proxyResolution,compilation"
BLOCKSCOUT_URL = "https://eth.blockscout.com/api/v2/smart-contracts/{addr}"

CLONE_PREFIX = "363d3d373d3d3d363d73"
CLONE_SUFFIX = "5af43d82803e903d91602b57fd5bf3"
ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ZERO_ADDR = "0x" + "0" * 40

OP_SELFDESTRUCT, OP_DELEGATECALL = 0xFF, 0xF4

SNAP_KEYS = ("implementation", "admin", "admin_owner", "code_hash", "impl_code_hash",
             "verified", "impl_verified", "safe_threshold", "timelock_delay")


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
    out = b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out


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


# ---------------------------------------------------------------- bytecode helpers
def strip_metadata(code):
    """Drop the trailing Solidity CBOR metadata blob (its hash bytes would give false opcode hits)."""
    if len(code) >= 2:
        ln = int.from_bytes(code[-2:], "big")
        start = len(code) - 2 - ln
        if ln >= 1 and start >= 0 and 0xA1 <= code[start] <= 0xA6:
            return code[:start]
    return code


def scan_opcodes(code):
    """Set of real opcodes in runtime bytecode; PUSH1..PUSH32 (0x60..0x7f) immediates are skipped."""
    ops, i, n = set(), 0, len(code)
    while i < n:
        op = code[i]
        if 0x60 <= op <= 0x7F:
            i += op - 0x5F
        else:
            ops.add(op)
        i += 1
    return ops


def hex_to_bytes(h):
    h = (h or "0x")[2:]
    if len(h) % 2:
        h = "0" + h
    return bytes.fromhex(h)


def clone_impl(code_hex):
    """EIP-1167 minimal proxy: exactly 45 bytes. Returns implementation address or None."""
    c = code_hex.lower()
    if (len(c) - 2) // 2 == 45 and c.startswith("0x" + CLONE_PREFIX) and c.endswith(CLONE_SUFFIX):
        return "0x" + c[22:62]
    return None


# ---------------------------------------------------------------- ABI decoding
def decode_uint(h):
    if not isinstance(h, str) or len(h) < 66:
        return None
    try:
        return int(h[2:66], 16)
    except ValueError:
        return None


def decode_address(h):
    """address return value; None when absent/zero/malformed."""
    if not isinstance(h, str) or len(h) < 66:
        return None
    try:
        if int(h[2:26], 16) != 0:
            return None
        a = "0x" + h[26:66].lower()
        int(a, 16)
    except ValueError:
        return None
    return None if a == ZERO_ADDR else a


def decode_address_array(h):
    """ABI-decode address[] (as returned by Safe.getOwners)."""
    try:
        data = h[2:]
        off = int(data[0:64], 16) * 2
        ln = int(data[off:off + 64], 16)
        if ln > 256 or len(data) < off + 64 + 64 * ln:
            return None
        out = []
        for i in range(ln):
            w = data[off + 64 + 64 * i: off + 128 + 64 * i]
            out.append("0x" + w[24:].lower())
        return out
    except (ValueError, TypeError):
        return None


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


# ---------------------------------------------------------------- RPC
class RpcError(Exception):
    pass


class Ctx:
    def __init__(self, timeout=20):
        self.timeout = timeout
        self.degraded = set()
        self.endpoints = set()
        self.fallbacks = []


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
                ctx.fallbacks.append("%s: %s failed -> %s" % (chain, urls[0], url))
            return out
    raise RpcError("all %s RPCs failed for %s" % (chain, calls[0][0]))


def rpc_call(ctx, chain, method, params, soft=False):
    return rpc_batch(ctx, chain, [(method, params)], soft=soft)[0]


def get_code(ctx, chain, addr):
    return rpc_call(ctx, chain, "eth_getCode", [addr, "latest"]).lower()


def eth_calls(ctx, chain, to, selectors):
    return rpc_batch(ctx, chain, [("eth_call", [{"to": to, "data": s}, "latest"]) for s in selectors], soft=True)


# ---------------------------------------------------------------- verification lookups
def lookup_verification(ctx, chain, addr):
    """Sourcify v2 first (404 = unverified, not degraded); Blockscout fallback on Ethereum."""
    a = addr.lower()
    info = {"verified": None, "source": None, "match": None, "name": None, "proxy_type": None,
            "implementations": [], "sourcify": "degraded"}
    res = bc.http_json(SOURCIFY_URL.format(cid=CHAINS[chain]["id"], addr=a), retries=1, timeout=ctx.timeout)
    if res.status == 200 and isinstance(res.data, dict):
        d = res.data
        pr = d.get("proxyResolution") or {}
        info["match"] = d.get("match")
        info["verified"] = bool(d.get("match"))
        info["sourcify"] = "verified" if info["verified"] else "unverified"
        info["source"] = "sourcify"
        info["name"] = (d.get("compilation") or {}).get("name")
        info["proxy_type"] = pr.get("proxyType") if pr.get("isProxy") else None
        info["implementations"] = sorted(
            {i["address"].lower() for i in (pr.get("implementations") or []) if isinstance(i, dict) and i.get("address")})
    elif res.status == 404:
        info.update(verified=False, sourcify="unverified", source="sourcify")
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
            impls = []
            for i in d.get("implementations") or []:
                if isinstance(i, dict):
                    v = i.get("address_hash") or i.get("address")
                    if v:
                        impls.append(v.lower())
            if impls and not info["implementations"]:
                info["implementations"] = sorted(set(impls))
        elif bs.status == 404:
            if info["verified"] is None:
                info.update(verified=False, source="blockscout")
        else:
            ctx.degraded.add("blockscout")
    return info


# ---------------------------------------------------------------- admin classification
def classify_controller(ctx, chain, addr, role, depth, max_depth, add):
    """Classify an admin/owner address. Emits findings through add(); returns an info tree."""
    info = {"address": addr, "role": role, "kind": None}
    code = get_code(ctx, chain, addr)
    if code in ("0x", "0x0", ""):
        info["kind"] = "EOA"
        add("HIGH", "EOA_ADMIN",
            "%s %s is a single EOA: one key controls upgrades/administration (custody such as HSM/MPC is not visible on-chain)"
            % (role, addr), ":" + role, role=role, address=addr)
        return info
    info["bytes"] = (len(code) - 2) // 2
    r = eth_calls(ctx, chain, addr, [SEL_GET_THRESHOLD, SEL_GET_OWNERS, SEL_GET_MIN_DELAY, SEL_DELAY, SEL_OWNER])
    thr, owners = decode_uint(r[0]), decode_address_array(r[1]) if r[1] else None
    if thr and owners:
        info.update(kind="safe", threshold=thr, owner_count=len(owners), owners=sorted(owners))
        if thr == 1:
            add("MEDIUM", "MULTISIG_1_OF_N", "%s %s is a Safe multisig with threshold 1 of %d owners (effectively single-signer)"
                % (role, addr, len(owners)), ":" + role, role=role, address=addr, threshold=thr, owners=sorted(owners))
        else:
            add("INFO", "SAFE_MULTISIG", "%s %s is a Safe multisig, %d-of-%d" % (role, addr, thr, len(owners)),
                ":" + role, role=role, address=addr, threshold=thr, owners=sorted(owners))
        return info
    delay = decode_uint(r[2])
    if delay is None:
        delay = decode_uint(r[3])
    if delay is not None:
        info.update(kind="timelock", delay=delay)
        if delay == 0:
            add("MEDIUM", "ZERO_DELAY_TIMELOCK", "%s %s is a timelock with zero delay (no review window)" % (role, addr),
                ":" + role, role=role, address=addr, delay=0)
        else:
            add("INFO", "TIMELOCK_ADMIN", "%s %s is a timelock with %d s delay" % (role, addr, delay),
                ":" + role, role=role, address=addr, delay=delay)
        return info
    info["kind"] = "contract"
    owner = decode_address(r[4])
    if owner and depth < max_depth:
        info["owner"] = classify_controller(ctx, chain, owner, role + ".owner", depth + 1, max_depth, add)
    elif owner:
        info["owner_address"] = owner
        add("LOW", "ADMIN_CONTRACT_UNKNOWN", "%s %s is an unclassified contract owned by %s (depth limit; use --deep)"
            % (role, addr, owner), ":" + role, role=role, address=addr, owner=owner)
    else:
        add("MEDIUM", "ADMIN_CONTRACT_UNKNOWN",
            "%s %s is a contract that is not a recognised Safe/timelock: verify who controls it" % (role, addr),
            ":" + role, role=role, address=addr)
    return info


def first_in_tree(info, field):
    while info:
        if field in info:
            return info[field]
        info = info.get("owner")
    return None


def describe_controller(info):
    if not info:
        return "none resolved"
    k = info["kind"]
    if k == "EOA":
        d = "%s [EOA]" % info["address"]
    elif k == "safe":
        d = "%s [Safe %d-of-%d]" % (info["address"], info["threshold"], info["owner_count"])
    elif k == "timelock":
        d = "%s [Timelock delay=%ds]" % (info["address"], info["delay"])
    else:
        d = "%s [contract]" % info["address"]
    if info.get("owner"):
        d += " -> owner " + describe_controller(info["owner"])
    return d


# ---------------------------------------------------------------- per-address inspection
def _opcode_flags(code_hex):
    ops = scan_opcodes(strip_metadata(hex_to_bytes(code_hex)))
    return {"selfdestruct": OP_SELFDESTRUCT in ops, "delegatecall": OP_DELEGATECALL in ops}


def inspect_address(ctx, chain, addr, deep=False, all_chains=False, label=None):
    """Returns (contract_dict, findings). Raises RpcError when chain data cannot be read."""
    a = addr.lower()
    findings = []

    def add(sev, code, msg, suffix="", **ev):
        findings.append(bc.Finding(sev, code, msg, ev, key="%s:%s:%s%s" % (chain, a, code, suffix)))

    c = {"chain": chain, "address": a, "label": label, "bytecode_bytes": 0, "code_hash": None, "proxy": None,
         "implementation": None, "admin": None, "verification": None, "impl_verification": None, "opcodes": {}}
    code = get_code(ctx, chain, a)
    n = (len(code) - 2) // 2
    c["bytecode_bytes"] = n
    if n == 0:
        add("INFO" if all_chains else "HIGH", "EOA_OR_EMPTY",
            "no contract code at %s on %s (EOA, self-destructed or wrong chain)" % (a, chain))
        c["snapshot"] = None
        return c, findings
    c["code_hash"] = "0x" + keccak256(hex_to_bytes(code)).hex()

    # --- proxy detection
    words = dict(zip([s[0] for s in SLOTS], rpc_batch(ctx, chain, [("eth_getStorageAt", [a, s, "latest"]) for _, s in SLOTS])))
    ptype, impl, beacon = None, None, None
    ci = clone_impl(code)
    if ci:
        ptype, impl = "EIP-1167 minimal proxy", ci
    elif word_addr(words["impl1967"]):
        ptype, impl = "EIP-1967", word_addr(words["impl1967"])
    elif word_addr(words["beacon"]):
        ptype, beacon = "EIP-1967 beacon", word_addr(words["beacon"])
        impl = decode_address(eth_calls(ctx, chain, beacon, [SEL_IMPLEMENTATION])[0])
        if not impl:
            add("MEDIUM", "BEACON_IMPL_UNRESOLVED", "beacon %s did not return an implementation()" % beacon, beacon=beacon)
    elif word_addr(words["uups1822"]):
        ptype, impl = "EIP-1822 proxiable", word_addr(words["uups1822"])
    elif word_addr(words["zos_impl"]):
        ptype, impl = "ZeppelinOS legacy", word_addr(words["zos_impl"])
    admin_slot = word_addr(words["admin1967"]) or word_addr(words["zos_admin"])

    ver = lookup_verification(ctx, chain, a)
    c["verification"] = ver
    if not impl and ver["implementations"]:
        impl = ver["implementations"][0]
        ptype = ptype or "%s (per %s)" % (ver["proxy_type"] or "proxy", ver["source"])
    if beacon:
        c["beacon"] = beacon
    is_proxy = ptype is not None
    c["proxy"] = {"type": ptype, "beacon": beacon} if is_proxy else None
    c["implementation"] = impl

    # --- implementation
    impl_code, impl_ver = None, None
    if impl:
        impl_code = get_code(ctx, chain, impl)
        c["impl_bytes"] = (len(impl_code) - 2) // 2
        if c["impl_bytes"] == 0:
            add("HIGH", "IMPL_NO_CODE", "implementation %s has no code (proxy is bricked or points at a self-destructed contract)" % impl, implementation=impl)
        else:
            c["impl_code_hash"] = "0x" + keccak256(hex_to_bytes(impl_code)).hex()
        impl_ver = lookup_verification(ctx, chain, impl)
        c["impl_verification"] = impl_ver

    # --- admin / owner
    max_depth = 3 if deep else 1
    controller, ctrl_info = None, None
    if admin_slot:
        controller = admin_slot
    else:
        owner_addr = decode_address(eth_calls(ctx, chain, a, [SEL_OWNER])[0])
        if not owner_addr and impl:
            owner_addr = decode_address(eth_calls(ctx, chain, impl, [SEL_OWNER])[0])
        controller = owner_addr
    role = "proxy_admin" if admin_slot else "owner"
    if controller:
        ctrl_info = classify_controller(ctx, chain, controller, role, 0, max_depth, add)
    elif is_proxy:
        add("LOW", "ADMIN_UNRESOLVED", "no admin slot or owner() found; upgrade authority may live inside the implementation (UUPS-style)")
    if deep and impl and admin_slot:
        io = decode_address(eth_calls(ctx, chain, a, [SEL_OWNER])[0]) or decode_address(eth_calls(ctx, chain, impl, [SEL_OWNER])[0])
        if io and io != controller and int(io, 16) > 0xffff and not io.endswith("dead"):
            c["impl_owner"] = classify_controller(ctx, chain, io, "impl_owner", 0, max_depth, add)
    c["admin"] = ctrl_info

    # --- opcode scan
    c["opcodes"]["target"] = fl = _opcode_flags(code)
    if fl["selfdestruct"]:
        add("HIGH", "CONTRACT_HAS_SELFDESTRUCT", "SELFDESTRUCT opcode present in %s code (heuristic; EIP-6780 limits effect post-Cancun)"
            % ("proxy" if is_proxy else "contract"), where="target")
    if fl["delegatecall"]:
        if is_proxy:
            add("INFO", "PROXY_DELEGATECALL", "DELEGATECALL in proxy code (expected for a proxy)")
        else:
            add("MEDIUM", "IMPL_HAS_DELEGATECALL", "DELEGATECALL in non-proxy contract code: external code may run with this contract's storage", where="target")
    if impl_code and c.get("impl_bytes"):
        c["opcodes"]["impl"] = ifl = _opcode_flags(impl_code)
        if ifl["selfdestruct"]:
            add("CRITICAL", "IMPL_HAS_SELFDESTRUCT", "implementation %s contains SELFDESTRUCT: a proxy delegating to it can be destroyed" % impl, implementation=impl)
        if ifl["delegatecall"]:
            add("MEDIUM", "IMPL_HAS_DELEGATECALL", "implementation %s contains DELEGATECALL (heuristic)" % impl, ":impl", implementation=impl)

    # --- verification findings
    if ver["verified"] is False:
        add("HIGH", "UNVERIFIED_CONTRACT", "%s is not source-verified (Sourcify%s)" % (a, "/Blockscout" if chain == "eth" else ""))
    if impl_ver is not None and impl_ver["verified"] is False and c.get("impl_bytes"):
        add("HIGH", "UNVERIFIED_IMPLEMENTATION", "implementation %s is not source-verified" % impl, implementation=impl)

    c["snapshot"] = {
        "implementation": impl,
        "admin": controller,
        "admin_owner": (ctrl_info or {}).get("owner", {}).get("address") if ctrl_info else None,
        "code_hash": c["code_hash"],
        "impl_code_hash": c.get("impl_code_hash"),
        "verified": ver["verified"],
        "impl_verified": impl_ver["verified"] if impl_ver else None,
        "safe_threshold": first_in_tree(ctrl_info, "threshold"),
        "timelock_delay": first_in_tree(ctrl_info, "delay"),
    }
    return c, findings


# ---------------------------------------------------------------- delta
def compute_events(prev, snap, chain, addr):
    ev = []

    def add(sev, code, msg, **evid):
        ev.append(bc.Finding(sev, code, msg, evid, key="%s:%s:%s" % (chain, addr, code)))

    if prev.get("implementation") != snap["implementation"]:
        add("CRITICAL", "IMPLEMENTATION_CHANGED", "implementation changed %s -> %s" % (prev.get("implementation"), snap["implementation"]),
            old=prev.get("implementation"), new=snap["implementation"])
    if prev.get("admin") != snap["admin"] or prev.get("admin_owner") != snap["admin_owner"]:
        add("CRITICAL", "ADMIN_CHANGED", "admin changed %s (owner %s) -> %s (owner %s)"
            % (prev.get("admin"), prev.get("admin_owner"), snap["admin"], snap["admin_owner"]),
            old=prev.get("admin"), new=snap["admin"], old_owner=prev.get("admin_owner"), new_owner=snap["admin_owner"])
    changed = prev.get("code_hash") != snap["code_hash"]
    if prev.get("implementation") == snap["implementation"] and prev.get("impl_code_hash") != snap["impl_code_hash"]:
        changed = True
    if changed:
        add("CRITICAL", "BYTECODE_CHANGED", "runtime bytecode changed at the same address",
            old=prev.get("code_hash"), new=snap["code_hash"], old_impl=prev.get("impl_code_hash"), new_impl=snap["impl_code_hash"])
    for k in ("verified", "impl_verified"):
        if prev.get(k) is True and snap[k] is False:
            add("HIGH", "VERIFICATION_REGRESSED", "%s went from true to false" % k, field=k)
    for k in ("safe_threshold", "timelock_delay"):
        if prev.get(k) != snap[k]:
            add("MEDIUM", "GOVERNANCE_CHANGED", "%s changed %s -> %s" % (k, prev.get(k), snap[k]), field=k, old=prev.get(k), new=snap[k])
    return ev


# ---------------------------------------------------------------- rendering
_COLORS = {"CRITICAL": "\033[1;31m", "HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[36m", "INFO": "\033[2m"}


def fmt_finding(f, color=False):
    sev = "%-8s" % f.sev
    if color:
        sev = _COLORS[f.sev] + sev + "\033[0m"
    return "  [%s] %s: %s" % (sev, f.code, f.msg)


def _yn(v):
    return "unknown" if v is None else ("yes" if v else "NO")


def render_contract(c):
    lines = ["target    %s:%s%s" % (c["chain"], c["address"], "  (%s)" % c["label"] if c.get("label") else "")]
    if c.get("error"):
        return lines + ["error     %s" % c["error"]]
    lines.append("bytecode  %d bytes%s" % (c["bytecode_bytes"], "  keccak=" + c["code_hash"] if c["code_hash"] else ""))
    if c["bytecode_bytes"] == 0:
        return lines
    p = c["proxy"]
    lines.append("proxy     %s" % (p["type"] + (" (beacon %s)" % p["beacon"] if p["beacon"] else "") if p else "none detected (slots 1967/beacon/1822/zOS, EIP-1167)"))
    if c["implementation"]:
        iv = c["impl_verification"]
        lines.append("impl      %s (%d bytes, verified=%s)" % (c["implementation"], c.get("impl_bytes", 0), _yn(iv["verified"] if iv else None)))
    else:
        lines.append("impl      -")
    lines.append("admin     %s" % describe_controller(c["admin"]))
    if c.get("impl_owner"):
        lines.append("impl.own  %s" % describe_controller(c["impl_owner"]))
    v = c["verification"]
    lines.append("sourcify  %s%s" % ({"verified": "verified (%s)" % v["match"], "unverified": "NOT VERIFIED", "degraded": "DEGRADED (lookup failed)"}[v["sourcify"]],
                                     "  name=%s" % v["name"] if v.get("name") else "") + ("  [verified via %s]" % v["source"] if v["source"] == "blockscout" and v["verified"] else ""))
    parts = []
    for k in ("target", "impl"):
        o = c["opcodes"].get(k)
        if o:
            parts.append("%s: SELFDESTRUCT=%s DELEGATECALL=%s" % (k, "yes" if o["selfdestruct"] else "no", "yes" if o["delegatecall"] else "no"))
    lines.append("opcodes   %s" % (" | ".join(parts) or "-"))
    return lines


def contract_json(c):
    out = {k: v for k, v in c.items()}
    return json.loads(json.dumps(out, sort_keys=True))


# ---------------------------------------------------------------- CLI
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser():
    p = _Parser(prog="evm_contract_inspector.py", description="Read-only EVM contract & proxy upgradeability inspector")
    p.add_argument("addresses", nargs="+", metavar="ADDRESS")
    p.add_argument("--chain", choices=sorted(CHAINS))
    p.add_argument("--all-chains", action="store_true")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--state", metavar="PATH")
    p.add_argument("--delta", action="store_true")
    p.add_argument("--watch-label", metavar="NAME")
    p.add_argument("--fail-on", choices=["medium", "high", "critical"], default="medium")
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument("--no-color", action="store_true")
    return p


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
        addrs, seen = [], set()
        for a in args.addresses:
            if not ADDR_RE.match(a):
                raise UsageError("invalid address %r (need 0x + 40 hex chars)" % a)
            if a.lower() not in seen:
                seen.add(a.lower())
                addrs.append(a)
    except UsageError as e:
        print("error: %s" % e, file=sys.stderr)
        return bc.EXIT_USAGE
    except SystemExit as e:  # --help
        return int(e.code or 0)

    chains = sorted(CHAINS) if args.all_chains else [args.chain]
    ctx = Ctx(timeout=args.timeout)
    store = bc.StateStore(args.state) if args.state else None
    findings, contracts, events = [], [], []
    standing_by_key, prior_standing, baseline = {}, {}, {}
    for a in addrs:
        if not checksum_ok(a):
            findings.append(bc.Finding("LOW", "NON_EIP55_CHECKSUM", "%s is mixed-case but fails the EIP-55 checksum (expected %s)" % (a, to_checksum(a)),
                                       {"address": a, "expected": to_checksum(a)}, key="addr:%s:NON_EIP55_CHECKSUM" % a.lower()))
        for ch in chains:
            sk = "%s:%s" % (ch, a.lower())
            try:
                c, fl = inspect_address(ctx, ch, a, deep=args.deep, all_chains=args.all_chains, label=args.watch_label)
            except RpcError as e:
                ctx.degraded.add("rpc:" + ch)
                contracts.append({"chain": ch, "address": a.lower(), "label": args.watch_label, "error": str(e)})
                continue
            contracts.append(c)
            findings.extend(fl)
            snap = c.get("snapshot")
            if store and snap:
                prev = store.get(sk)
                standing_by_key[sk] = [f.to_dict() for f in fl]
                if args.delta:
                    if prev is None:
                        baseline[sk] = True
                    else:
                        events.extend(compute_events(prev, snap, ch, a.lower()))
                        prior_standing[sk] = prev.get("findings", [])
                state = dict(snap)
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
    now = now or bc.utc_now()
    scored = bc.sort_findings(all_f)

    if args.json:
        payload = {
            "tool": TOOL,
            "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope_note": SCOPE_NOTE,
            "degraded_sources": degraded,
            "contracts": [contract_json(c) for c in sorted(contracts, key=lambda c: (c["chain"], c["address"]))],
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
    for c in sorted(contracts, key=lambda c: (c["chain"], c["address"])):
        lines += render_contract(c) + [""]
    if degraded:
        lines += ["DEGRADED  data sources failed: %s (result may be incomplete)" % ", ".join(degraded), ""]
    lines.append("findings")
    lines += [fmt_finding(f, color) for f in scored if f not in events] or ["  (no findings)"]
    if delta is not None:
        lines += ["", "delta"]
        if delta["baseline"]:
            lines.append("  baseline run: no prior state for these targets; recorded %d finding(s)" % len(delta["new"]))
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
