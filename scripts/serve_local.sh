#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s --rox-core <path> [--port <port>] [--no-pull]\n' \
        "${0##*/}" >&2
    exit 2
}

rox_core=
port=8000
no_pull=false
while (($#)); do
    case "$1" in
        --rox-core)
            (($# >= 2)) || usage
            [[ $2 != --* ]] || usage
            rox_core=$2
            shift 2
            ;;
        --port)
            (($# >= 2)) || usage
            [[ $2 =~ ^[0-9]+$ ]] || usage
            port=$((10#$2))
            ((port >= 1 && port <= 65535)) || usage
            shift 2
            ;;
        --no-pull)
            no_pull=true
            shift
            ;;
        *)
            usage
            ;;
    esac
done

[[ -n $rox_core ]] || usage
[[ -d $rox_core ]] || {
    printf 'rox-core path does not exist: %s\n' "$rox_core" >&2
    exit 2
}
rox_core=$(cd -- "$rox_core" && pwd)
if ! git -C "$rox_core" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'rox-core path is not a Git worktree: %s\n' "$rox_core" >&2
    exit 2
fi

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

timed_step() {
    local label=$1
    shift
    local started=$SECONDS
    local status=0
    "$@" || status=$?
    printf '%s: %ss\n' "$label" "$((SECONDS - started))"
    return "$status"
}

update_project() {
    local branch
    local status
    if [[ $no_pull == true ]]; then
        printf 'Skipping pull: --no-pull was supplied.\n'
        return
    fi

    branch=$(git branch --show-current)
    if [[ $branch != main ]]; then
        printf 'Skipping pull: current branch is %s, not main.\n' "$branch"
        return
    fi
    status=$(git status --porcelain)
    if [[ -n $status ]]; then
        printf 'Skipping pull: the worktree is not clean.\n'
        return
    fi
    git pull --ff-only
}

ensure_pinned_commit() {
    local repository=$1
    local commit=$2
    if ! git -C "$repository" cat-file -e "${commit}^{commit}" 2>/dev/null; then
        if ! timed_step "fetch rox-core origin" git -C "$repository" fetch origin; then
            printf 'Could not fetch origin; pinned rox-core commit %s is unavailable.\n' \
                "$commit" >&2
            return 1
        fi
    fi
    if ! git -C "$repository" cat-file -e "${commit}^{commit}" 2>/dev/null; then
        printf 'Pinned rox-core commit %s is unavailable after fetching origin.\n' \
            "$commit" >&2
        return 1
    fi
}

timed_step "project update" update_project
timed_step "uv sync" uv sync
timed_step "PlantUML fetch" ./scripts/fetch_plantuml.sh

commit_file=pages/authoring/COMMIT
if [[ ! -f $commit_file ]]; then
    printf 'Pinned rox-core commit file is missing: %s/%s\n' \
        "$project_root" "$commit_file" >&2
    exit 1
fi
pinned_commit=$(<"$commit_file")
if [[ ! $pinned_commit =~ ^[0-9a-fA-F]{40,64}$ ]]; then
    printf 'Pinned rox-core SHA is invalid in %s: %s\n' "$commit_file" "$pinned_commit" >&2
    exit 1
fi
timed_step "pinned rox-core commit check" ensure_pinned_commit "$rox_core" "$pinned_commit"

timed_step "site build" uv run rox-dox build pages \
    --repo "$rox_core" \
    --repo-url https://github.com/Rox-AI/rox-core \
    --out site \
    --plantuml-jar tools/plantuml.jar

printf 'Open http://localhost:%s/rox-core.html\n' "$port"
exec python3 -m http.server "$port" --bind 127.0.0.1 --directory site
