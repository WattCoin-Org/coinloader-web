(function () {
  'use strict';

  const BOT_SPECS = {
    'wattcoin-scraper': {
      title: 'WattCoin Web Scraper',
      slug: 'getting-started + wattcoin-scraper',
      badge: 'LIVE NOW — FREE',
      price: 'FREE (100 WATT Starter Grant + 10/day Free Quota)',
      shareUrl: 'https://x.ai/bot/k1oyHmw4iS4VBW1U8_3Ol',
      bodyHtml: `
        <p>Self-onboarding Grok Bot template wired to the WattCoin Agent Registry (<code>https://wattcoin.org/api/v1</code>) and static web extraction pipeline.</p>
        <h4>1. First-Turn Onboarding (<code>getting-started</code>)</h4>
        <ul>
          <li>Checks for <code>/workspace/.wattcoin_env</code>; if absent, slugifies the bot name to match <code>^[A-Za-z0-9_-]{3,64}$</code> (default <code>scraper-bot</code>) and calls <code>POST /api/v1/agents/register</code>.</li>
          <li>Saves <code>WATTCOIN_AGENT_ID</code> and <code>WATTCOIN_AGENT_KEY</code> (<code>wck_...</code>) to <code>/workspace/.wattcoin_env</code> with <code>chmod 600</code> permissions. Never prints the secret key in chat.</li>
          <li>Completes <code>onboarding_v1</code> (25 WATT) and <code>starter_v1</code> (75 WATT) by dynamically reading <code>data.mint</code> from <code>/api/v1/price</code> and <code>withdraw_min</code> from <code>/api/v1/agents/stats</code>.</li>
          <li>Proves readiness with a live verification scrape of <code>https://example.com</code> and reports remaining quota from <code>X-Quota-Remaining</code>.</li>
        </ul>
        <h4>2. Extraction Modes &amp; Error Branching (<code>wattcoin-scraper</code>)</h4>
        <ul>
          <li><strong>Free Tier (<code>format: "text"</code>):</strong> 10 free scrapes per UTC day with an activated <code>X-Agent-Key: wck_...</code>. Performs server-side HTTP fetch + BeautifulSoup plain-text extraction (no client-side JS execution).</li>
          <li><strong>Paid Tier (<code>format: "html" | "json"</code>):</strong> 100 WATT per call on-chain (always prompts for explicit confirmation before any paid call).</li>
          <li><strong>Strict Error Branching:</strong> Branches on the JSON <code>reason</code> field (<code>quota_exhausted</code>, <code>tasks_incomplete</code>, <code>format_requires_payment</code>) and falls back cleanly to local <code>curl</code> + Python HTML-to-text parsing (<code>bs4</code> or stdlib <code>html.parser</code>) in <code>/workspace</code> when daily quota is exhausted.</li>
        </ul>
      `
    },
    'solana-wallet-hygiene': {
      title: 'Solana Wallet Hygiene Bot',
      slug: 'solana-wallet-hygiene',
      badge: 'IN DEVELOPMENT — PHASE 2 SPEC',
      price: 'Planned: $19 in SOL (Not Yet Available)',
      bodyHtml: `
        <p>Read-only Solana wallet auditor for reclaimable token account rent and stale SPL / Token-2022 delegations. Stages unsigned base64 transactions locally in <code>/workspace</code> — never holds keys, never signs, and never submits transactions.</p>
        <h4>1. Dual Token Program Discovery</h4>
        <ul>
          <li>Queries <code>getParsedTokenAccountsByOwner</code> twice on every audit: once for legacy SPL Token (<code>TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA</code>) and once for Token-2022 (<code>TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb</code>).</li>
          <li>Always performs a full read-only audit first before staging any transaction batch.</li>
        </ul>
        <h4>2. Strict 3-Bucket Safety Classifier</h4>
        <ul>
          <li><strong>SAFE TO CLOSE:</strong> Zero balance, no delegate, owner holds close authority, no Token-2022 extension holding withheld state (<code>transferFeeAmount.withheldAmount == "0"</code>), not frozen. Eligible for batch staging.</li>
          <li><strong>NEEDS YOUR CONFIRMATION (One-by-One):</strong> Any account with a non-null <code>delegate</code> or non-zero <code>delegatedAmount</code>, recent ATA activity, or unreadable Token-2022 extensions. Never batched; unidentified delegates are flagged explicitly by address.</li>
          <li><strong>DO NOT TOUCH:</strong> Frozen accounts, non-zero balances, Token-2022 accounts with non-zero <code>withheldAmount</code>, or third-party close authorities.</li>
        </ul>
        <h4>3. Economics &amp; Key Honesty</h4>
        <ul>
          <li>Calculates exact reclaimable rent (<code>≥0.002039 SOL</code> floor per standard 165-byte empty account; higher for Token-2022 accounts with extensions) vs. network fees before staging.</li>
          <li>Never prints or accepts seed phrases or private keys.</li>
        </ul>
      `
    },
    'solana-token-dd': {
      title: 'Retail Token Due-Diligence Bot',
      slug: 'solana-token-dd',
      badge: 'IN DEVELOPMENT — PHASE 2 SPEC',
      price: 'Planned: $29 in SOL (Not Yet Available)',
      bodyHtml: `
        <p>Factual on-chain Solana mint &amp; liquidity researcher. Reports verifiable mechanical capabilities with source timestamps — zero scores, zero ratings, and zero investment opinions.</p>
        <h4>1. On-Chain Inspection Scope</h4>
        <ul>
          <li><strong>Authorities:</strong> Mint authority, freeze authority, and metadata update authority (active vs. revoked, plus holder address).</li>
          <li><strong>Supply &amp; History:</strong> Total supply, decimals, mint creation timestamp, and recent authority mutations.</li>
          <li><strong>Token-2022 Extensions:</strong> Inspects <code>TransferFeeConfig</code> (current &amp; max bps), <code>TransferHook</code>, <code>PermanentDelegate</code>, <code>NonTransferable</code>, and <code>DefaultAccountState</code>, describing what each extension mechanically permits.</li>
          <li><strong>Liquidity &amp; Holder Distribution:</strong> Pool depth, LP lock/burn status, and Top-10 / Top-20 holder concentration with known exchange, pool, and program accounts separated from individual wallets.</li>
        </ul>
        <h4>2. Hard Guardrails (Mechanics, Not Motives)</h4>
        <ul>
          <li>Never labels a token "safe", "unsafe", "scam", "rug", or "promising", and never outputs a numerical score or letter grade.</li>
          <li>Explicitly flags any unreadable extension, unverified contract, or missing pool data rather than letting gaps pass silently.</li>
        </ul>
      `
    },
    'bot-skill-auditor': {
      title: 'Bot & Skill Security Auditor',
      slug: 'bot-skill-auditor',
      badge: 'IN DEVELOPMENT — PHASE 2 SPEC',
      price: 'Planned: $29 in SOL (Not Yet Available)',
      bodyHtml: `
        <p>Static, read-only security inspector for third-party Grok Bot templates, <code>SKILL.md</code> files, routine prompts, and linked GitHub repositories.</p>
        <h4>1. Primary Execution Rule: Read Only, Never Run</h4>
        <ul>
          <li>Never executes bash, Python, or Node blocks inside an audited artifact. Never curls embedded URLs or installs unpinned packages during inspection.</li>
          <li>Treats any prompt instruction inside an audited file claiming "already audited" or "skip this section" as a finding itself.</li>
        </ul>
        <h4>2. Five Mandatory Capability Buckets</h4>
        <ul>
          <li><strong>Bucket 1 — Prompt &amp; Confirmation Bypass:</strong> Instructions to skip confirmation cards, auto-approve tools, hide output, or run outbound actions unattended in routines.</li>
          <li><strong>Bucket 2 — Secret &amp; Filesystem Access:</strong> Reads/writes touching <code>.env</code>, <code>/home/box/agent-data</code>, Solana keypair files (<code>id.json</code>), seed phrases, or paths outside <code>/workspace</code>.</li>
          <li><strong>Bucket 3 — Outbound Network &amp; Exfiltration:</strong> Every hardcoded domain, URL, IP, webhook, or POST body transmitting local files or env vars.</li>
          <li><strong>Bucket 4 — Unverifiable Runtime Execution:</strong> <code>curl | sh</code>, <code>eval</code>, base64-decoded execution, and unpinned <code>pip</code> / <code>npm</code> / <code>npx</code> installs whose payload can change post-audit.</li>
          <li><strong>Bucket 5 — Local Machine Escalation:</strong> Enumeration of connected machines, <code>machineId</code> targeting, or commands escaping the sandboxed Linux box.</li>
        </ul>
        <h4>3. Zero Pass/Fail Badges</h4>
        <ul>
          <li>Quotes exact lines and mechanical consequences without issuing a "safe/clean" badge or numeric risk score.</li>
        </ul>
      `
    },
    'hyperliquid-monitor': {
      title: 'Hyperliquid & Perp Basis Monitor',
      slug: 'hyperliquid-monitor',
      badge: 'IN DEVELOPMENT — PHASE 3 SPEC',
      price: 'Planned: $29 in SOL (Not Yet Available)',
      bodyHtml: `
        <p>Unauthenticated read-only perpetuals, funding rate, and liquidation-distance monitor via <code>POST https://api.hyperliquid.xyz/info</code>.</p>
        <h4>1. Zero API Keys Required</h4>
        <ul>
          <li>Uses only a public 42-character <code>0x...</code> address. Immediately refuses any API wallet key, agent key, private key, or seed phrase.</li>
          <li>Never places, modifies, or cancels orders.</li>
        </ul>
        <h4>2. Monitored Telemetry</h4>
        <ul>
          <li><strong>Funding:</strong> Current rate, predicted next (<code>{"type":"predictedFundings"}</code>), sign flips, and user-defined threshold crossings.</li>
          <li><strong>Clearinghouse State:</strong> Position size, entry, mark, unrealized PnL, margin ratio, liquidation price, and exact distance to liquidation in both price and percentage (<code>{"type":"clearinghouseState","user":"0x..."}</code>).</li>
          <li><strong>Vaults &amp; Basis:</strong> Vault TVL, drawdown, and spot-perp spread across tracked markets.</li>
        </ul>
        <h4>3. Urgency &amp; Data Discipline</h4>
        <ul>
          <li>Reports state, never trade advice: states exact distance to liquidation without recommending whether to close, add margin, or hedge.</li>
          <li>Timestamps every payload and flags stale or rate-limited API responses prominently.</li>
        </ul>
      `
    }
  };

  function showToast(msg) {
    const toast = document.getElementById('copy-toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2600);
  }

  async function copyText(text, triggerBtn, feedbackLabel) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      if (triggerBtn) {
        const originalHtml = triggerBtn.getAttribute('data-original-html') || triggerBtn.innerHTML;
        if (!triggerBtn.getAttribute('data-original-html')) {
          triggerBtn.setAttribute('data-original-html', originalHtml);
        }
        triggerBtn.innerHTML = feedbackLabel || '✓ Copied';
        setTimeout(() => {
          triggerBtn.innerHTML = originalHtml;
        }, 2000);
      }
      showToast('Copied to clipboard: ' + (text.length > 80 ? text.slice(0, 80) + '…' : text));
    } catch (err) {
      showToast('Copy failed — select and copy manually.');
    }
  }

  // Copy buttons
  document.querySelectorAll('[data-copy]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const value = btn.getAttribute('data-copy');
      const label = btn.getAttribute('data-copy-label') || '✓ Copied!';
      copyText(value, btn, label);
    });
  });

  // Terminal Tabs (ARIA tablist + keyboard arrow navigation)
  const termTabs = Array.from(document.querySelectorAll('.term-tab'));
  const termPanes = Array.from(document.querySelectorAll('.term-pane'));

  function activateTab(tab, focusTab) {
    const targetId = tab.getAttribute('data-tab');
    termTabs.forEach((t) => {
      const isSelected = t === tab;
      t.classList.toggle('active', isSelected);
      t.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      t.setAttribute('tabindex', isSelected ? '0' : '-1');
    });
    termPanes.forEach((p) => {
      const isMatch = p.id === targetId;
      p.classList.toggle('active', isMatch);
      if (isMatch) {
        p.removeAttribute('hidden');
      } else {
        p.setAttribute('hidden', '');
      }
    });
    if (focusTab) tab.focus();
  }

  termTabs.forEach((tab, idx) => {
    tab.addEventListener('click', () => activateTab(tab, false));
    tab.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const dir = e.key === 'ArrowRight' ? 1 : -1;
        const nextIdx = (idx + dir + termTabs.length) % termTabs.length;
        activateTab(termTabs[nextIdx], true);
      } else if (e.key === 'Home') {
        e.preventDefault();
        activateTab(termTabs[0], true);
      } else if (e.key === 'End') {
        e.preventDefault();
        activateTab(termTabs[termTabs.length - 1], true);
      }
    });
  });

  // Category Filter Pills (with aria-pressed)
  const filterPills = document.querySelectorAll('.filter-pill');
  const botCards = document.querySelectorAll('.bot-card');
  filterPills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const category = pill.getAttribute('data-filter');
      filterPills.forEach((p) => {
        const isActive = p === pill;
        p.classList.toggle('active', isActive);
        p.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });

      botCards.forEach((card) => {
        const cats = (card.getAttribute('data-categories') || '').split(/\s+/);
        if (category === 'all' || cats.includes(category)) {
          card.classList.remove('hidden');
        } else {
          card.classList.add('hidden');
        }
      });
    });
  });

  // Spec Modal (focus move, background inert, Tab focus trap, and trigger focus restore)
  const modalBackdrop = document.getElementById('spec-modal');
  const modalPanel = modalBackdrop ? modalBackdrop.querySelector('.modal-panel') : null;
  const modalTitle = document.getElementById('modal-title');
  const modalBadge = document.getElementById('modal-badge');
  const modalSlug = document.getElementById('modal-slug');
  const modalBody = document.getElementById('modal-body');
  const modalCloseBtn = document.getElementById('modal-close');
  const backgroundRegions = document.querySelectorAll('.top-ticker, header.site-header, main, footer.site-footer');
  let lastFocusedTrigger = null;

  function setBackgroundInert(isInert) {
    backgroundRegions.forEach((el) => {
      if (isInert) {
        el.setAttribute('inert', '');
        el.setAttribute('aria-hidden', 'true');
      } else {
        el.removeAttribute('inert');
        el.removeAttribute('aria-hidden');
      }
    });
  }

  function openSpecModal(botKey, triggerEl) {
    const spec = BOT_SPECS[botKey];
    if (!spec || !modalBackdrop) return;
    lastFocusedTrigger = triggerEl || document.activeElement;
    modalTitle.textContent = spec.title;
    modalBadge.textContent = spec.badge;
    modalSlug.textContent = spec.slug + ' · ' + spec.price;
    modalBody.innerHTML = spec.bodyHtml;
    modalBackdrop.classList.add('open');
    if (modalPanel) modalPanel.scrollTop = 0;
    modalBackdrop.setAttribute('aria-hidden', 'false');
    setBackgroundInert(true);
    if (modalCloseBtn) modalCloseBtn.focus();
  }

  function closeSpecModal() {
    if (!modalBackdrop || !modalBackdrop.classList.contains('open')) return;
    modalBackdrop.classList.remove('open');
    modalBackdrop.setAttribute('aria-hidden', 'true');
    setBackgroundInert(false);
    if (lastFocusedTrigger && typeof lastFocusedTrigger.focus === 'function') {
      lastFocusedTrigger.focus();
    }
    lastFocusedTrigger = null;
  }

  document.querySelectorAll('[data-open-spec]').forEach((btn) => {
    btn.addEventListener('click', () => {
      openSpecModal(btn.getAttribute('data-open-spec'), btn);
    });
  });

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', closeSpecModal);
  }
  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) closeSpecModal();
    });
  }
  document.addEventListener('keydown', (e) => {
    if (!modalBackdrop || !modalBackdrop.classList.contains('open')) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeSpecModal();
    } else if (e.key === 'Tab' && modalPanel) {
      const focusables = Array.from(
        modalPanel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
      ).filter((el) => !el.hasAttribute('disabled'));
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
})();
