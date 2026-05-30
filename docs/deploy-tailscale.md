# Deploying agentic-translator on a Tailscale-fronted local server

This guide describes how to run **agentic-translator** on a single always-on
machine inside your office or home, and expose it to a small team of remote
translators via **Tailscale** — without opening any firewall ports, without
publishing the service to the public internet, and without keeping any
confidential client data on a cloud provider's hardware.

This is the recommended deployment for small Language Service Provider (LSP)
teams (≤20 translators) where confidentiality of glossaries / TMs / source
documents is a competitive requirement.

## At a glance

```
[Translator's laptop, anywhere]
         │ (WireGuard, encrypted)
         ▼
[Office Mac mini / Linux box on Tailnet]
  ├── streamlit run app.py  (localhost:8501)
  ├── models/   on local disk
  └── engines/  on local disk
```

- Translators reach the server at e.g. `http://translab-server.<your-tailnet>.ts.net:8501`
- All traffic is encrypted by Tailscale (WireGuard)
- The server is invisible from the public internet — only Tailnet-joined devices reach it
- All client data stays on the office machine

## Hardware requirements

| Role | Minimum | Recommended |
|---|---|---|
| Server | Any machine that can run Python 3.11 + Streamlit (8 GB RAM) | Mac mini M4 (16 GB / 256 GB) — silent, low-power, very reliable |
| Translator clients | Any modern browser + Tailscale client | — |

The server runs unattended 24/7. Avoid laptops that sleep when the lid closes.

## Prerequisites

- **Tailscale account** for the company (recommend **Tailscale Starter** or **Business** plan — links Google / Microsoft SSO, supports SSO-based ACLs, includes audit log). Free / Personal plans are not appropriate for company use per their terms.
- **GitHub access** to:
  - `chuckmy/agentic-translator` (this repo, public)
  - `<your-org>/agentic-models` (your private models repo) — see [GitHub model repo guidance](../README.md#models-repo) (TBA)
- **Anthropic or OpenAI API key** with a company billing account.

## Part 1 — Server setup (one-time, ~30 minutes)

The following commands assume **macOS** on the server. For Linux, swap
`brew` → `apt`, `launchd` → `systemd`. The shape of the steps is identical.

### 1. Install system dependencies

```bash
# Homebrew (skip if already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python@3.11 git
brew install --cask tailscale
```

### 2. Clone the code and the models repo

```bash
# system code
cd ~
git clone https://github.com/chuckmy/agentic-translator.git
cd agentic-translator
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# private models repo (substitute your-org / your-repo)
mkdir -p ~/translab
cd ~/translab
git clone git@github.com:your-org/agentic-models.git models-repo
```

If your models repo does not yet exist, create it on GitHub (private) and
push an empty initial commit; you'll author Models from the Streamlit UI
in Model-dev mode.

### 3. Create the server config file

```bash
mkdir -p ~/.config/agentic-translator
cat > ~/.config/agentic-translator/server.env <<'EOF'
# Where the Models live (your private agentic-models repo)
export AT_MODELS_DIR="$HOME/translab/models-repo/models"
export AT_ENGINES_DIR="$HOME/translab/models-repo/engines"

# Company-wide LLM API key (loaded once at server start; translators do NOT
# need to enter their own). Hide the BYOK UI in the sidebar.
export ANTHROPIC_API_KEY="sk-ant-api03-..."   # ← replace with your real key
export AT_COMPANY_MODE=1                       # hides BYOK input in the UI

# Optional: pick a default provider / model
# export LLM_PROVIDER=anthropic
# export ANTHROPIC_MODEL=claude-sonnet-4-6
EOF
chmod 600 ~/.config/agentic-translator/server.env
```

The 600 permissions are important — this file holds the company API key.

### 4. Try running once, manually

```bash
source ~/.config/agentic-translator/server.env
cd ~/agentic-translator
.venv/bin/streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    --server.headless true
```

In a separate browser on the same machine, open <http://localhost:8501>.
You should see the UI with the BYOK key input **hidden** and a small
"Using company API key" caption instead. Stop it (Ctrl-C) once verified.

### 5. Join the company Tailnet

```bash
# Start the Tailscale menu bar app and sign in with the company SSO account
# (Google Workspace / Microsoft 365). Then give this machine a stable name:
sudo tailscale set --hostname=translab-server

# Verify
tailscale status
```

After this, the server is reachable on the tailnet as
`http://translab-server.<your-tailnet>.ts.net:8501` from any other
device on the tailnet.

### 6. Auto-start on boot (launchd, macOS)

Copy the template plist into LaunchAgents (this template is shipped in
the repo at `scripts/co.translab.agentic-translator.plist`):

```bash
cp scripts/co.translab.agentic-translator.plist \
   ~/Library/LaunchAgents/co.translab.agentic-translator.plist

# Edit the absolute paths inside the plist to match your machine, then:
launchctl load ~/Library/LaunchAgents/co.translab.agentic-translator.plist
```

Streamlit now starts at boot and restarts automatically if it crashes.
Logs are written to `~/.config/agentic-translator/streamlit.log`.

Verify with:

```bash
launchctl list | grep agentic
tail -f ~/.config/agentic-translator/streamlit.log
```

## Part 2 — Translator setup (per translator, ~5 minutes)

Each remote translator does the following one-time setup on their own
laptop:

1. Install Tailscale from <https://tailscale.com/download>.
2. Open the app, sign in with their **company SSO account** (Google / Microsoft).
3. The server `translab-server` will appear in their tailnet device list.
4. Bookmark `http://translab-server.<your-tailnet>.ts.net:8501` in their browser.
5. Done — they can now use agentic-translator from anywhere.

Day-to-day, the translator only needs to:

- Make sure Tailscale is running (small menu-bar icon).
- Visit the bookmark.
- Pick **Mode: Engine** and a compiled Engine, paste source, translate.

The Streamlit UI hides API-key entry; the company key on the server is
used silently. Translators never see, type, or know the key.

## Part 3 — Tailscale ACL recommendation

Recommended ACL JSON (paste in the Tailscale admin console → Access
controls). Restricts translators to the Streamlit port only; gives a
small admin group SSH and full access:

```json
{
  "groups": {
    "group:admins":     ["alice@translab.co"],
    "group:translators": ["bob@translab.co", "carol@translab.co"]
  },

  "tagOwners": {
    "tag:server": ["group:admins"]
  },

  "acls": [
    // Admins: full access to the server
    { "action": "accept", "src": ["group:admins"],     "dst": ["tag:server:*"] },

    // Translators: only the Streamlit port
    { "action": "accept", "src": ["group:translators"], "dst": ["tag:server:8501"] }
  ],

  "ssh": [
    // SSH only for admins
    { "action": "accept", "src": ["group:admins"], "dst": ["tag:server"], "users": ["root", "translab"] }
  ]
}
```

Then tag the server machine in the admin console with `tag:server`. After
this, even a malicious translator with valid SSO cannot SSH into the
server or reach any port other than 8501.

## Part 4 — Maintenance & updates

### Update the code

```bash
cd ~/agentic-translator
git pull
.venv/bin/pip install -r requirements.txt
launchctl unload ~/Library/LaunchAgents/co.translab.agentic-translator.plist
launchctl load   ~/Library/LaunchAgents/co.translab.agentic-translator.plist
```

### Update the models repo (Specs / glossaries / engines)

Models live on a separate private repo. Translators or Spec authors can
work in two patterns:

- **Direct on the server**: open the Streamlit UI in Model-dev mode,
  edit the Spec, click **Lock & Compile**, then SSH (admin only) and
  `git commit && git push` from `~/translab/models-repo`.
- **Branch-and-PR**: edit Models on a developer machine, push to a
  branch, open a PR. After merge, on the server: `git pull` (or via a
  cron job).

### Backup

Add the server's `~/translab/models-repo` to **Time Machine** (or your
preferred backup) — but the canonical source of truth is the GitHub
repo, so a fresh clone is always sufficient.

