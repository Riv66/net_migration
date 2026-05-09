param (
    [string[]]$Regions
)

# =========================================================
# AWS Network Inventory Export
# =========================================================

$ErrorActionPreference = "Stop"

$OutputDir = Join-Path $PSScriptRoot "aws-network-inventory"

# ---------------------------------------------------------
# Validate AWS CLI
# ---------------------------------------------------------

try {
    $null = aws --version 2>$null
}
catch {
    Write-Host ""
    Write-Host "ERROR: AWS CLI not found."
    Write-Host "Install AWS CLI and ensure it is in PATH."
    exit 1
}

# ---------------------------------------------------------
# Validate AWS credentials
# ---------------------------------------------------------

try {
    $Identity = aws sts get-caller-identity --output json | ConvertFrom-Json

    Write-Host ""
    Write-Host "Authenticated AWS Account:"
    Write-Host "  Account : $($Identity.Account)"
    Write-Host "  ARN     : $($Identity.Arn)"
}
catch {
    Write-Host ""
    Write-Host "ERROR: AWS credentials are not configured or invalid."
    Write-Host $_
    exit 1
}

# ---------------------------------------------------------
# Discover enabled regions if none specified
# ---------------------------------------------------------

if (-not $Regions -or $Regions.Count -eq 0) {

    Write-Host ""
    Write-Host "No regions specified. Discovering enabled regions..."

    try {

        $RegionsRaw = aws ec2 describe-regions `
            --query "Regions[?OptInStatus=='opt-in-not-required'||OptInStatus=='opted-in'].RegionName" `
            --output text

        $Regions = $RegionsRaw -split '\s+'

        $Regions = $Regions | Where-Object { $_ -and $_.Trim() -ne "" }

        $Regions = $Regions | Sort-Object
    }
    catch {
        Write-Host "ERROR discovering AWS regions."
        Write-Host $_
        exit 1
    }
}

if (-not $Regions -or $Regions.Count -eq 0) {
    Write-Host "No AWS regions available."
    exit 1
}

# ---------------------------------------------------------
# Create output directory
# ---------------------------------------------------------

New-Item `
    -ItemType Directory `
    -Force `
    -Path $OutputDir | Out-Null

Write-Host ""
Write-Host "Processing $($Regions.Count) regions..."
Write-Host "Output directory:"
Write-Host "  $OutputDir"

# ---------------------------------------------------------
# Helper: Export AWS JSON safely
# ---------------------------------------------------------

function Export-AwsJson {

    param (
        [string]$AwsArgs,
        [string]$OutFile
    )

    $FullPath = Join-Path $RegionDir $OutFile

    Write-Host "  - Exporting $OutFile"

    try {

        # Execute AWS CLI directly
        $output = & aws @($AwsArgs -split ' ')

        if ($LASTEXITCODE -ne 0) {
            throw "AWS CLI returned exit code $LASTEXITCODE"
        }

        # Convert array output to string safely
        if ($output -is [System.Array]) {
            $output = $output -join [Environment]::NewLine
        }

        # Basic JSON validation
        try {
            $null = $output | ConvertFrom-Json
        }
        catch {
            throw "Invalid JSON returned from AWS CLI"
        }

        # Write UTF8 WITHOUT BOM
        $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

        [System.IO.File]::WriteAllText(
            $FullPath,
            $output,
            $Utf8NoBom
        )

        $size = (Get-Item $FullPath).Length

        Write-Host "    OK"
        Write-Host "    Saved ($size bytes)"
    }
    catch {

        Write-Host "    ERROR: $_"

        # Save empty valid JSON object
        [System.IO.File]::WriteAllText(
            $FullPath,
            "{}",
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

# ---------------------------------------------------------
# Export Loop
# ---------------------------------------------------------

$index = 1

foreach ($Region in $Regions) {

    Write-Host ""
    Write-Host "[$index/$($Regions.Count)] Region: $Region"

    $RegionDir = Join-Path $OutputDir $Region

    New-Item `
        -ItemType Directory `
        -Force `
        -Path $RegionDir | Out-Null

    # -----------------------------------------------------
    # Core Networking
    # -----------------------------------------------------

    Export-AwsJson `
        "ec2 describe-vpcs --region $Region --output json" `
        "vpcs.json"

    Export-AwsJson `
        "ec2 describe-subnets --region $Region --output json" `
        "subnets.json"

    Export-AwsJson `
        "ec2 describe-route-tables --region $Region --output json" `
        "route_tables.json"

    Export-AwsJson `
        "ec2 describe-internet-gateways --region $Region --output json" `
        "igws.json"

    Export-AwsJson `
        "ec2 describe-nat-gateways --region $Region --output json" `
        "nat.json"

    Export-AwsJson `
        "ec2 describe-security-groups --region $Region --output json" `
        "security_groups.json"

    Export-AwsJson `
        "ec2 describe-network-interfaces --region $Region --output json" `
        "network_interfaces.json"

    Export-AwsJson `
        "ec2 describe-vpc-peering-connections --region $Region --output json" `
        "vpc_peering.json"

    # -----------------------------------------------------
    # Transit Gateway Resources
    # -----------------------------------------------------

    Export-AwsJson `
        "ec2 describe-transit-gateways --region $Region --output json" `
        "tgws.json"

    Export-AwsJson `
        "ec2 describe-transit-gateway-attachments --region $Region --output json" `
        "tgw_attachments.json"

    # -----------------------------------------------------
    # Optional Additional Resources
    # -----------------------------------------------------

    Export-AwsJson `
        "ec2 describe-network-acls --region $Region --output json" `
        "network_acls.json"

    Export-AwsJson `
        "ec2 describe-vpc-endpoints --region $Region --output json" `
        "vpc_endpoints.json"

    Export-AwsJson `
        "ec2 describe-egress-only-internet-gateways --region $Region --output json" `
        "egress_only_igws.json"

    $index++
}

# ---------------------------------------------------------
# Validation Summary
# ---------------------------------------------------------

Write-Host ""
Write-Host "Validating exported JSON files..."

$BadFiles = @()

Get-ChildItem `
    -Path $OutputDir `
    -Recurse `
    -Filter *.json | ForEach-Object {

    try {

        $content = Get-Content $_.FullName -Raw

        $null = $content | ConvertFrom-Json
    }
    catch {

        $BadFiles += $_.FullName
    }
}

Write-Host ""

if ($BadFiles.Count -gt 0) {

    Write-Host "WARNING: Some files contain invalid JSON"

    foreach ($File in $BadFiles) {
        Write-Host "  $File"
    }
}
else {

    Write-Host "All JSON files validated successfully."
}

# ---------------------------------------------------------
# Complete
# ---------------------------------------------------------

Write-Host ""
Write-Host "Export complete."
Write-Host "Inventory saved to:"
Write-Host "  $OutputDir"
Write-Host ""
Write-Host "Ready for Python topology generation."
