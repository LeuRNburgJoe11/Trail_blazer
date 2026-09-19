param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "asia-southeast1",
    [string]$Service = "railpulse-prototype",
    [string]$Repository = "railpulse"
)

$ErrorActionPreference = "Stop"
throw "Deployment paused: the former script published Streamlit, not React. See docs/GOOGLE_CLOUD_DEPLOYMENT.md. No cloud changes have been made."
