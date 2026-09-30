#!/usr/bin/env bash
# Downloads the pinned PlantUML jar into tools/ and verifies its checksum.
set -euo pipefail
VERSION=1.2025.4
SHA256=26518e14a3a04100cd76c0d96cab2d1171f36152215edd9790a28d20268200c1
DEST="$(dirname "$0")/../tools/plantuml.jar"
mkdir -p "$(dirname "$DEST")"
curl -sSL -o "$DEST" "https://github.com/plantuml/plantuml/releases/download/v${VERSION}/plantuml-${VERSION}.jar"
echo "${SHA256}  ${DEST}" | sha256sum -c -