### Monitoring

```bash
# Server health
tail -f ~/.config/agentic-translator/streamlit.log
launchctl list | grep agentic

# Tailscale connectivity
tailscale status
tailscale ping <translator-device>
```

Tailscale Starter/Business includes a **device dashboard + audit log**:
see when each translator last connected, from which device, for how long.

## Part 5 — Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Browser shows "Can't connect" | Tailscale not running on translator's laptop, or server's Tailscale not signed in. Check `tailscale status` on both ends. |
| `translab-server.<...>.ts.net` doesn't resolve | MagicDNS off in admin console. Turn it on under DNS settings. |
| Streamlit page loads but "Using company API key" not shown | `AT_COMPANY_MODE=1` not in env. Re-source `server.env` and restart Streamlit. |
| "No engines yet" in Engine mode | The models repo on the server is empty. Compile at least one Engine (Model-dev mode → Lock & Compile, or `at model compile <id>`). |
| Streamlit becomes slow with many concurrent users | Single-process Streamlit limit. Either upgrade the host CPU or migrate to FastAPI backend (planned for v0.14.0). |
| Server reboots and Streamlit doesn't come back | launchd plist path / env var wrong. Check `tail -100 /var/log/system.log | grep agentic`. |
| Translator can SSH to the server | ACL not applied — re-paste the JSON above and verify with `tailscale ping` from a translator device. |

## Costs (monthly, 5 translators)

| Item | Cost |
|---|---|
| Server hardware (Mac mini M4, amortised over 3 years) | ~¥3,000 |
| Electricity (~5 W continuous) | ~¥250 |
| Tailscale Starter (5 users × $5) | ~¥3,750 |
| Internet (existing) | ¥0 |
| **Total infrastructure** | **~¥7,000 / month** |
| LLM API (depends on usage; example: 1M tokens/day mixed input+output @ Claude Sonnet 4.6 rates) | ~¥30,000〜¥150,000 |

The infrastructure is dwarfed by the LLM bill, but unlike a cloud
deployment the infrastructure cost does not grow with traffic.

## When to graduate beyond Tailscale + localhost

This setup comfortably supports up to ~20 concurrent translators. Move
on when:

- You consistently exceed ~20 active sessions.
- You need 99.9 %+ SLA (your office internet / power become the SPOF).
- You need automated regression testing on every model bump (v0.16 +).
- You want to expose Engines to clients via API (FastAPI backend, v0.14 +).

The Azure migration path is described separately (see
`docs/deploy-azure.md`, TBA). Because everything in this stack is
driven by environment variables (`AT_MODELS_DIR`, `AT_ENGINES_DIR`,
`ANTHROPIC_API_KEY`), the migration is largely an exercise in moving
file paths to Azure Files / Blob and the same container image up to
Azure Container Apps.
