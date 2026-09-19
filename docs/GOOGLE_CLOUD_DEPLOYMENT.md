# Google Cloud deployment readiness

The selected application is the **React dashboard + RailPulser**, not Streamlit.
The old PowerShell script is deliberately blocked before any cloud command: it
previously deployed the wrong UI and granted unauthenticated access by default.
Local Docker instructions remain in [DOCKER.md](DOCKER.md).

## Can a hackathon account deploy it?

Yes, if the assigned project permits Cloud Run, Cloud Build and Artifact Registry,
has billing/credits enabled, and grants the relevant deployment, build and service
account permissions. A Google login alone does not establish these permissions.
Confirm the organiser's allowed region, quota, credit expiry and public-access policy.
Do not send credentials or service-account keys to collaborators or commit them.

Cloud Shell is a terminal for building/deploying, not the persistent app host.
Use Cloud Build + Artifact Registry + Cloud Run after adapting the application.
Cloud Run supports Compose deployment, but not every local Compose setting
translates unchanged; review supported fields and volume semantics.

## Remaining React deployment work

- Configure cloud ingress, frontend/backend networking and the actual HTTPS origin.
  The current assistant intentionally allows only localhost origins.
- Add authentication/authorization or an explicitly approved public-demo policy;
  uploading an image does not secure user files or API credentials.
- Replace process-local snapshots with user-scoped shared storage before horizontal
  scaling. One instance is only a pilot mitigation: restarts still lose snapshots.
- Package or securely provision Door's Normal reference and the dashboard Rail model.
  Local named volumes do not automatically appear in Cloud Run.
- Bound request sizes, concurrency, retention and spend; configure cleanup and
  ensure credentials/recordings are excluded from logs and build uploads.
- Build for the Cloud Run container contract, test all four upload paths and verify
  session isolation before distributing a public URL.

No Google Cloud resources have been created by this integration review.

Official references:
- https://docs.cloud.google.com/shell/docs/deploy-cloud-run-app
- https://docs.cloud.google.com/run/docs/deploying
- https://docs.cloud.google.com/run/docs/deploy-run-compose
