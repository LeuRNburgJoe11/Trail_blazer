# Public judge-facing React deployment

This deploys React + FastAPI + RailPulser, not Streamlit. Cloud Shell is the
deployment terminal; Cloud Run hosts the service. Use the organiser's project.
Public access means anyone can call the app; anonymous cookies provide session
isolation, not identity verification.

## Cloud Shell (bash)

The reviewed files are on branch cloud01. Run:

    git clone --branch cloud01 https://github.com/LeuRNburgJoe11/Trail_blazer.git RailPulse_Cloud
    cd RailPulse_Cloud
    bash deploy/deploy_cloud_run.sh qwiklabs-gcp-04-ab0c86b13180 us-central1 --public

If the directory already exists, inspect it before pulling; do not overwrite local
edits. Git, gcloud and Python 3 are provided by Cloud Shell.

The script:
1. Enables Cloud Run, Artifact Registry, Cloud Build and IAM APIs.
2. Creates an image repository and a dedicated runtime service account with no
   project roles if absent. It does not grant broad roles to the build identity.
3. Builds the cloud Docker target for linux/amd64 using Cloud Build. Raw datasets,
   local environments and credentials are excluded from source upload.
4. Deploys privately, then configures the generated HTTPS origin.
5. Grants public invocation only after origin configuration succeeds.
6. Tests model availability, General chat and synthetic SHM upload + chat.

The final printed HTTPS URL is the judge-facing link. No provider key is needed
for local evidence answers. First build can take several minutes. Exact verified
definitions bypass paid generation even when a key is supplied.

## Required project access

Billing/credits must be enabled. The deployer needs API enablement, Cloud Build
submission, Artifact Registry management, Cloud Run deployment/IAM and service
account creation/use permissions. The configured Cloud Build identity needs
permission to build/push images. Lab policies may prohibit public invocation or
service-account creation. If a command fails, stop and share only the error text;
ask the organiser for the specific missing permission. Do not add a personal card
or grant Owner broadly.

The runtime identity has no project roles: models/references are baked into the
image, and the demo needs no cloud storage/database access. No Google password or
service-account key is stored.

## Public-demo boundaries

- Exact configured HTTPS host/origin; API POSTs must be same-origin.
- Secure, HttpOnly, SameSite=Strict anonymous cookies; snapshot capabilities are
  additionally bound to the browser session. No cross-user result browsing.
- 24 MiB total request limit, at most 8 files, bounded XLSX expanded size.
- 20 API requests per session/minute, 60 globally/minute and 2 simultaneous
  API executions per worker. These are demo safeguards, not full DDoS protection.
- Temporary upload/output directories removed after each request.
- Provider keys are not saved to disk or application logs. Optional generation
  sends compact selected evidence only. Do not enable external body logging.
- One worker; max one Cloud Run instance, concurrency 4, CPU 2, memory 2 GiB,
  timeout 240 seconds, min instances 0. Maximum instances is not a hard billing
  cap; transient overlapping revisions/instances can still occur.
- Sessions/results expire after an hour, eviction, restart or revision change.
  Rerun analysis if a snapshot is unavailable. This is NOT durable horizontal
  scaling and NOT an operational decision/safety service.
- Use non-sensitive hackathon data only. Lab expiry may delete the service.

The cloud image packages the Door reference and nested Rail model from
deploy/assets using training data only. Rail now displays the registered model's
measured mean fold CV (~0.632), not a hard-coded 0.792 pooled score.
See deploy/README.md for reproduction and provenance.

## Judge acceptance test

1. Open the printed URL. General should answer "What does SHM mean?"
2. Upload one valid file per subsystem. Run analysis, select a result in chat,
   and compare the explanation with the visible result.
3. Another private browser session must not see the first session's results.
   Copied snapshot tokens with another session cookie are rejected.
4. Optionally select a provider/model, enter your own key and consent, and ask
   for a result explanation. Check AI vs local-fallback labels; account access
   is required. No paid provider calls are performed by deployment smoke tests.
5. Do not upload sensitive data or treat predictions as safety clearance.

Local verification exercises all four inference/chat paths with official data
mounted read-only. The deployed smoke test uses synthetic SHM, not an accuracy
evaluation.

## Costs, diagnostics and shutdown

Build, registry storage and Cloud Run consume credits. Check credit expiry,
quotas and budget alerts with the organiser before distributing the URL.
No load tests are included. Inspect service status/logs in Cloud Console if needed.

To revoke public access (the service still exists):

    gcloud run services remove-iam-policy-binding railpulser-demo --region=us-central1 --member=allUsers --role=roles/run.invoker

To delete the service when finished:

    gcloud run services delete railpulser-demo --region=us-central1

Registry images/build storage may remain billable until separately cleaned up.
Do not delete the organiser's project. Production scaling needs authenticated
ownership, shared scoped snapshots, a durable upload lifecycle and stronger abuse
controls before increasing instances.

Official references:
- https://docs.cloud.google.com/shell/docs/deploy-cloud-run-app
- https://docs.cloud.google.com/run/docs/container-contract
- https://docs.cloud.google.com/build/docs/deploying-builds/deploy-cloud-run
