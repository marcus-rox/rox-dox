#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s <domain> [--map]\n' "${0##*/}" >&2
    exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
domain=$1
shift
regenerate_map=false
if [[ ${1:-} == --map ]]; then
    regenerate_map=true
    shift
fi
[[ $# -eq 0 ]] || usage

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repo=/home/ubuntu/repos/rox-core
site_dir=/home/ubuntu/scratch/site_gen
shots_dir=/home/ubuntu/scratch/shots_gen
plantuml_jar=/home/ubuntu/rox-docs-t2/tools/plantuml.jar

cd "$project_root"
mkdir -p "$shots_dir"

timed_step() {
    local label=$1
    shift
    local started=$SECONDS
    "$@"
    printf '%s: %ss\n' "$label" "$((SECONDS - started))"
}

if [[ $regenerate_map == true ]]; then
    timed_step "feature map" uv run python pages/authoring/feature_map.py \
        --domain "$domain" --repo "$repo"
fi

timed_step "feature pages" uv run python pages/authoring/feature_pages.py \
    --domain "$domain" --repo "$repo"

timed_step "partial build" uv run rox-dox build pages \
    --repo "$repo" \
    --repo-url https://github.com/Rox-AI/rox-core \
    --out "$site_dir" \
    --plantuml-jar "$plantuml_jar" \
    --only "domain-${domain},feature-${domain}-*" \
    --no-folder-pages

shopt -s nullglob
feature_pages=("$project_root"/pages/features/"feature-${domain}-"*.json)
[[ ${#feature_pages[@]} -gt 0 ]] || {
    printf 'No feature pages found for domain %s\n' "$domain" >&2
    exit 1
}
lint_page_ids=("domain-${domain}")
for feature_page in "${feature_pages[@]}"; do
    page_id=${feature_page##*/}
    lint_page_ids+=("${page_id%.json}")
done
timed_lint() {
    local started=$SECONDS
    local lint_status=0
    local output summary
    output=$(uv run rox-dox lint-diagrams pages --page "${lint_page_ids[@]}" 2>&1) \
        || lint_status=$?
    if [[ $lint_status -le 1 && -n $output ]]; then
        summary=${output##*$'\n'}
    else
        summary="lint unavailable"
    fi
    printf 'lint: %s\n' "$summary"
    printf 'diagram lint: %ss\n' "$((SECONDS - started))"
}
timed_lint

timed_step "screenshot domain-${domain}" google-chrome \
    --headless=new \
    --no-sandbox \
    --hide-scrollbars \
    --window-size=1600,9000 \
    "--screenshot=${shots_dir}/domain-${domain}.png" \
    "file://${site_dir}/domain-${domain}.html"

for feature_page in "${feature_pages[@]}"; do
    page_id=${feature_page##*/}
    page_id=${page_id%.json}
    timed_step "screenshot ${page_id}" google-chrome \
        --headless=new \
        --no-sandbox \
        --hide-scrollbars \
        --window-size=1600,9000 \
        "--screenshot=${shots_dir}/${page_id}.png" \
        "file://${site_dir}/${page_id}.html"
done
