#!/bin/bash
set -e

strip_quotes() {
    local value="$1"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

SYNTELES_MANIFEST_URL="$(strip_quotes "${SYNTELES_MANIFEST_URL}")"
AGENTLET="$(strip_quotes "${AGENTLET:-generic-assistant}")"
PROMPT="$(strip_quotes "${PROMPT}")"
DEBUG="$(strip_quotes "${DEBUG}")"

# Add debug flag if DEBUG is set
DEBUG_FLAG=""
if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "1" ]; then
    DEBUG_FLAG="--debug"
fi

if [ -n "$SYNTELES_MANIFEST_URL" ]; then
    # Fetch manifest and extract all values
    # Mask the manifest URL in logs for security
    MANIFEST_URL_SAFE=$(echo "$SYNTELES_MANIFEST_URL" | sed -E 's|(https://[^/]+/[^?]+).*|\1?[SIGNATURE_REDACTED]|')
    echo "Fetching manifest from: $MANIFEST_URL_SAFE"
    MANIFEST_JSON=$(curl -fsSL "$SYNTELES_MANIFEST_URL")
    export MANIFEST_JSON

    python3 - <<'PYEOF'
import json, os, shlex

manifest = json.loads(os.environ["MANIFEST_JSON"])

# Write agentlet YAML
with open("/tmp/agentlet.yaml", "w") as f:
    f.write(manifest.get("agentlet_yaml", ""))

# Write extracted values to a shell-sourceable file
prompt = manifest.get("prompt", "")
output_url = manifest.get("output_url", "")
input_files = manifest.get("input_files", [])
timeout = manifest.get("timeout", "")

# Determine image file names: use manifest type field when present,
# fall back to extension detection for manifests from older platform versions.
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
image_names = [
    f["name"] for f in input_files
    if f.get("type") == "image"
    or os.path.splitext(f.get("name", ""))[1].lower() in _IMAGE_EXTS
]

with open("/tmp/manifest_env.sh", "w") as f:
    f.write(f"export PROMPT={shlex.quote(prompt)}\n")
    f.write(f"export SYNTELES_OUTPUT_URL={shlex.quote(output_url)}\n")
    f.write(f"export SYNTELES_INPUT_FILES={shlex.quote(json.dumps(input_files))}\n")
    f.write(f"export SYNTELES_TIMEOUT={shlex.quote(str(timeout))}\n")
    f.write(f"export SYNTELES_IMAGE_FILES={shlex.quote(json.dumps(image_names))}\n")
PYEOF

    # shellcheck source=/dev/null
    source /tmp/manifest_env.sh
    AGENTLET=/tmp/agentlet.yaml
    
    # Debug: verify manifest values were extracted (mask sensitive URLs)
    echo "Manifest values extracted:"
    echo "  PROMPT: ${PROMPT:0:50}$([ ${#PROMPT} -gt 50 ] && echo '...')"
    if [ -n "$SYNTELES_OUTPUT_URL" ]; then
        # Extract just the S3 bucket and key path, mask the signature
        OUTPUT_URL_SAFE=$(echo "$SYNTELES_OUTPUT_URL" | sed -E 's|(https://[^/]+/[^?]+).*|\1?[SIGNATURE_REDACTED]|')
        echo "  SYNTELES_OUTPUT_URL: $OUTPUT_URL_SAFE"
    else
        echo "  SYNTELES_OUTPUT_URL: (not set)"
    fi
    echo "  SYNTELES_TIMEOUT: $SYNTELES_TIMEOUT"
    echo "  Input files count: $(echo "$SYNTELES_INPUT_FILES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")"
fi

# Download input files if present
if [ -n "$SYNTELES_INPUT_FILES" ] && [ "$SYNTELES_INPUT_FILES" != "[]" ]; then
    echo "Downloading input files to /tmp/input..."
    python3 - <<'PYEOF'
import json, os, urllib.request, re

