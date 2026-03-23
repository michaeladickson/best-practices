# Cloud Run Deployment

## Two-Image Pattern

Separate images for API (always-on service) and jobs (scheduled/on-demand):

```yaml
# cloudbuild-api.yaml — Web service
steps:
  - name: node:20    # Build React frontend
    entrypoint: bash
    args: ['-c', 'cd frontend && npm ci && npm run build']
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'Dockerfile.api', '-t', 'image:latest', '.']
  - name: gcr.io/cloud-builders/docker
    args: ['push', 'image:latest']
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    args: ['gcloud', 'run', 'deploy', 'service-name', '--image', 'image:latest']

# cloudbuild-sync.yaml — Batch jobs
# Same image, different CLI flags: --qbo-only for QBO job
```

## Environment Variables in Cloud Run

```bash
# Regular vars
--set-env-vars=CORS_ORIGINS=https://app.example.com,ENVIRONMENT=production

# Secrets from Secret Manager
--set-secrets=SENDGRID_API_KEY=sendgrid-api-key:latest

# Cloud SQL
--add-cloudsql-instances=project:region:instance
```

## Multi-Stage Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:20 AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json .
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python API
FROM python:3.12-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY --from=frontend /app/frontend/dist /app/static
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Autoscaling

- Min instances: 1 (avoid cold starts for API)
- Max instances: 3 (cost control)
- Jobs: scale to 0 when idle

## Health Checks

Always expose `/api/health` endpoint for load balancer probes.

## Where Used

- **crumbl-ops**: Full Cloud Run deployment with API + sync jobs
