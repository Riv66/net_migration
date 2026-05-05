param (
    [string[]]$Regions
)

$OutputDir = "aws-network-inventory"

if (-not $Regions -or $Regions.Count -eq 0) {
    $Regions = (aws ec2 describe-regions --query "Regions[].RegionName" --output text).Split()
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($Region in $Regions) {
    $RegionDir = Join-Path $OutputDir $Region
    New-Item -ItemType Directory -Force -Path $RegionDir | Out-Null

    aws ec2 describe-vpcs --region $Region > "$RegionDir\vpcs.json"
    aws ec2 describe-subnets --region $Region > "$RegionDir\subnets.json"
    aws ec2 describe-route-tables --region $Region > "$RegionDir\route_tables.json"
    aws ec2 describe-internet-gateways --region $Region > "$RegionDir\igws.json"
    aws ec2 describe-nat-gateways --region $Region > "$RegionDir\nat.json"
}
