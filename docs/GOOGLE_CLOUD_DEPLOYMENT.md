# Google Cloud Prototype

The unified RailPulse Streamlit app is packaged for Google Cloud Run. The image
contains the audited inference code and frozen model bundle, but excludes raw
training data and intermediate reports.

## Deploy from Windows PowerShell

Install and authenticate the Google Cloud CLI with the participant project, then
run these commands from the repository root:

```powershell
gcloud auth login
gcloud auth application-default login
.\deploy_cloud_run.ps1 -ProjectId YOUR_PARTICIPANT_PROJECT_ID
```

The script builds the image with Cloud Build, stores it in Artifact Registry,
deploys the public Cloud Run service, and prints the hosted prototype URL. Use
that printed `https://...run.app` value as **Link to Prototype** in the
hackathon submission.

The default region is `asia-southeast1`, but it can be changed when required by
the organiser's quota allocation:

```powershell
.\deploy_cloud_run.ps1 -ProjectId YOUR_PARTICIPANT_PROJECT_ID -Region asia-southeast1
```

The deployed app is intentionally unauthenticated so judges can open the link.
Do not upload raw datasets or secrets to the image. Uploaded recordings are
processed in memory-backed temporary storage and are not persisted by the app.