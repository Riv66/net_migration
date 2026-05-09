# generate_aws_connectivity_diagrams.py
#
# AWS-style connectivity diagrams from AWS inventory exports
#
# REQUIREMENTS
#
# pip install diagrams pillow
#
# Graphviz required:
# https://graphviz.org/download/
#
# Ensure dot.exe is in PATH on Windows
#
# INPUT STRUCTURE
#
# aws-network-inventory/
#   us-east-1/
#       vpcs.json
#       subnets.json
#       route_tables.json
#       igws.json
#       nat_gateways.json
#       security_groups.json
#       vpc_peering.json
#
# OUTPUT
#
# output/
#   us-east-1/
#       connectivity_vpc-xxxx.png
#
# FEATURES
#
# - AWS-style diagrams
# - Region grouping
# - VPC boundaries
# - AZ boundaries
# - Public/private subnet visualization
# - CIDR visibility
# - Route table relationships
# - NAT/IGW flows
# - Security group relationships
# - VPC peering visualization
# - Readable labels
# - Name tag prioritization

import json
import os
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.network import (
    VPC,
    PublicSubnet,
    PrivateSubnet,
    InternetGateway,
    NATGateway,
    RouteTable,
    VPCPeering,
)

from diagrams.aws.security import SecurityHub
from diagrams.onprem.network import Internet
from diagrams.generic.network import Router


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = "aws-network-inventory"
OUTPUT_DIR = "output"

Path(OUTPUT_DIR).mkdir(exist_ok=True)


# =========================================================
# HELPERS
# =========================================================

def load_json(path):

    if not os.path.exists(path):
        return {}

    try:

        with open(path, "r", encoding="utf-8-sig") as f:

            content = f.read().strip()

            if not content:
                return {}

            return json.loads(content)

    except Exception as e:

        print(f"Failed loading {path}: {e}")

        return {}


def get_name(tags, fallback="Unnamed"):
    """
    Prefer Name tag.
    """

    if not tags:
        return fallback

    for t in tags:

        if t.get("Key") == "Name":

            value = t.get("Value")

            if value and value.strip():
                return value.strip()

    return fallback


def short_id(resource_id):

    if not resource_id:
        return ""

    if len(resource_id) <= 12:
        return resource_id

    return resource_id[:12] + "..."


def subnet_display_name(subnet):

    subnet_id = subnet.get("SubnetId", "")

    name = get_name(
        subnet.get("Tags"),
        ""
    )

    cidr = subnet.get("CidrBlock", "")

    if name:
        return f"{name}\n{cidr}"

    return f"{short_id(subnet_id)}\n{cidr}"


def vpc_display_name(vpc):

    vpc_id = vpc.get("VpcId", "")

    name = get_name(
        vpc.get("Tags"),
        ""
    )

    cidr = vpc.get("CidrBlock", "")

    if name:
        return f"{name}\n{cidr}"

    return f"{short_id(vpc_id)}\n{cidr}"


def classify_subnet(subnet, route_tables):

    subnet_id = subnet.get("SubnetId")

    associated_rtb = None

    for rt in route_tables:

        for assoc in rt.get("Associations", []):

            if assoc.get("SubnetId") == subnet_id:
                associated_rtb = rt

    if not associated_rtb:
        return "private"

    for route in associated_rtb.get("Routes", []):

        gateway = route.get("GatewayId", "")

        if gateway.startswith("igw-"):
            return "public"

    return "private"


# =========================================================
# REGION SELECTION
# =========================================================

all_regions = sorted([
    d for d in os.listdir(BASE_DIR)
    if os.path.isdir(os.path.join(BASE_DIR, d))
])

print("\nAvailable regions:\n")

for r in all_regions:
    print(f" - {r}")

selection = input(
    "\nEnter regions separated by commas (blank = all regions): "
).strip()

if selection:

    REGIONS = [
        r.strip()
        for r in selection.split(",")
        if r.strip() in all_regions
    ]

else:

    REGIONS = all_regions

print("\nSelected regions:\n")

for r in REGIONS:
    print(f" - {r}")


# =========================================================
# BUILD DIAGRAMS
# =========================================================

