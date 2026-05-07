param (
    [string[]]$Regions
)

$OutputDir = "aws-network-inventory"

# Get enabled regions if none specified
if (-not $Regions -or $Regions.Count -eq 0) {

    Write-Host "No regions specified. Discovering enabled regions..."

    $RegionsRaw = aws ec2 describe-regions `
        --query "Regions[?OptInStatus=='opt-in-not-required'||OptInStatus=='opted-in'].RegionName" `
        --output text

    $Regions = $RegionsRaw.Split()
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "Processing $($Regions.Count) regions..."

$index = 1

foreach ($Region in $Regions) {

    Write-Host ""
    Write-Host "[$index/$($Regions.Count)] Region: $Region"

    $RegionDir = Join-Path $OutputDir $Region

    New-Item -ItemType Directory -Force -Path $RegionDir | Out-Null

    # Helper function
    function Export-AwsJson {
        param (
            [string]$Command,
            [string]$File
        )

        Write-Host "  - $File"

        try {

            $output = Invoke-Expression $Command

            $output | Set-Content `
                -Path "$RegionDir\$File" `
                -Encoding utf8

        }
        catch {

            Write-Host "    ERROR: $_"

            "{}" | Set-Content `
                -Path "$RegionDir\$File" `
                -Encoding utf8
        }
    }

    Export-AwsJson `
        "aws ec2 describe-vpcs --region $Region --output json" `
        "vpcs.json"

    Export-AwsJson `
        "aws ec2 describe-subnets --region $Region --output json" `
        "subnets.json"

    Export-AwsJson `
        "aws ec2 describe-route-tables --region $Region --output json" `
        "route_tables.json"

    Export-AwsJson `
        "aws ec2 describe-internet-gateways --region $Region --output json" `
        "igws.json"

    Export-AwsJson `
        "aws ec2 describe-nat-gateways --region $Region --output json" `
        "nat.json"

    Export-AwsJson `
        "aws ec2 describe-security-groups --region $Region --output json" `
        "security_groups.json"

    Export-AwsJson `
        "aws ec2 describe-network-interfaces --region $Region --output json" `
        "network_interfaces.json"

    Export-AwsJson `
        "aws ec2 describe-vpc-peering-connections --region $Region --output json" `
        "vpc_peering.json"

    # Optional TGW resources
    try {

        Export-AwsJson `
            "aws ec2 describe-transit-gateways --region $Region --output json" `
            "tgws.json"

        Export-AwsJson `
            "aws ec2 describe-transit-gateway-attachments --region $Region --output json" `
            "tgw_attachments.json"

    }
    catch {

        Write-Host "  - No Transit Gateway resources"
    }

    $index++
}

Write-Host ""
Write-Host "Export complete."
Write-Host "Output directory: $OutputDir"
