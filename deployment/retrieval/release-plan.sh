#!/bin/sh
set -eu
# Prints instructions only. No cloud, IAM, deployment or traffic command is executed.
case "${1:-check}" in
 check) cat <<'TEXT'
Before deployment: inspect the existing service account and private invoker policy.
Verify no allUsers/allAuthenticatedUsers invoker binding, internal ingress reachability,
ID-token audience matching the configured service origin, and Enterprise reader-only graph role.
Authenticated /health/ready and /v1/provenance must match the reviewed index/model pins.
Linux image/base digest, wheels and resource sizing remain unverified locally.
TEXT
 ;;
 rollback) cat <<'TEXT'
Local registry rollback only:
python -m retrieval_service.cli rollback --registry REGISTRY.json --version PREVIOUS_VALIDATED_INDEX_HASH
Review the old immutable index/model/graph pair and its evidence, then request approval
for a separate cloud revision/traffic rollback. This script does not change running services.
TEXT
 ;;
 *) echo 'usage: release-plan.sh [check|rollback]' >&2; exit 2 ;;
esac
