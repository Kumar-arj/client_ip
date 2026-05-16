# client_ip — IP Echo App

A minimal FastAPI service that returns the client's originating IP address. Built as part of the BigID DevOps Home Assignment.

---

## Endpoints

| Endpoint  | Description |
|-----------|-------------|
| `GET /`   | Returns the client's originating IP as JSON: `{"ip": "1.2.3.4"}`. Respects `X-Forwarded-For` when behind a proxy or load balancer. |
| `GET /health` | Liveness probe — returns `{"status": "ok"}` |
| `GET /ready`  | Readiness probe — returns `{"status": "ready"}` |

---

## Run Locally

### Prerequisites

- Python 3.12+, or Docker, or a local Kubernetes cluster (kind / minikube)

### Python (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Test it:

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

### Docker

```bash
docker build -t client_ip:local .
docker run -p 8080:8080 client_ip:local
```

### kind (Kubernetes locally)

```bash
# Create cluster
kind create cluster --name local

# Build and load image
docker build -t client_ip:local .
kind load docker-image client_ip:local --name local

# Deploy with Helm
helm upgrade --install ip-app charts/ip-app/ \
  --set image.repository=client_ip \
  --set image.tag=local \
  --set image.pullPolicy=Never

# Forward port and test
kubectl port-forward svc/ip-app 8080:80 &
curl http://localhost:8080/health
```

---

## Run Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

---

## Dockerfile

Multi-stage build for a minimal runtime image:

- **Stage 1 (builder):** installs dependencies with `pip install --prefix=/install` into an isolated directory
- **Stage 2 (runtime):** copies only the installed packages into `/usr/local`, runs as non-root user `appuser` (UID 1000)

A `.dockerignore` is used to exclude tests, `.venv`, and other dev artefacts from the build context.

---

## Helm Chart

Located in `charts/ip-app/`. The chart includes:

- `Deployment` with configurable replica count
- `Service` (ClusterIP, port 80 → container 8080)
- Liveness, readiness, and startup probes — all configurable via `values.yaml`
- Resource `requests` and `limits` with sensible defaults
- No hardcoded secrets

### Providing secrets

Do **not** put secrets in `values.yaml`. Use one of:

```bash
# Option 1 — plain Kubernetes Secret
kubectl create secret generic app-secrets \
  --from-literal=MY_KEY=my_value

# Option 2 — Sealed Secrets (GitOps-safe)
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# Option 3 — External Secrets Operator
# Point ExternalSecret at AWS Secrets Manager / Vault / etc.
```

Then enable in `values.yaml`:

```yaml
secrets:
  enabled: true
  name: app-secrets
```

### Lint the chart

```bash
helm lint charts/ip-app/ --strict
```

---

## CI/CD Pipeline

File: `.github/workflows/ci.yaml`  
Triggers on every push and pull request to `main` or `develop`.

### Pipeline stages

```
lint → test → build → scan → helm-lint → deploy → smoke-test → notify
```

| Job | What it does |
|-----|--------------|
| **lint** | Runs `flake8` (max line length 120) |
| **test** | Runs `pytest` with coverage; uploads report to Codecov |
| **build** | Multi-stage Docker build; pushes to GHCR tagged with commit SHA, branch name, and `latest` |
| **scan** | Trivy image vulnerability scan (CRITICAL + HIGH); uploads SARIF to GitHub Security tab |
| **helm-lint** | `helm lint --strict` on the chart |
| **deploy** | Creates a kind cluster, loads image, deploys via Helm to `staging` namespace |
| **smoke-test** | `curl` checks on `/health`, `/ready`, and `/` via `kubectl port-forward` |
| **notify** | Prints pipeline status (✅/❌) with commit and branch info |

All shell scripts are extracted into reusable **composite actions** under `.github/actions/`.

### Image registry

Images are published to GitHub Container Registry (GHCR):

```
ghcr.io/kumar-arj/client_ip:<commit-sha>
ghcr.io/kumar-arj/client_ip:main
ghcr.io/kumar-arj/client_ip:latest
```

### Image scan

Trivy scans the pushed image for CRITICAL and HIGH CVEs. Results are uploaded as SARIF to the **GitHub Security → Code scanning** tab. The scan step uses the image digest (not a mutable tag) to guarantee the exact pushed image is scanned.

---

## Project Structure

```
.
├── app/
│   └── main.py              # FastAPI application
├── tests/
│   └── test_app.py          # Pytest unit tests
├── charts/
│   └── ip-app/              # Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── .github/
│   ├── workflows/
│   │   └── ci.yaml          # CI/CD pipeline
│   └── actions/             # Reusable composite actions
│       ├── lint-python/
│       ├── test-python/
│       ├── set-image-ref/
│       ├── helm-lint/
│       ├── helm-deploy/
│       ├── load-image-kind/
│       ├── create-namespace/
│       ├── wait-rollout/
│       ├── smoke-tests/
│       ├── debug-pods/
│       ├── scan-report/
│       └── notify-status/
├── Dockerfile
├── requirements.txt
└── README.md
```

