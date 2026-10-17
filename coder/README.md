# Sol Coder Workspace Template (Docker)

Terraform template for [Coder](https://coder.com/docs/workspaces) workspaces on the Sol host. Each workspace is a Docker container that the `coder` service creates on the host engine (OrbStack) through `/var/run/docker.sock`.

| Item | Value |
| :--- | :--- |
| Coder server | `coder` service in [`compose/coding.yml`](../compose/coding.yml), image `ghcr.io/coder/coder:${CODER_TAG:-latest}` |
| Access URL | `https://coder.vrg.rocks` (`CODER_ACCESS_URL`, behind Authentik forward auth in the `Caddyfile`) |
| Template file | [`main.tf`](main.tf) (the only `.tf` file in this directory) |
| Workspace image | `codercom/enterprise-base:ubuntu` |
| Persistent storage | Docker volume `coder-<workspace-id>-home` at `/home/coder` |

> [!NOTE]
> `coder/default.tf` was deleted in October 2026. Terraform loads every `.tf` file in a directory as one module. The duplicate `terraform`, `provider`, `variable`, `data`, `module`, and `resource` blocks in `default.tf` and `main.tf` made `terraform validate` and `coder templates push` fail.

## How the Coder Server Reaches Docker

[`compose/coding.yml`](../compose/coding.yml) sets up the server as follows:

- `/var/run/docker.sock:/var/run/docker.sock` gives the server access to the host Docker engine.
- `group_add: ["${PGID}"]` adds the host group (`20`) so the `coder` user can open the socket.
- `${DOCKER_CONFIG_DIR}/coder:/home/coder/.config` keeps server state in `config/coder`.
- `${DOCKER_BASE_DIR}:/Sol` exposes the repository inside the server container. This is where you run `coder templates push` from.

Check socket access from the server container:

```bash
docker exec coder docker ps --format '{{.Names}}' | head -n 3
```

## What `main.tf` Provisions

| Resource | Purpose |
| :--- | :--- |
| `docker_volume.home_volume` | `coder-${workspace_id}-home`. Labels: `coder.owner`, `coder.owner_id`, `coder.workspace_id`, `coder.workspace_name_at_creation`. `lifecycle { ignore_changes = all }` keeps it across template updates. |
| `docker_container.workspace` | Runs only while the workspace is started (`count = start_count`). Name `coder-<owner>-<workspace>`. Mounts the home volume at `/home/coder`. |
| `coder_agent.main` | Linux agent. The architecture comes from the provisioner (`arm64` on the M1 Pro). |
| `module.code-server` | `registry.coder.com/coder/code-server/coder` `~> 1.0` (browser VS Code inside each workspace). |

Networking detail: the agent init script replaces `localhost` and `127.0.0.1` with `host.docker.internal`. The container maps `host.docker.internal` to `host-gateway`, so the agent can reach the Coder server through the host.

Git identity: `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, and `GIT_COMMITTER_EMAIL` come from the Coder owner profile. They override `~/.gitconfig`.

Agent metadata shown in the Coder UI: CPU and RAM usage (workspace and host), home disk usage, host load average (every 60 seconds), and host swap (every 10 seconds).

## Workspace Startup Script

The `startup_script` runs on every start. Each step checks first, so a restart does not reinstall tools that already exist in `/home/coder`.

1. **Home seed:** Copies `/etc/skel` into `~` once, then writes `~/.init_done`.
2. **System packages:** `sudo apt-get update` and `sudo apt-get install -y curl unzip git tar`. No Rust toolchain.
3. **Bun:** If `~/.bun` is missing, runs `curl -fsSL https://bun.sh/install | bash` and appends `BUN_INSTALL` and `PATH` lines to `~/.bashrc`.
4. **Jujutsu (`jj`):** If `jj` is not on `PATH` and `~/.local/bin/jj` is missing, downloads the prebuilt release `v0.28.2`:
    - Target `aarch64-unknown-linux-musl` when `uname -m` is `aarch64` or `arm64`, and `x86_64-unknown-linux-musl` otherwise.
    - URL `https://github.com/jj-vcs/jj/releases/download/v0.28.2/jj-v0.28.2-<target>.tar.gz`, extracted to `~/.local/bin/jj`.
    - Appends `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`.

The old template ran `cargo install jj-cli --locked`, which compiled Jujutsu from source on all 8 cores at every first start. The prebuilt binary removes that step (review estimate: about 4 minutes down to about 2 seconds).

To change the `jj` version, edit `JJ_VERSION="v0.28.2"` in `main.tf` and push the template. Existing workspaces keep their installed binary because `~/.local/bin/jj` lives on the persistent volume. Delete `~/.local/bin/jj` in a workspace to force the new version on its next start.

## Persistence Rules

- Kept across restarts: everything under `/home/coder` (projects, `~/.bun`, `~/.local/bin/jj`, `~/.bashrc`, dotfiles).
- Lost on restart: anything outside `/home/coder`, including apt packages. The startup script installs them again on each start.
- To bake extra tools into every workspace, change the image in `docker_container.workspace` or add idempotent steps to `startup_script`. You can also use [Coder dotfiles](https://coder.com/docs/dotfiles).

## Pushing the Template on Sol

Run from inside the `coder` server container, where the repository is mounted at `/Sol`:

```bash
# Authenticate the CLI against the Sol deployment (opens a token flow)
docker exec -it coder coder login https://coder.vrg.rocks

# Check the template directory (expect only main.tf and README.md)
docker exec coder ls /Sol/coder

# Create or update the template named "sol-docker" from this directory
docker exec -it coder coder templates push sol-docker --directory /Sol/coder

# Confirm the new version
docker exec coder coder templates versions list sol-docker
```

The template name `sol-docker` is an example. Use the name of the template that already exists in the Coder UI so the push creates a new version instead of a second template. List the existing names with `docker exec coder coder templates list`.

Optional variable: `docker_socket` (default empty). An empty value lets the Docker provider use its default socket. Set it only if Coder must talk to a different engine, for example with `--variable docker_socket=unix:///var/run/docker.sock`.

## Updating Running Workspaces

```bash
# List workspaces and their template versions
docker exec coder coder list

# Move one workspace to the latest template version
docker exec -it coder coder update <workspace-name>
```

The home volume is kept during updates (`ignore_changes = all`).
