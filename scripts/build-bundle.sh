#!/usr/bin/env bash
# Package the schemas and knowledge pack into dist/ as a versioned bundle.
#
# The bundle is what a downstream consumer (or a future SEO session) pulls in
# instead of vendoring copies of these files.
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="dist"
VERSION="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

rm -rf "$OUT"
mkdir -p "$OUT/schemas" "$OUT/knowledge"

cp schemas/*.schema.json "$OUT/schemas/"
cp docs/knowledge/*.md "$OUT/knowledge/"

cat > "$OUT/manifest.json" <<MANIFEST
{
  "name": "seo-knowledge-bundle",
  "commit": "${VERSION}",
  "built_at": "${BUILT_AT}",
  "schemas": [$(cd "$OUT/schemas" && ls *.json | sed 's/.*/"&"/' | paste -sd, -)],
  "knowledge": [$(cd "$OUT/knowledge" && ls *.md | sed 's/.*/"&"/' | paste -sd, -)]
}
MANIFEST

python3 -c "import json;json.load(open('$OUT/manifest.json'));print('manifest valid')"

echo "Bundle built at ${OUT}/ (commit ${VERSION})"
find "$OUT" -type f | sort