for f in json.loads(os.environ["SYNTELES_INPUT_FILES"]):
    dest = os.path.join("/tmp/input", f["name"])
    print(f"  Downloading {f['name']}...")
    # Mask the presigned URL signature for security in logs
    url_safe = re.sub(r'(https://[^/]+/[^?]+).*', r'\1?[SIGNATURE_REDACTED]', f["url"])
    print(f"    from: {url_safe}")
    # Use the actual URL for download
    urllib.request.urlretrieve(f["url"], dest)
    print(f"  Saved to {dest}")
PYEOF
fi

# Add timeout flag if SYNTELES_TIMEOUT is set
TIMEOUT_FLAG=""
if [ -n "$SYNTELES_TIMEOUT" ] && [ "$SYNTELES_TIMEOUT" != "None" ]; then
    TIMEOUT_FLAG="--timeout $SYNTELES_TIMEOUT"
fi

# Build --image flags from manifest type info (set during manifest processing above).
# Falls back to extension detection when SYNTELES_IMAGE_FILES is unset (no-manifest path).
IMAGE_FLAGS=""
if [ -n "$SYNTELES_IMAGE_FILES" ] && [ "$SYNTELES_IMAGE_FILES" != "[]" ]; then
    IMAGE_FLAGS=$(python3 -c "
import json, os
names = json.loads(os.environ['SYNTELES_IMAGE_FILES'])
print(' '.join('--image /tmp/input/' + n for n in names if n), end='')
")
elif [ -d "/tmp/input" ]; then
    # Fallback: no manifest (direct AGENTLET/PROMPT env var path) — use extension detection
    for img in /tmp/input/*.jpg /tmp/input/*.jpeg /tmp/input/*.png /tmp/input/*.gif /tmp/input/*.webp \
               /tmp/input/*.JPG /tmp/input/*.JPEG /tmp/input/*.PNG /tmp/input/*.GIF /tmp/input/*.WEBP; do
        [ -f "$img" ] && IMAGE_FLAGS="$IMAGE_FLAGS --image $img"
    done
fi

# Run agentlet-core
# shellcheck disable=SC2086
agentlet-core --agentlet "$AGENTLET" --prompt "$PROMPT" $DEBUG_FLAG $TIMEOUT_FLAG $IMAGE_FLAGS

# Upload output files if /tmp/output is non-empty and SYNTELES_OUTPUT_URL is set
echo "Checking for output files..."
if [ -n "$SYNTELES_OUTPUT_URL" ]; then
    # Mask the presigned URL signature for security
    OUTPUT_URL_SAFE=$(echo "$SYNTELES_OUTPUT_URL" | sed -E 's|(https://[^/]+/[^?]+).*|\1?[SIGNATURE_REDACTED]|')
    echo "  SYNTELES_OUTPUT_URL: $OUTPUT_URL_SAFE"
else
    echo "  SYNTELES_OUTPUT_URL: (not set)"
fi
echo "  /tmp/output exists: $([ -d /tmp/output ] && echo 'YES' || echo 'NO')"
if [ -d /tmp/output ]; then
    echo "  /tmp/output contents: $(ls -la /tmp/output 2>/dev/null || echo 'empty or error')"
fi

if [ -n "$SYNTELES_OUTPUT_URL" ] && [ -n "$(ls -A /tmp/output 2>/dev/null)" ]; then
    echo "Zipping output files..."
    cd /tmp/output && zip -r /tmp/output.zip . || {
        echo "ERROR: Failed to zip output files"
        exit 1
    }
    echo "Uploading output.zip to S3..."
    HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/upload_response.txt -X PUT \
        -H "Content-Type: application/zip" \
        --data-binary @/tmp/output.zip \
        "$SYNTELES_OUTPUT_URL")
    
    if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 204 ]; then
        echo "✓ Output uploaded successfully (HTTP $HTTP_CODE)"
    else
        echo "ERROR: Upload failed with HTTP $HTTP_CODE"
        cat /tmp/upload_response.txt
        exit 1
    fi
else
    echo "Skipping output upload:"
    [ -z "$SYNTELES_OUTPUT_URL" ] && echo "  - SYNTELES_OUTPUT_URL is not set"
    [ -z "$(ls -A /tmp/output 2>/dev/null)" ] && echo "  - /tmp/output is empty or does not exist"
fi
