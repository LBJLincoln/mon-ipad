# Credential Sharing Protocol

> Single source of truth: `.env.local` on the VM. Distribute via scp. NEVER commit to Git.

---

## The File

`.env.local` lives at `~/mon-ipad/.env.local` on every machine.

It is in `.gitignore` and MUST NEVER be committed to any repository.

## Credential Categories

| Category | Example Vars | Count | Purpose |
|----------|-------------|-------|---------|
| Anthropic | `ANTHROPIC_API_KEY` | 1 | Claude API access |
| HuggingFace | `HF_TOKEN`, `HF_TOKEN_2`, `HF_TOKEN_3` | 3 | 3 HF accounts (LBJLincoln, LBJLincoln26, Nomos42) |
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` | 3+ | Database access |
| Telegram | `TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_ID` | 2+ | Bot tokens, chat IDs |
| Kaggle | `KAGGLE_USERNAME`, `KAGGLE_KEY` | 2 | Kaggle API |
| Modal | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | 2 | Modal.com serverless GPU |
| NBA APIs | `NBA_API_KEY` etc. | varies | Sports data |
| GitHub | `GITHUB_TOKEN` | 1 | GitHub API (not SSH) |
| Google | `GOOGLE_API_KEY` etc. | varies | Search, Colab |
| Neo4j | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | 3 | Knowledge graph |
| Various | Other API keys | varies | FEC, FRED, CoinGecko, etc. |

## Distribution Protocol

### Initial Setup (New Machine)

```bash
# From the new machine, pull .env.local from VM
scp termius@<VM_IP>:~/mon-ipad/.env.local ~/nomos42/mon-ipad/.env.local
```

### After Adding/Rotating a Key

1. **Update on VM first** (always the source of truth):
   ```bash
   # On the VM
   nano ~/mon-ipad/.env.local
   # Add or update the key
   ```

2. **Distribute to each machine**:
   ```bash
   # From VM, push to each machine (if VM can SSH to them)
   scp ~/mon-ipad/.env.local user@macbook1-ip:~/nomos42/mon-ipad/.env.local
   scp ~/mon-ipad/.env.local user@macbook2-ip:~/nomos42/mon-ipad/.env.local
   scp ~/mon-ipad/.env.local user@acer-ip:~/nomos42/mon-ipad/.env.local
   ```

   Or from each machine, pull:
   ```bash
   scp termius@<VM_IP>:~/mon-ipad/.env.local ~/nomos42/mon-ipad/.env.local
   ```

3. **Verify on each machine**:
   ```bash
   source ~/nomos42/mon-ipad/.env.local
   echo "Loaded $(env | grep -c '=') env vars"
   ```

### Automated Sync (Optional)

Add to cron on each local machine:
```cron
# Pull latest credentials from VM daily at 3am
0 3 * * * scp -q termius@<VM_IP>:~/mon-ipad/.env.local ~/nomos42/mon-ipad/.env.local 2>/dev/null
```

## Security Rules

1. **NEVER commit `.env.local` to Git.** It is in `.gitignore`. Double-check before any `git add .`
2. **NEVER send credentials via Telegram, email, or any unencrypted channel.** SCP only.
3. **NEVER store credentials in Claude memory files or CLAUDE.md.**
4. **File permissions**: After copying, restrict access:
   ```bash
   chmod 600 ~/nomos42/mon-ipad/.env.local
   ```
5. **Rotation schedule**: No fixed schedule, but rotate immediately if:
   - A machine is lost or stolen
   - A key shows unauthorized usage
   - A service reports a breach
6. **Machine decommission**: Before retiring a machine:
   ```bash
   rm -f ~/nomos42/mon-ipad/.env.local
   # Also revoke that machine's SSH key from GitHub and VM authorized_keys
   ```

## Emergency Key Rotation

If a machine is compromised:

1. Immediately regenerate the most sensitive keys:
   - `ANTHROPIC_API_KEY` at console.anthropic.com
   - `TELEGRAM_BOT_TOKEN` via @BotFather
   - `HF_TOKEN*` at huggingface.co/settings/tokens
   - `SUPABASE_SERVICE_KEY` at supabase dashboard

2. Update `.env.local` on the VM

3. Redistribute to remaining trusted machines only

4. Revoke the compromised machine's SSH keys:
   ```bash
   # On VM: remove the machine's key from authorized_keys
   nano ~/.ssh/authorized_keys
   # On GitHub: Settings > SSH keys > Delete the key
   ```

## Checking What You Have

```bash
# Count total credentials
source ~/nomos42/mon-ipad/.env.local
env | grep -c "TOKEN\|KEY\|SECRET\|PASSWORD\|URL"

# List credential names (not values)
grep -oP '^\w+(?==)' ~/nomos42/mon-ipad/.env.local | sort

# Verify a specific service
# Anthropic
curl -s https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-sonnet-4-20250514","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' | head -c 100

# HuggingFace
curl -s https://huggingface.co/api/whoami -H "Authorization: Bearer $HF_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','FAIL'))"
```
