#!/usr/bin/env bash
# Run in Cloud Shell from the repository root. No passwords or keys required.
set -euo pipefail
if [[ "${3:-}" != "--public" || -z "${1:-}" || -z "${2:-}" ]]; then
  echo "Usage: bash deploy/deploy_cloud_run.sh PROJECT_ID REGION --public"
  echo "Creates billable resources and an unauthenticated judge-facing demo."
  exit 2
fi
project_id="$1"
region="$2"
service="railpulser-demo"
repository="railpulse"
runtime_account="railpulse-demo@${project_id}.iam.gserviceaccount.com"
revision_tag="$(git rev-parse --short HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="${region}-docker.pkg.dev/${project_id}/${repository}/${service}:${revision_tag}"

gcloud config set project "$project_id"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com
if ! gcloud artifacts repositories describe "$repository" --location="$region" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repository" --repository-format=docker --location="$region" --description="RailPulser hackathon demo"
fi
if ! gcloud iam service-accounts describe "$runtime_account" >/dev/null 2>&1; then
  gcloud iam service-accounts create railpulse-demo --display-name="RailPulser demo runtime (no project roles)"
fi
# Build executes as the project's configured Cloud Build identity, not runtime SA.
gcloud builds submit --config=cloudbuild.yaml --substitutions="_IMAGE=$image" .
# Keep private while the exact service origin is established and configured.
gcloud run deploy "$service" --image="$image" --region="$region" \
  --service-account="$runtime_account" --port=8080 --no-allow-unauthenticated \
  --memory=2Gi --cpu=2 --concurrency=4 --timeout=240 --min-instances=0 --max-instances=1 \
  --set-env-vars=RAILPULSE_PUBLIC_ORIGIN=
service_url="$(gcloud run services describe "$service" --region="$region" --format='value(status.url)')"
if [[ "$service_url" != https://*.run.app ]]; then
  echo "Unexpected service URL; service remains private. Inspect the deployment."
  exit 1
fi
gcloud run services update "$service" --region="$region" --update-env-vars="RAILPULSE_PUBLIC_ORIGIN=$service_url"
gcloud run services add-iam-policy-binding "$service" --region="$region" \
  --member=allUsers --role=roles/run.invoker
python3 scripts/smoke_cloud_http.py --base-url "$service_url"
echo "Judge-facing React dashboard: $service_url"
echo "Public demo, not durable hosting. Lab expiry or service restarts can discard sessions."
