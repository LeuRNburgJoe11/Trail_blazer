param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "asia-southeast1",
    [string]$Service = "railpulse-prototype",
    [string]$Repository = "railpulse"
)

$ErrorActionPreference = "Stop"
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/$Service`:latest"

gcloud config set project $ProjectId
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories describe $Repository --location=$Region 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud artifacts repositories create $Repository --repository-format=docker --location=$Region --description="RailPulse prototype images"
}
gcloud builds submit --tag $Image .
gcloud run deploy $Service --image $Image --region $Region --platform managed --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 900 --max-instances 2
gcloud run services describe $Service --region $Region --format="value(status.url)"