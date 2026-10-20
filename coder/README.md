# Sol Coder Workspace Template (Docker)

Terraform template for [Coder](https://coder.com/docs/workspaces) workspaces on the Sol host. Each workspace is a Docker container that the `coder` service creates on the host engine (OrbStack) through `/var/run/docker.sock`.

| Item | Value |
| :--- | :--- |
| Coder server | `coder` service in [`compose/coding.yml`](../compose/coding.yml), image `ghcr.io/coder/coder:latest` |
| Access URL | `https://coder.vrg.rocks` (`CODER_ACCESS_URL`, protected by zero-click Tinyauth v5 OIDC with `CODER_DISABLE_PASSWORD_AUTH=true` and `CODER_OIDC_ALLOW_SIGNUPS=false`) |
| Active template | `sol-workspace` (defined by [`main.tf`](main.tf), the only `.tf` file in this directory) |
| Workspace image | `codercom/enterprise-base:ubuntu` |
| Persistent storage | Docker volume `coder-<workspace-id>-home` at `/home/coder` (backed up to `data/backups/coder_home.tar.gz`) |

> [!NOTE]
> `coder/default.tf` was deleted in October 2026. Terraform loads every `.tf` file in a directory as one module. The duplicate `terraform`, `provider`, `variable`, `data`, `module`, and `resource` blocks in `default.tf` and `main.tf` previously caused `terraform validate` and `coder templates push` to fail.

## How the Coder Server Reaches Docker & Authenticates

[`compose/coding.yml`](../compose/coding.yml) and [`Caddyfile`](../Caddyfile) configure the server as follows:

- `/var/run/docker.sock:/var/run/docker.sock` gives the server access to the host OrbStack Docker engine.
- `group_add: ["0"]` adds the container user (`uid=1000`) to `gid=0` (`root`), which owns `/var/run/docker.sock` inside the OrbStack Linux VM, so `coder` can talk to the Docker daemon without running as root.
- `CODER_CLUSTER_HOST: "127.0.0.1"` binds the embedded PostgreSQL WireGuard/DERP cluster address to loopback.
- `redir /login /api/v2/users/oidc/callback 302` in `Caddyfile` pairs with Tinyauth v5 OIDC (`CODER_OIDC_ISSUER_URL: https://auth.vrg.rocks`) and admin-scoped `oidc_consents` in `scripts/identity_sync.py` to sign in `vrg` with zero clicks while blocking non-admin signups (`CODER_OIDC_ALLOW_SIGNUPS: "false"`).
- `${DOCKER_CONFIG_DIR}/coder:/home/coder/.config` keeps server state and the embedded PostgreSQL database in `config/coder` (dumped nightly to `data/backups/coder_db.sql.gz` by `scripts/stage_db_backups.sh`).
- `${DOCKER_BASE_DIR}:/Sol` mounts the repository inside the server container for template pushes.

Check socket access from the server container:

```bash
docker exec coder curl -sS --unix-socket /var/run/docker.sock http://localhost/_ping
```

## What `main.tf` Provisions

| Resource | Purpose |
| :--- | :--- |
| `docker_volume.home_volume` | `coder-${workspace_id}-home`. Labels: `coder.owner`, `coder.owner_id`, `coder.workspace_id`, `coder.workspace_name_at_creation`. `lifecycle { ignore_changes = all }` preserves it across template updates. |
| `docker_container.workspace` | Runs only while the workspace is started (`count = start_count`). Name `coder-<owner>-<workspace>`. Mounts the home volume at `/home/coder`. |
| `coder_agent.main` | Linux agent. The architecture comes from the provisioner (`arm64` on the M1 Pro). |
| `module.code-server` | `registry.coder.com/coder/code-server/coder` `~> 1.0` (browser VS Code inside each workspace). |

Networking detail: the agent init script replaces `localhost` and `127.0.0.1` with `host.docker.internal`. The container maps `host.docker.internal` to `host-gateway`, so the agent reaches the Coder server through the host.

Git identity: `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, and `GIT_COMMITTER_EMAIL` come from the Coder owner profile and override `~/.gitconfig`.

Agent metadata shown in the Coder UI: CPU and RAM usage (workspace and host), home disk usage, host load average (every 60 seconds), and host swap (every 10 seconds).

## Workspace Startup Script

The `startup_script` runs on every start. Each step checks first, so a restart does not reinstall tools that already exist in `/home/coder`.

1. **Home seed:** Copies `/etc/skel` into `~` once, then writes `~/.init_done`.
2. **System packages:** `sudo apt-get update` and `sudo apt-get install -y curl unzip git tar`. No Rust toolchain is compiled.
3. **Bun:** If `~/.bun` is missing, runs `curl -fsSL https://bun.sh/install | bash` and appends `BUN_INSTALL` and `PATH` lines to `~/.bashrc`.
4. **Jujutsu (`jj`):** If `jj` is not on `PATH` and `~/.local/bin/jj` is missing, downloads the prebuilt release `v0.28.2`:
    - Target `aarch64-unknown-linux-musl` when `uname -m` is `aarch64` or `arm64`, and `x86_64-unknown-linux-musl` otherwise.
    - URL `https://github.com/jj-vcs/jj/releases/download/v0.28.2/jj-v0.28.2-<target>.tar.gz`, extracted to `~/.local/bin/jj`.
    - Appends `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`.

The initial template ran `cargo install jj-cli --locked`, which compiled Jujutsu from source on all CPU cores at first start (~4 minutes). Downloading the prebuilt musl binary completes in ~2 seconds.

To change the `jj` version, edit `JJ_VERSION="v0.28.2"` in `main.tf` and push the template. Existing workspaces keep their installed binary because `~/.local/bin/jj` lives on the persistent volume. Delete `~/.local/bin/jj` in a workspace to force the new version on its next start.

## Persistence & Backup Rules

- **Kept across restarts:** Everything under `/home/coder` (projects, `~/.bun`, `~/.local/bin/jj`, `~/.bashrc`, dotfiles).
- **Backed up nightly (`scripts/stage_db_backups.sh`):**
  - Embedded PostgreSQL database (`config/coder/coderv2/postgres`) is dumped to `data/backups/coder_db.sql.gz` (with PG 17 `SET transaction_timeout` stripped for PG 16 compatibility).
  - Active workspace volume (`coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home`) is recorded in `data/backups/coder_volume_name.txt` and archived to `data/backups/coder_home.tar.gz`.
  - Both artifacts are snapshotted into Restic (`/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`) and restored automatically by `scripts/restore.sh --restore-dbs`.
- **Lost on container recreation:** Anything outside `/home/coder`, including apt packages. The startup script reinstalls apt packages on each start.

## Pushing the `sol-workspace` Template on Sol

Run from inside the `coder` server container, where the repository is mounted at `/Sol`:

```bash
# List existing templates (active template is "sol-workspace")
docker exec coder coder templates list

# Check the template directory (expect main.tf and README.md)
docker exec coder ls /Sol/coder

# Push an updated version of the "sol-workspace" template non-interactively
docker exec coder coder templates push sol-workspace -d /Sol/coder -y

# Confirm the new version
docker exec coder coder templates versions list sol-workspace
```

Optional variable: `docker_socket` (default empty). An empty value lets the Docker provider use its default socket (`/var/run/docker.sock`).

## Updating Running Workspaces

```bash
# List workspaces and their template versions
docker exec coder coder list

# Move one workspace to the latest template version
docker exec -it coder coder update <workspace-name>
```

The home volume is preserved during updates (`ignore_changes = all`).
