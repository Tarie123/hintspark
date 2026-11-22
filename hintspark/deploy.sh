#!/usr/bin/env bash
# Deploy HintSpark to Google Cloud Run.
# Usage:
#   export PROJECT_ID=your-project
#   export NVIDIA_API_KEY=nvapi-...      # from build.nvidia.com
#   ./deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="hintspark"
SA_NAME="hintspark-run"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

echo "==> Least-privilege service account"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name "HintSpark Cloud Run"

echo "==> NVIDIA API key -> Secret Manager"
if [[ -n "${NVIDIA_API_KEY:-}" ]]; then
  if gcloud secrets describe nvidia-api-key >/dev/null 2>&1; then
    printf "%s" "$NVIDIA_API_KEY" | gcloud secrets versions add nvidia-api-key --data-file=-
  else
    printf "%s" "$NVIDIA_API_KEY" | gcloud secrets create nvidia-api-key --replication-policy=automatic --data-file=-
  fi
  gcloud secrets add-iam-policy-binding nvidia-api-key \
    --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor >/dev/null
  SECRET_FLAG=(--set-secrets "NVIDIA_API_KEY=nvidia-api-key:latest")
else
  echo "    NVIDIA_API_KEY not set - app will use built-in hints only."
  SECRET_FLAG=()
fi

echo "==> Supabase database URL -> Secret Manager"
if [[ -n "${DATABASE_URL:-}" ]]; then
  if gcloud secrets describe supabase-database-url >/dev/null 2>&1; then
    printf "%s" "$DATABASE_URL" | gcloud secrets versions add supabase-database-url --data-file=-
  else
    printf "%s" "$DATABASE_URL" | gcloud secrets create supabase-database-url --replication-policy=automatic --data-file=-
  fi
  gcloud secrets add-iam-policy-binding supabase-database-url \
    --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor >/dev/null
  DATABASE_SECRET_FLAG=(--set-secrets "DATABASE_URL=supabase-database-url:latest")
else
  echo "    DATABASE_URL not set - analytics will use local logging only."
  DATABASE_SECRET_FLAG=()
fi

echo "==> Build and deploy to Cloud Run (gen1 = gVisor sandbox)"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --execution-environment gen1 \
  --memory 1Gi --cpu 1 --concurrency 10 --max-instances 5 --timeout 60 \
  --set-env-vars "PORT=${PORT:-8080}" \
  "${DATABASE_SECRET_FLAG[@]}" \
  "${SECRET_FLAG[@]}" \
  --allow-unauthenticated

echo "==> Done:"
gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)'
