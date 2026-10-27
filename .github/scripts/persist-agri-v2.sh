#!/usr/bin/env bash
set -euo pipefail
# Transactional scoped commit: no reset/copy overlay and no lost deletions.
python -m automation.agri_v2.checkpoint_persistence
