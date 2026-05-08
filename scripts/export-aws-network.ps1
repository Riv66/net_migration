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

    function Export-AwsJson {

        param (
            [string]$Command,
            [string]$File,
            [string]$EmptyRootKey
        )

        $FilePath = Join-Path $RegionDir $File

        Write-Host "  - Exporting $File"

        try {

            # Execute AWS CLI
            $output = Invoke-Expression $Command 2>&1

            # Detect AWS CLI errors
            if ($LASTEXITCODE -ne 0) {

                throw $output
            }

            # Validate JSON before writing
            try {

                $parsed = $output | ConvertFrom-Json

                # Write normalized JSON
                $parsed | ConvertTo-Json -Depth 100 | Set-Content `
                    -Path $FilePath `
                    -Encoding utf8

                Write-Host "    OK"

            }
            catch {

                Write-Host "    INVALID JSON RETURNED"

                # Create valid empty structure
                $emptyObject = @{
                    $EmptyRootKey = @()
                }

                $emptyObject | ConvertTo-Json -Depth 5 | Set-Content `
                    -Path $FilePath `
                    -Encoding utf8

                Write-Host "    Wrote empty fallback JSON"
            }
        }
        catch {

            Write-Host "    ERROR: $_"

            # Always write VALID JSON
            $emptyObject = @{
                $EmptyRootKey = @()
            }

            $emptyObject | ConvertTo-Json -Depth 5 | Set-Content `
                -Path $FilePath `
                -Encoding utf8
        }

        # Verify file exists and size
        if (Test-Path $FilePath) {

            $size = (Get-Item $FilePath).Length

            Write-Host "    Saved ($size bytes)"
        }
        else {

            Write-Host "    FAILED TO CREATE FILE"
        }
    }

    Export-AwsJson `
        "aws ec2 describe-vpcs --region $Region --output json" `
        "vpcs.json" `
        "Vpcs"

    Export-AwsJson `
        "aws ec2 describe-subnets --region $Region --output json" `
        "subnets.json" `
        "Subnets"

    Export-AwsJson `
        "aws ec2 describe-route-tables --region $Region --output json" `
        "route_tables.json" `
        "RouteTables"

    Export-AwsJson `
        "aws ec2 describe-internet-gateways --region $Region --output json" `
        "igws.json" `
        "InternetGateways"

    Export-AwsJson `
        "aws ec2 describe-nat-gateways --region $Region --output json" `
        "nat_gateways.json" `
        "NatGateways"

    Export-AwsJson `
        "aws ec2 describe-security-groups --region $Region --output json" `
        "security_groups.json" `
        "SecurityGroups"

    Export-AwsJson `
        "aws ec2 describe-network-interfaces --region $Region --output json" `
        "network_interfaces.json" `
        "NetworkInterfaces"

    Export-AwsJson `
        "aws ec2 describe-vpc-peering-connections --region $Region --output json" `
        "vpc_peering.json" `
        "VpcPeeringConnections"

    # Transit Gateway resources
    Export-AwsJson `
        "aws ec2 describe-transit-gateways --region $Region --output json" `
        "tgws.json" `
        "TransitGateways"

    Export-AwsJson `
        "aws ec2 describe-transit-gateway-attachments --region $Region --output json" `
        "tgw_attachments.json" `
        "TransitGatewayAttachments"

    $index++
}

Write-Host ""
Write-Host "Export complete."
Write-Host "Output directory: $OutputDir"
