#!/usr/bin/env bash
set -euo pipefail

readonly PLANTUML_VERSION="1.2026.7"
readonly PLANTUML_SHA256="ece3acb459678958d8a11454a83dd06fe4caa8e1fffb1c7eda7bfcf1dfbac574"
readonly PLANTUML_URL="https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-gplv2-${PLANTUML_VERSION}.jar"
readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PLANTUML_DIR="${ROOT_DIR}/tools"
readonly PLANTUML_JAR="${PLANTUML_DIR}/plantuml.jar"

mkdir -p "${PLANTUML_DIR}"

if [[ -f "${PLANTUML_JAR}" ]] && printf '%s  %s\n' "${PLANTUML_SHA256}" "${PLANTUML_JAR}" | sha256sum --check --status; then
  printf 'PlantUML %s already verified at %s\n' "${PLANTUML_VERSION}" "${PLANTUML_JAR}"
  exit 0
fi

temporary_jar="${PLANTUML_JAR}.tmp.$$"
trap 'rm -f "${temporary_jar}"' EXIT
curl --fail --location --silent --show-error "${PLANTUML_URL}" --output "${temporary_jar}"
printf '%s  %s\n' "${PLANTUML_SHA256}" "${temporary_jar}" | sha256sum --check -
mv "${temporary_jar}" "${PLANTUML_JAR}"
trap - EXIT
printf 'Downloaded PlantUML %s to %s\n' "${PLANTUML_VERSION}" "${PLANTUML_JAR}"
