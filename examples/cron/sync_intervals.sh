#!/usr/bin/env bash
set -euo pipefail

: "${NOTION_UPLOADER_URL:?Set NOTION_UPLOADER_URL}"
: "${NOTION_UPLOADER_API_KEY:?Set NOTION_UPLOADER_API_KEY}"

exec 9>/tmp/notion-uploader-intervals-sync.lock
flock -n 9 || exit 0

curl \
  --fail-with-body \
  --silent \
  --show-error \
  --max-time 180 \
  --retry 3 \
  --retry-delay 20 \
  --request POST \
  --header "x-api-key: ${NOTION_UPLOADER_API_KEY}" \
  "${NOTION_UPLOADER_URL%/}/v2/intervals/sync"
