#!/usr/bin/env bash
set -euo pipefail

task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task_cli="${BASETEN_CLI:-baseten}"
task_metadata="${TMPDIR:-/tmp}/apex-baseten-deployment.json"

# Check authentication before submitting a billable deployment.
"$task_cli" auth status
# Preserve scale-to-zero when replacing this existing model's production version.
"$task_cli" model environment update-autoscaling \
  --model-name apex-flash-1-abliterated --environment production \
  --min-replica 0 --max-replica 1 --scale-down-delay 60 \
  --concurrency-target 2
task_result="$(mktemp "${TMPDIR:-/tmp}/apex-deployment.XXXXXX")"
"$task_cli" model push --dir "$task_dir" --environment production --output json > "$task_result"
mv -- "$task_result" "$task_metadata"
task_model_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"]["id"])' "$task_metadata")"
task_deployment_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["deployment"]["id"])' "$task_metadata")"

# Apply before waiting for the image build or model load. Autoscaling is a
# deployment setting, not a top-level Truss config field.
"$task_cli" model deployment update-autoscaling \
  --model-id "$task_model_id" --deployment-id "$task_deployment_id" \
  --min-replica 0 --max-replica 1 --scale-down-delay 60 \
  --concurrency-target 2

printf '\nInspect deployment and verify autoscaling settings:\n'
printf '%s model deployment describe --model-id %s --deployment-id %s\n' \
  "$task_cli" "$task_model_id" "$task_deployment_id"
printf '\nFollow build and runtime logs:\n'
printf '%s model deployment logs --model-id %s --deployment-id %s --tail\n' \
  "$task_cli" "$task_model_id" "$task_deployment_id"
printf '\nSmoke test once ready:\npython3 %s/smoke_test.py\n' "$task_dir"
