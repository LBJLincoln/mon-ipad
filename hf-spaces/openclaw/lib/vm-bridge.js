/**
 * VM Bridge — SSH remote execution on the Nomos42 VM.
 *
 * Gives OpenClaw (Eve) the same power as Claude Code CLI (Adam):
 * - Execute any command on the VM
 * - Git operations (commit, push, pull)
 * - File read/write
 * - Script execution
 * - Full filesystem access
 *
 * Uses SSH2 with ed25519 key authentication.
 */

const { Client } = require('ssh2');
const logger = require('./logger');

class VMBridge {
  constructor(config = {}) {
    this.host = config.host || process.env.VM_HOST || '34.136.180.66';
    this.port = config.port || 22;
    this.username = config.username || process.env.VM_USER || 'termius';
    this.privateKey = config.privateKey || process.env.SSH_PRIVATE_KEY || '';
    this.workDir = config.workDir || '/home/termius';
    this.timeout = config.timeout || 30000; // 30s default
  }

  /**
   * Execute a command on the VM via SSH.
   * Returns { stdout, stderr, code }
   */
  exec(command, options = {}) {
    const timeout = options.timeout || this.timeout;
    const cwd = options.cwd || this.workDir;

    return new Promise((resolve, reject) => {
      if (!this.privateKey) {
        return reject(new Error('SSH_PRIVATE_KEY not configured'));
      }

      const conn = new Client();
      let stdout = '';
      let stderr = '';
      let timedOut = false;

      const timer = setTimeout(() => {
        timedOut = true;
        conn.end();
        reject(new Error(`SSH command timed out after ${timeout}ms`));
      }, timeout);

      conn.on('ready', () => {
        // Wrap command with cd and source .env.local
        const fullCmd = `cd ${cwd} && source /home/termius/mon-ipad/.env.local 2>/dev/null; ${command}`;

        conn.exec(fullCmd, (err, stream) => {
          if (err) {
            clearTimeout(timer);
            conn.end();
            return reject(err);
          }

          stream.on('close', (code) => {
            clearTimeout(timer);
            conn.end();
            if (!timedOut) {
              resolve({ stdout: stdout.trim(), stderr: stderr.trim(), code });
            }
          });

          stream.on('data', (data) => { stdout += data.toString(); });
          stream.stderr.on('data', (data) => { stderr += data.toString(); });
        });
      });

      conn.on('error', (err) => {
        clearTimeout(timer);
        reject(new Error(`SSH connection failed: ${err.message}`));
      });

      conn.connect({
        host: this.host,
        port: this.port,
        username: this.username,
        privateKey: this.privateKey,
        readyTimeout: 10000,
      });
    });
  }

  /**
   * Execute a git command in a repo directory.
   */
  async git(repo, command) {
    const repoPath = repo.startsWith('/') ? repo : `/home/termius/${repo}`;
    return this.exec(`git ${command}`, { cwd: repoPath });
  }

  /**
   * Read a file from the VM.
   */
  async readFile(filePath) {
    const result = await this.exec(`cat "${filePath}"`, { timeout: 10000 });
    if (result.code !== 0) throw new Error(`Read failed: ${result.stderr}`);
    return result.stdout;
  }

  /**
   * Write content to a file on the VM.
   * Uses base64 encoding to handle special characters safely.
   */
  async writeFile(filePath, content) {
    const b64 = Buffer.from(content).toString('base64');
    const result = await this.exec(
      `echo "${b64}" | base64 -d > "${filePath}"`,
      { timeout: 15000 }
    );
    if (result.code !== 0) throw new Error(`Write failed: ${result.stderr}`);
    return { ok: true, path: filePath };
  }

  /**
   * Append content to a file on the VM.
   */
  async appendFile(filePath, content) {
    const b64 = Buffer.from(content).toString('base64');
    const result = await this.exec(
      `echo "${b64}" | base64 -d >> "${filePath}"`,
      { timeout: 15000 }
    );
    if (result.code !== 0) throw new Error(`Append failed: ${result.stderr}`);
    return { ok: true, path: filePath };
  }

  /**
   * Git commit + push in a repo.
   */
  async gitCommitPush(repo, message, files = '.') {
    const repoPath = repo.startsWith('/') ? repo : `/home/termius/${repo}`;
    const addResult = await this.exec(
      `git add ${files} && git commit -m "${message.replace(/"/g, '\\"')}" && git push origin main`,
      { cwd: repoPath, timeout: 60000 }
    );
    return addResult;
  }

  /**
   * Clone or pull a repo.
   */
  async gitSync(repo) {
    const repoPath = `/home/termius/${repo}`;
    const result = await this.exec(
      `if [ -d "${repoPath}/.git" ]; then cd "${repoPath}" && git pull origin main; else git clone https://github.com/LBJLincoln/${repo}.git "${repoPath}"; fi`,
      { timeout: 60000 }
    );
    return result;
  }

  /**
   * List files in a directory.
   */
  async ls(dirPath, options = '') {
    const result = await this.exec(`ls ${options} "${dirPath}"`, { timeout: 10000 });
    return result.stdout;
  }

  /**
   * Check if VM is reachable.
   */
  async ping() {
    const start = Date.now();
    try {
      const result = await this.exec('echo ok', { timeout: 5000 });
      return {
        reachable: result.stdout === 'ok',
        latency: Date.now() - start,
      };
    } catch (err) {
      return { reachable: false, latency: Date.now() - start, error: err.message };
    }
  }

  /**
   * Get VM system info.
   */
  async sysinfo() {
    const result = await this.exec(
      'echo "hostname=$(hostname)" && echo "uptime=$(uptime -p)" && echo "disk=$(df -h / | tail -1 | awk \'{print $3"/"$2" ("$5")"}\' )" && echo "mem=$(free -h | awk \'/Mem:/ {print $3"/"$2}\')" && echo "load=$(cat /proc/loadavg | cut -d" " -f1-3)"',
      { timeout: 10000 }
    );
    if (result.code !== 0) return { error: result.stderr };

    const info = {};
    for (const line of result.stdout.split('\n')) {
      const [key, ...val] = line.split('=');
      if (key && val.length) info[key.trim()] = val.join('=').trim();
    }
    return info;
  }

  /**
   * Manage HF Spaces from VM (using huggingface_hub via Python).
   */
  async hfSpaceAction(spaceId, action, params = {}) {
    let pyCmd;
    switch (action) {
      case 'restart':
        pyCmd = `from huggingface_hub import HfApi; api = HfApi(); api.restart_space("${spaceId}"); print("OK")`;
        break;
      case 'pause':
        pyCmd = `from huggingface_hub import HfApi; api = HfApi(); api.pause_space("${spaceId}"); print("OK")`;
        break;
      case 'resume':
        pyCmd = `from huggingface_hub import HfApi; api = HfApi(); api.restart_space("${spaceId}"); print("OK")`;
        break;
      case 'logs':
        pyCmd = `from huggingface_hub import HfApi; api = HfApi(); logs = api.get_space_runtime("${spaceId}"); print(logs)`;
        break;
      case 'set-secret':
        pyCmd = `from huggingface_hub import HfApi; api = HfApi(); api.add_space_secret("${spaceId}", "${params.key}", "${params.value}"); print("OK")`;
        break;
      default:
        throw new Error(`Unknown HF action: ${action}`);
    }
    return this.exec(
      `cd /home/termius/mon-ipad && source .env.local && python3 -c '${pyCmd}'`,
      { timeout: 30000 }
    );
  }
}

module.exports = VMBridge;
