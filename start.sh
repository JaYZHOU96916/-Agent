#!/usr/bin/env bash
# Local, single-user deployment. Keep secrets in Compose's env file, never source it.
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ $# -gt 0 ]]; then
  if [[ $# -eq 1 && ( "$1" == "--help" || "$1" == "-h" ) ]]; then
    printf 'Usage: ./start.sh\nBuild and start the local workspace; preserve existing .env and data volumes.\n'
    exit 0
  fi
  printf 'Unknown argument. Usage: ./start.sh [--help]\n' >&2
  exit 2
fi

fail() { printf 'Startup failed: %s\n' "$1" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || fail 'Install Docker Desktop or Docker Engine with Compose v2, then start Docker.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
docker compose up --help | grep -q -- '--wait-timeout' || fail 'Update Docker Compose to a version supporting --wait-timeout.'
docker info >/dev/null 2>&1 || fail 'Docker Engine is not running or this user cannot access it.'
[[ "$(docker info --format '{{.OSType}}')" == 'linux' ]] || fail 'Switch Docker to Linux containers.'

if [[ ! -e .env ]]; then
  (umask 077; cp -n .env.example .env)
  printf 'Created .env (private permissions). Set LLM_API_KEY and LLM_MODEL to enable analysis.\n'
fi

# A user-specified environment/file value takes precedence over automatic detection.
if [[ -z "${DOCKER_GID+x}" ]] && ! grep -Eq '^[[:space:]]*(export[[:space:]]+)?DOCKER_GID[[:space:]]*=' .env; then
  if [[ -S /var/run/docker.sock ]]; then
    DOCKER_GID="$(stat -Lc '%g' /var/run/docker.sock 2>/dev/null || stat -Lf '%g' /var/run/docker.sock)"
    export DOCKER_GID
  fi
fi

compose=(docker compose --project-directory "$PROJECT_DIR" --env-file "$PROJECT_DIR/.env" -f "$PROJECT_DIR/docker-compose.yml")
trap 'printf "Startup did not finish. Check: docker compose ps -a; docker compose logs --tail=100 backend frontend redis\nExisting data volumes have been preserved.\n" >&2' ERR
"${compose[@]}" config --quiet
"${compose[@]}" up --build -d --wait --wait-timeout 120 backend frontend
"${compose[@]}" exec -T backend python - < "$PROJECT_DIR/scripts/verify_stack.py"
printf '\nWorkspace ready: http://127.0.0.1:3000\nAPI docs: http://127.0.0.1:8000/docs\nStop (preserving data): docker compose down\nSamples: python3 examples/generate.py\n'
