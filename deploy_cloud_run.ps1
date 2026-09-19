param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "asia-southeast1",
    [string]$Service = "railpulse-prototype",
    [string]$Repository = "railpulse"
)

$ErrorActionPreference = "Stop"
throw "Use Cloud Shell: bash deploy/deploy_cloud_run.sh PROJECT_ID REGION --public. See docs/GOOGLE_CLOUD_DEPLOYMENT.md. This legacy Streamlit script makes no cloud changes."
