#!/usr/bin/env bash
set -euo pipefail

ref="${1:?usage: dispatch_autonomous_validation.sh <ref>}"

for workflow in ci.yml dependency-validation.yml gate-integrity.yml; do
  echo "Dispatching ${workflow} on ${ref}"
  gh workflow run "$workflow" --ref "$ref"
done
