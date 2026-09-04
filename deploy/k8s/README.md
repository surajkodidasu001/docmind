# Kubernetes deployment (untested against a real cluster)

These manifests are real, syntactically valid Kubernetes/KEDA config — but
they've only been validated with `kubectl --dry-run=client` in this
sandbox, not against a live cluster, because that needs an actual cloud
account or local cluster (kind/minikube) that doesn't exist here. Treat
this as a solid starting point, not a "deploy and forget" artifact — you'll
want to adjust resource requests/limits after watching real usage, and
plug in your actual container registry / secrets management.

## Files

- `deployment.yaml` — API + Streamlit UI deployments, each with resource
  requests/limits and liveness/readiness probes hitting `/api/health`
- `service.yaml` — ClusterIP services for both
- `secret.yaml.example` — template for `ANTHROPIC_API_KEY` etc. (copy to
  `secret.yaml`, fill in real values, **do not commit the real one**)
- `scaledobject.yaml` — KEDA ScaledObject that autoscales the API
  deployment based on HTTP request rate (via `keda-http-add-on`) rather
  than raw CPU, since this workload is I/O-bound (waiting on the Anthropic
  API) more than CPU-bound — CPU-based HPA would under-scale it

## Prerequisites this assumes

- A cluster with KEDA installed (`helm install keda kedacore/keda`)
- The `keda-http-add-on` scaler installed for HTTP-based scaling
- Your image pushed to a registry the cluster can pull from (replace
  `docmind:latest` in `deployment.yaml`)
- A real Qdrant deployment (or managed Qdrant Cloud) — the in-memory mode
  this repo defaults to doesn't survive pod restarts and can't be shared
  across replicas, which defeats the point of autoscaling

## Applying

```bash
kubectl create namespace docmind
kubectl -n docmind apply -f secret.yaml   # after filling in real values
kubectl -n docmind apply -f deployment.yaml -f service.yaml -f scaledobject.yaml
```
