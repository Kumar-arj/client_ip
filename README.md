# client_ip — IP Echo App

A tiny web service that tells you your own IP address. Send it an HTTP request and it replies with your IP in JSON. It also exposes health and readiness endpoints used by Kubernetes to monitor the app.

Built as part of the DevOps Assignment.

---

## What the app does

| Endpoint | What it returns |
|----------|-----------------|
| `GET /` | Your originating IP address: `{"ip": "1.2.3.4"}`. Works correctly behind proxies and load balancers (reads `X-Forwarded-For`). |
| `GET /health` | `{"status": "ok"}` — used by Kubernetes to check if the app is alive |
| `GET /ready` | `{"status": "ready"}` — used by Kubernetes to check if the app can accept traffic |

---

## Run Locally

Choose **one** of the three options below depending on what you have installed.

---

### Option 1 — Python only (simplest)

**What you need:** Python 3.12 or newer ([download here](https://www.python.org/downloads/))

```bash
# Clone the repo (if you haven't already)
git clone https://github.com/Kumar-arj/client_ip.git
cd client_ip

# Create an isolated Python environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start the app
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

The app is now running at **http://localhost:8080**. Open a second terminal and test it:

```bash
curl http://localhost:8080/         # {"ip":"127.0.0.1"}
curl http://localhost:8080/health   # {"status":"ok"}
curl http://localhost:8080/ready    # {"status":"ready"}
```

Press `Ctrl+C` in the first terminal to stop the app.

---

### Option 2 — Docker

**What you need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# Build the image
docker build -t client_ip:local .

# Run the container (port 8080 on your machine → port 8080 in the container)
docker run -p 8080:8080 client_ip:local
```

Test the same URLs as above. Press `Ctrl+C` to stop.

---

### Option 3 — Kubernetes with kind (advanced)

**What you need:** Docker, plus the following tools:

```bash
# Install kind (local Kubernetes)
brew install kind          # macOS
# Windows/Linux: https://kind.sigs.k8s.io/docs/user/quick-start/#installation

# Install Helm (Kubernetes package manager)
brew install helm          # macOS
# Windows/Linux: https://helm.sh/docs/intro/install/

# Install kubectl (Kubernetes CLI) — if not already present
brew install kubectl       # macOS
# Windows/Linux: https://kubernetes.io/docs/tasks/tools/
```

Once all tools are installed:

```bash
# 1. Create a local Kubernetes cluster
kind create cluster --name local

# 2. Build the Docker image and load it into the cluster
docker build -t client_ip:local .
kind load docker-image client_ip:local --name local

# 3. Deploy with Helm
helm upgrade --install ip-app charts/ip-app/ \
  --set image.repository=client_ip \
  --set image.tag=local \
  --set image.pullPolicy=Never

# 4. Wait for the app to start (usually ~10 seconds)
kubectl rollout status deployment/ip-app --timeout=2m

# 5. Forward a local port and test
kubectl port-forward svc/ip-app 8080:80 &
curl http://localhost:8080/health

# 6. Clean up when done
kill %1                          # stop port-forward
kind delete cluster --name local # delete the cluster
```

---

## Run Tests

Make sure you are in the project folder with the virtual environment active:

```bash
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

Expected output: **5 tests passed**, ~86% coverage.

---

## How the Docker image is built

The `Dockerfile` uses a **two-stage build** to keep the final image as small as possible:

1. **Build stage** — installs all Python dependencies into a separate folder (`/install`)
2. **Runtime stage** — starts from a clean minimal Python image, copies only the installed packages, and runs the app as a non-root user (`appuser`) for security

A `.dockerignore` file prevents test files, the virtual environment, and other development artefacts from being included in the image.

---

## Helm Chart

The Helm chart lives in `charts/ip-app/` and packages everything Kubernetes needs to run the app:

- **Deployment** — runs the container, configured replica count
- **Service** — exposes the app inside the cluster (port 80 → container port 8080)
- **Probes** — liveness, readiness, and startup probes, all tunable in `values.yaml`
- **Resources** — CPU and memory requests/limits with sensible defaults in `values.yaml`

### Passing secrets to the app

Secrets are **never** stored in the chart or `values.yaml`. Use one of these approaches:

```bash
# Option A — standard Kubernetes Secret (simplest)
kubectl create secret generic app-secrets \
  --from-literal=MY_KEY=my_value

# Option B — Sealed Secrets (safe to commit to Git)
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# Option C — External Secrets Operator
# Pulls secrets from AWS Secrets Manager, HashiCorp Vault, etc.
```

Then tell the app to load them by editing `charts/ip-app/values.yaml`:

```yaml
secrets:
  enabled: true
  name: app-secrets   # must match the secret name you created above
```

### Validate the chart

```bash
helm lint charts/ip-app/ --strict
```

---

## CI/CD Pipeline

File: `.github/workflows/ci.yaml`
Runs automatically on every push and pull request to `main` or `develop`.

### Stages (in order)

```
lint → test → build → scan → helm-lint → deploy → smoke-test → notify
```

| Stage | What happens |
|-------|--------------|
| **lint** | Checks code style with `flake8` |
| **test** | Runs all unit tests with `pytest`; uploads coverage to Codecov |
| **build** | Builds the Docker image and pushes it to GHCR (GitHub's container registry) |
| **scan** | Scans the image for known security vulnerabilities using Trivy; results appear in the GitHub Security tab |
| **helm-lint** | Validates the Helm chart with `helm lint --strict` |
| **deploy** | Spins up a temporary Kubernetes cluster (kind), deploys the app via Helm |
| **smoke-test** | Sends `curl` requests to `/health`, `/ready`, and `/` — fails the pipeline if any return an error |
| **notify** | Prints a ✅ or ❌ summary with the commit SHA and branch name |

All the shell scripts in the pipeline are stored as reusable **composite actions** in `.github/actions/` so they can be maintained and tested independently.

### Published image

Every successful push to `main` publishes the image to GitHub Container Registry:

```
ghcr.io/kumar-arj/client_ip:latest          ← always the newest main build
ghcr.io/kumar-arj/client_ip:main            ← branch tag
ghcr.io/kumar-arj/client_ip:<commit-sha>    ← exact build, e.g. ghcr.io/kumar-arj/client_ip:3a7f1c2...
```

Pull it with:

```bash
docker pull ghcr.io/kumar-arj/client_ip:latest
```

### Vulnerability scanning

Trivy scans the exact image digest (not a tag) that was just pushed, so there is no risk of scanning a different image. Findings at CRITICAL or HIGH severity are uploaded as SARIF to **GitHub → Security → Code scanning alerts**.

---

## Project structure

```
client_ip/
├── app/
│   └── main.py              # The FastAPI web application
├── tests/
│   └── test_app.py          # Automated tests (pytest)
├── charts/
│   └── ip-app/              # Helm chart for Kubernetes deployment
│       ├── Chart.yaml       # Chart metadata
│       ├── values.yaml      # All configurable settings
│       └── templates/       # Kubernetes resource templates
├── .github/
│   ├── workflows/
│   │   └── ci.yaml          # CI/CD pipeline definition
│   └── actions/             # Reusable pipeline building blocks
│       ├── lint-python/
│       ├── test-python/
│       ├── helm-lint/
│       ├── helm-deploy/
│       ├── load-image-kind/
│       ├── smoke-tests/
│       └── ...
├── Dockerfile               # Multi-stage container build
├── .dockerignore            # Files excluded from the Docker build
└── requirements.txt         # Python dependencies
```


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