for region in REGIONS:

    print(f"\nProcessing region: {region}")

    region_dir = os.path.join(BASE_DIR, region)

    output_region_dir = os.path.join(
        OUTPUT_DIR,
        region
    )

    Path(output_region_dir).mkdir(exist_ok=True)

    # =====================================================
    # LOAD DATA
    # =====================================================

    vpcs = load_json(
        os.path.join(region_dir, "vpcs.json")
    ).get("Vpcs", [])

    subnets = load_json(
        os.path.join(region_dir, "subnets.json")
    ).get("Subnets", [])

    route_tables = load_json(
        os.path.join(region_dir, "route_tables.json")
    ).get("RouteTables", [])

    igws = load_json(
        os.path.join(region_dir, "igws.json")
    ).get("InternetGateways", [])

    nat_gateways = load_json(
        os.path.join(region_dir, "nat_gateways.json")
    ).get("NatGateways", [])

    security_groups = load_json(
        os.path.join(region_dir, "security_groups.json")
    ).get("SecurityGroups", [])

    peerings = load_json(
        os.path.join(region_dir, "vpc_peering.json")
    ).get("VpcPeeringConnections", [])

    # =====================================================
    # PER VPC DIAGRAM
    # =====================================================

    for vpc in vpcs:

        vpc_id = vpc.get("VpcId")

        vpc_name = get_name(
            vpc.get("Tags"),
            vpc_id
        )

        print(f"  Building: {vpc_name}")

        filename = os.path.join(
            output_region_dir,
            f"connectivity_{vpc_id}"
        )

        with Diagram(
            name=f"{region} - {vpc_name}",
            filename=filename,
            outformat="png",
            show=False,
            direction="LR",
            graph_attr={

                "fontsize": "18",

                "pad": "0.5",

                "nodesep": "0.7",

                "ranksep": "1.2",

                "splines": "ortho",
            },
        ):

            internet = Internet("Internet")

            # =================================================
            # REGION
            # =================================================

            with Cluster(f"Region\n{region}"):

                # =============================================
                # VPC
                # =============================================

                with Cluster(
                    f"VPC\n{vpc_display_name(vpc)}"
                ):

                    router = Router("VPC Router")

                    # =========================================
                    # INTERNET GATEWAYS
                    # =========================================

                    vpc_igws = []

                    for igw in igws:

                        for att in igw.get(
                            "Attachments",
                            []
                        ):

                            if att.get("VpcId") != vpc_id:
                                continue

                            igw_id = igw.get(
                                "InternetGatewayId"
                            )

                            igw_node = InternetGateway(
                                f"Internet Gateway\n{short_id(igw_id)}"
                            )

                            vpc_igws.append(igw_node)

                            router >> igw_node >> internet

                    # =========================================
                    # NAT GATEWAYS
                    # =========================================

                    nat_nodes = {}

                    for nat in nat_gateways:

                        subnet_id = nat.get("SubnetId")

                        subnet = next(
                            (
                                s for s in subnets
                                if s.get("SubnetId") == subnet_id
                            ),
                            None
                        )

                        if not subnet:
                            continue

                        if subnet.get("VpcId") != vpc_id:
                            continue

                        nat_id = nat.get("NatGatewayId")

                        nat_node = NATGateway(
                            f"NAT Gateway\n{short_id(nat_id)}"
                        )

                        nat_nodes[nat_id] = nat_node

                    # =========================================
                    # SUBNETS
                    # =========================================

                    vpc_subnets = [
                        s for s in subnets
                        if s.get("VpcId") == vpc_id
                    ]

                    az_map = {}

                    for subnet in vpc_subnets:

                        az = subnet.get(
                            "AvailabilityZone",
                            "unknown-az"
                        )

                        az_map.setdefault(
                            az,
                            []
                        ).append(subnet)

                    # =========================================
                    # AZ CLUSTERS
                    # =========================================

                    for az, az_subnets in az_map.items():

                        with Cluster(
                            f"Availability Zone\n{az}"
                        ):

                            for subnet in az_subnets:

                                subnet_id = subnet.get(
                                    "SubnetId"
                                )

                                subnet_type = classify_subnet(
                                    subnet,
                                    route_tables
                                )

                                label = subnet_display_name(
                                    subnet
                                )

                                # =================================
                                # SUBNET NODE
                                # =================================

                                if subnet_type == "public":

                                    subnet_node = PublicSubnet(
                                        label
                                    )

                                else:

                                    subnet_node = PrivateSubnet(
                                        label
                                    )

                                # =================================
                                # ROUTE TABLES
                                # =================================

                                subnet_rt = None

                                for rt in route_tables:

                                    for assoc in rt.get(
                                        "Associations",
                                        []
                                    ):

                                        if assoc.get(
                                            "SubnetId"
                                        ) == subnet_id:

                                            subnet_rt = rt

                                if subnet_rt:

                                    rt_id = subnet_rt.get(
                                        "RouteTableId"
                                    )

                                    rt_node = RouteTable(
                                        f"Route Table\n{short_id(rt_id)}"
                                    )

                                    subnet_node >> rt_node

                                    rt_node >> router

                                    # =============================
                                    # NAT ROUTES
                                    # =============================

                                    for route in subnet_rt.get(
                                        "Routes",
                                        []
                                    ):

                                        nat_id = route.get(
                                            "NatGatewayId"
                                        )

                                        if nat_id in nat_nodes:

                                            rt_node >> nat_nodes[nat_id]

                                # =================================
                                # SECURITY GROUPS
                                # =================================

                                subnet_sgs = [
                                    sg for sg in security_groups
                                    if sg.get("VpcId") == vpc_id
                                ]

                                # limit SG rendering
                                for sg in subnet_sgs[:3]:

                                    sg_name = get_name(
                                        sg.get("Tags"),
                                        sg.get("GroupName")
                                    )

                                    sg_id = sg.get(
                                        "GroupId"
                                    )

                                    sg_node = SecurityHub(
                                        f"{sg_name}\n{short_id(sg_id)}"
                                    )

                                    subnet_node - Edge(
                                        style="dashed"
                                    ) - sg_node

                    # =========================================
                    # PEERING
                    # =========================================

                    for peer in peerings:

                        requester = peer.get(
                            "RequesterVpcInfo",
                            {}
                        ).get("VpcId")

                        accepter = peer.get(
                            "AccepterVpcInfo",
                            {}
                        ).get("VpcId")

                        if vpc_id not in [
                            requester,
                            accepter
                        ]:
                            continue

                        peer_id = peer.get(
                            "VpcPeeringConnectionId"
                        )

                        peer_node = VPCPeering(
                            f"Peering\n{short_id(peer_id)}"
                        )

                        router >> peer_node

        print(f"    Saved: {filename}.png")

print("\nDiagram generation complete.")
print(f"Output folder: {OUTPUT_DIR}")