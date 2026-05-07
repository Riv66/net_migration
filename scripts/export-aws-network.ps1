param (
    [string[]]$Regions
)

$OutputDir = "aws-network-inventory"

# If no regions provided → fetch only enabled/active regions
if (-not $Regions -or $Regions.Count -eq 0) {
    Write-Host "No regions specified. Fetching enabled regions only..."

    $RegionsRaw = aws ec2 describe-regions `
        --query "Regions[?OptInStatus=='opt-in-not-required'||OptInStatus=='opted-in'].RegionName" `
        --output text

    $Regions = $RegionsRaw.Split()
} else {
    Write-Host "Using provided regions: $($Regions -join ', ')"
}

# Create output directory
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "Total regions to process: $($Regions.Count)"
Write-Host "Starting export..."

$index = 1

foreach ($Region in $Regions) {
    Write-Host "[$index/$($Regions.Count)] Processing region: $Region"

    $RegionDir = Join-Path $OutputDir $Region
    New-Item -ItemType Directory -Force -Path $RegionDir | Out-Null

    Write-Host "  - VPCs"
    aws ec2 describe-vpcs --region $Region > "$RegionDir\vpcs.json"

    Write-Host "  - Subnets"
    aws ec2 describe-subnets --region $Region > "$RegionDir\subnets.json"

    Write-Host "  - Route Tables"
    aws ec2 describe-route-tables --region $Region > "$RegionDir\route_tables.json"

    Write-Host "  - Internet Gateways"
    aws ec2 describe-internet-gateways --region $Region > "$RegionDir\igws.json"

    Write-Host "  - NAT Gateways (may be slow)"
    aws ec2 describe-nat-gateways --region $Region > "$RegionDir\nat.json"

    Write-Host "  ✔ Completed region: $Region"
    $index++
                        }

Write-Host "Export complete. Output in '$OutputDir'"
