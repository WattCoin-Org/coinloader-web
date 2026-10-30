# EVM Smart Contract & Proxy Inspector ($29 SOL) | CoinLoader

> Read-only EVM proxy inspector for Grok Bot ($29 SOL). Resolves EIP-1967/UUPS proxy admins on Ethereum, Base & Arbitrum, flags EOA admins and checks Sourcify.

- SKU: `evm-contract-inspector`
- Price: $29 USD (one-time)
- Page: https://coinloader.com/bots/evm-contract-inspector.html
- Markdown: https://coinloader.com/bots/evm-contract-inspector.md

## When to use

Use when an agent needs proxy upgradeability, admin and source-verification facts for an EVM contract.

Inputs: a contract address on Ethereum, Base or Arbitrum

Outputs: implementation/admin/beacon slots, Safe/Timelock classification, opcode flags

## How an agent buys

- Price: $29 USD (one-time)
- Card (default): `POST https://www.wattcoin.org/api/v1/agents/license/stripe-checkout` with body `{"sku": "evm-contract-inspector", "storefront": "coinloader"}` returns a `checkout_url` (hosted page; a human completes payment). After payment: `GET https://www.wattcoin.org/api/v1/agents/license/stripe-session/{session_id}` returns the license code.
- SOL: `POST https://www.wattcoin.org/api/v1/agents/license/quote` then `POST https://www.wattcoin.org/api/v1/agents/license/purchase`. Each quote creates a 15-minute order. Add "dry_run": true to the POST quote body (or the stripe-checkout body) to see the price without creating an order.

Machine-readable catalog (all SKUs, prices, inputs/outputs, checkout): https://coinloader.com/catalog.json
Plain-text catalog: https://coinloader.com/llms.txt

---

# EVM Smart Contract & Proxy Inspector — Know who can upgrade the contract before you deposit.

Inspect any Ethereum, Base, or Arbitrum contract before you deposit or integrate: resolve EIP-1967, EIP-1822 UUPS, EIP-1167 clone, and ZeppelinOS legacy proxy storage slots in one batch, trace who actually controls upgrades (Safe M/N threshold & owners, TimelockController delay, ProxyAdmin, or a single EOA), check Sourcify v2 source verification, and scan runtime bytecode for SELFDESTRUCT and DELEGATECALL.

 SKU: `evm-contract-inspector` · Skills: `evm-contract-inspector-setup + evm-contract-inspector` · Tested: 779 lines stdlib Python, 55 unit tests

## What It Does

- Batched JSON-RPC slot resolution across **Ethereum (`eth`, 1)**, **Base (`base`, 8453)**, and **Arbitrum One (`arb`, 42161)**: EIP-1967 (`implementation`, `admin`, `beacon`), EIP-1822 UUPS, ZeppelinOS legacy (`0x7050c9e0...` / `0x10d6a54a...`), and EIP-1167 minimal proxy clones.
- Governance & controller chain probing (`--deep`, `--max-depth 2`): classifies Safe multisigs (`getThreshold()` / `getOwners()`), Timelocks (`getMinDelay()` / `delay()`), ProxyAdmin contracts, or single-key EOAs (`EOA_ADMIN`).
- Source verification via **Sourcify v2** (`fields=abi,proxyResolution,compilation`) with Blockscout v2 fallback, plus CBOR-stripped opcode scanning that skips `PUSH1..PUSH32` immediate bytes before flagging `SELFDESTRUCT` (`0xff`) or unexpected `DELEGATECALL` (`0xf4`).
- Stateful delta monitor (`--state PATH --delta`): emits `EVENT` / `NEW` / `CHANGED` / `RESOLVED` diffs whenever an implementation address, proxy admin, Safe threshold, or timelock delay changes. 100% Python stdlib, 55 unit tests.

## What It Does Not Do

- Strictly read-only: never asks for private keys or seed phrases, and never builds, signs, or broadcasts transactions.
- Never labels a contract 'safe', 'audited', or 'rug-proof'; an EOA admin is not proof of weak custody (HSM/MPC keys look identical on-chain).
- Opcode scans are byte-level heuristics, not formal verification or a substitute for a source audit.

## Licensing & Setup

One-time license, up to 3 workspace-reset rebinds. On Turn 1 the `evm-contract-inspector-setup` skill verifies your agent key, binds your `wcl_...` code through the read-only license helper, and confirms the bot files are installed. The license code is never printed in chat.

**One `wcl_...` key, two runtimes.** Your license key works inside Grok Bot *and* from any local terminal or IDE agent (Cursor, Claude Code, Windsurf, CI/CD) via the standalone single-file Python 3 CLI (standalone `/runtime/<script>.py` CLI) — Python 3.10+ standard library only, zero `pip install` dependencies, with `--json` / `--markdown` output.

## Frequently Asked Questions — EVM Smart Contract & Proxy Inspector

**How do I check if an Ethereum, Base, or Arbitrum contract is an upgradeable proxy with an EOA admin?**

Pass the contract address and chain (eth, base, or arb) to the inspector. It batches JSON-RPC reads of the EIP-1967, EIP-1822 UUPS, EIP-1167 and ZeppelinOS storage slots, then with --deep follows the admin or owner chain up to --max-depth 2. If the upgrade controller is a plain externally owned account it reports EOA_ADMIN; Safe multisigs (threshold and owners), TimelockControllers (minimum delay) and ProxyAdmin contracts are classified separately. An EOA admin is a fact about the chain, not proof of weak custody, because HSM or MPC keys look identical on-chain.

**How does the inspector check EIP-1967, Beacon, and ZeppelinOS proxy slots and Sourcify v2 source verification?**

It reads the EIP-1967 implementation, admin and beacon slots, the EIP-1822 proxiable slot, the legacy ZeppelinOS slots (0x7050c9e0... and 0x10d6a54a...) and EIP-1167 minimal-proxy bytecode in one batched call. Source verification comes from Sourcify v2 (fields=abi,proxyResolution,compilation) with a Blockscout v2 fallback, and runtime bytecode is scanned with CBOR metadata stripped and PUSH immediates skipped before flagging SELFDESTRUCT (0xff) or unexpected DELEGATECALL (0xf4).

**Do I need an Etherscan API key or wallet connection to inspect an EVM smart contract?**

No. The inspector is read-only and needs no wallet connection and no Etherscan key. It talks to public JSON-RPC endpoints for Ethereum, Base and Arbitrum One plus the public Sourcify and Blockscout APIs. Your only credential is the wcl_... license code, which is bound once through the read-only license helper and never printed in chat.

**What safety and refusal boundaries does the EVM Smart Contract & Proxy Inspector enforce?**

It is strictly read-only: it never asks for private keys or seed phrases and never builds, signs or broadcasts a transaction. It never labels a contract 'safe', 'audited' or 'rug-proof', and its opcode scans are byte-level heuristics, not formal verification or a substitute for a source audit. Output is factual and is not financial or security-certification advice.
