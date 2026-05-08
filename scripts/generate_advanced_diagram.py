#!/usr/bin/env python3
"""
AWS Network Topology Diagram Generator
--------------------------------------

Features
--------
- Interactive region selection
- Per-region detailed diagrams
- Global overview split into grouped pages
- Adds Name tags to all resources where available
- Dependency-focused relationships
- Readable layouts
- Transit Gateway + Peering support
- Multi-page outputs

Outputs
-------
output/
├── overview_ap.png
├── overview_eu.png
├── overview_us.png
├── region_us-east-1.png
├── region_eu-west-2.png
└── ...

Requirements
------------
pip install matplotlib networkx pillow
"""

import json
import os
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import networkx as nx


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = "aws-network-inventory"
OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# HELPERS
# ============================================================


def load_json(path):
    """
    Robust JSON loader
    Handles UTF-8 BOM and empty files
    """

    if not os.path.exists(path):
        print(f"Missing: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = f.read().strip()

            if not raw:
                return {}

            return json.loads(raw)

    except Exception as e:
        print(f"Failed to load {path}: {e}")
        return {}


def get_name_tag(tags, fallback="Unnamed"):
    if not tags:
        return fallback

    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value")

    return fallback


def short_name(resource_id, name):
    if name and name != "Unnamed":
        return f"{name}\n({resource_id})"
    return resource_id


def ensure_list(value):
    if value is None:
        return []
    return value


# ============================================================
# REGION INPUT
# ============================================================

all_regions = sorted([
    d.name for d in Path(BASE_DIR).iterdir()
    if d.is_dir()
])

print("\nAvailable regions:")
for r in all_regions:
    print(f" - {r}")

user_input = input(
    "\nEnter regions separated by commas "
    "(blank = all regions): "
).strip()

if user_input:
    selected_regions = [
        r.strip()
        for r in user_input.split(",")
        if r.strip() in all_regions
    ]
else:
    selected_regions = all_regions

print("\nSelected regions:")
for r in selected_regions:
    print(f" - {r}")


# ============================================================
# REGION GROUPING
# ============================================================

grouped_regions = defaultdict(list)

for region in selected_regions:

    if region.startswith("eu-"):
        grouped_regions["eu"].append(region)

    elif region.startswith("us-"):
        grouped_regions["us"].append(region)

    elif region.startswith("ap-"):
        grouped_regions["ap"].append(region)

    elif region.startswith("ca-"):
        grouped_regions["ca"].append(region)

    elif region.startswith("sa-"):
        grouped_regions["sa"].append(region)

    else:
        grouped_regions["other"].append(region)


# ============================================================
# GLOBAL OVERVIEW PAGES
# ============================================================

for group_name, regions in grouped_regions.items():

    print(f"\nBuilding overview page: {group_name}")

    G = nx.Graph()

    for region in regions:

        region_path = Path(BASE_DIR) / region

        vpcs = load_json(region_path / "vpcs.json").get("Vpcs", [])
        peerings = load_json(region_path / "vpc_peering.json").get(
            "VpcPeeringConnections", []
        )

        # REGION NODE
        G.add_node(
            region,
            label=region,
            color="lightblue",
            size=3000
        )

        # VPCS
        for vpc in vpcs:

            vpc_id = vpc.get("VpcId")

            name = get_name_tag(vpc.get("Tags"))

            cidr = vpc.get("CidrBlock")

            label = f"{name}\n{vpc_id}\n{cidr}"

            G.add_node(
                vpc_id,
                label=label,
                color="lightgreen",
                size=2000
            )

            G.add_edge(region, vpc_id)

        # PEERING
        for peer in peerings:

            requester = peer.get("RequesterVpcInfo", {}).get("VpcId")
            accepter = peer.get("AccepterVpcInfo", {}).get("VpcId")

            if requester and accepter:
                G.add_edge(
                    requester,
                    accepter,
                    style="dashed"
                )

    plt.figure(figsize=(18, 14))

    pos = nx.spring_layout(G, seed=42, k=2)

    node_colors = [
        G.nodes[n].get("color", "gray")
        for n in G.nodes
    ]

    node_sizes = [
        G.nodes[n].get("size", 1000)
        for n in G.nodes
    ]

    labels = {
        n: G.nodes[n].get("label", n)
        for n in G.nodes
    }

    nx.draw_networkx_nodes(
        G,
        pos,
        node_color=node_colors,
        node_size=node_sizes
    )

    nx.draw_networkx_edges(
        G,
        pos
    )

    nx.draw_networkx_labels(
        G,
        pos,
        labels,
        font_size=8
    )

    plt.title(f"AWS Global Overview ({group_name.upper()})")

    plt.axis("off")

    output_file = (
        Path(OUTPUT_DIR) /
        f"overview_{group_name}.png"
    )

    plt.savefig(
        output_file,
        bbox_inches="tight",
        dpi=300
    )

    plt.close()

    print(f"Saved: {output_file}")


# ============================================================
# DETAILED REGION PAGES
# ============================================================

for region in selected_regions:

    print(f"\nProcessing region: {region}")

    region_path = Path(BASE_DIR) / region

    # ========================================================
    # LOAD RESOURCES
    # ========================================================

    vpcs = load_json(region_path / "vpcs.json").get("Vpcs", [])

    subnets = load_json(region_path / "subnets.json").get("Subnets", [])

    route_tables = load_json(
        region_path / "route_tables.json"
    ).get("RouteTables", [])

    igws = load_json(
        region_path / "igws.json"
    ).get("InternetGateways", [])

    nat_gateways = load_json(
        region_path / "nat_gateways.json"
    ).get("NatGateways", [])

    if not nat_gateways:
        nat_gateways = load_json(
            region_path / "nat.json"
        ).get("NatGateways", [])

    security_groups = load_json(
        region_path / "security_groups.json"
    ).get("SecurityGroups", [])

    peerings = load_json(
        region_path / "vpc_peering.json"
    ).get("VpcPeeringConnections", [])

    tgws = load_json(
        region_path / "tgws.json"
    ).get("TransitGateways", [])

    tgw_attachments = load_json(
        region_path / "tgw_attachments.json"
    ).get("TransitGatewayAttachments", [])

    # ========================================================
    # GRAPH
    # ========================================================

    G = nx.DiGraph()

    # REGION ROOT
    G.add_node(
        region,
        label=region,
        color="skyblue",
        size=4000
    )

    # ========================================================
    # VPCS
    # ========================================================

    for vpc in vpcs:

        vpc_id = vpc.get("VpcId")

        name = get_name_tag(vpc.get("Tags"))

        cidr = vpc.get("CidrBlock")

        label = (
            f"VPC\n{name}\n"
            f"{vpc_id}\n"
            f"{cidr}"
        )

        G.add_node(
            vpc_id,
            label=label,
            color="lightgreen",
            size=3000
        )

        G.add_edge(region, vpc_id)

    # ========================================================
    # SUBNETS
    # ========================================================

    for subnet in subnets:

        subnet_id = subnet.get("SubnetId")

        vpc_id = subnet.get("VpcId")

        az = subnet.get("AvailabilityZone")

        cidr = subnet.get("CidrBlock")

        name = get_name_tag(subnet.get("Tags"))

        label = (
            f"Subnet\n{name}\n"
            f"{subnet_id}\n"
            f"{az}\n"
            f"{cidr}"
        )

        G.add_node(
            subnet_id,
            label=label,
            color="orange",
            size=1800
        )

        G.add_edge(vpc_id, subnet_id)

    # ========================================================
    # ROUTE TABLES
    # ========================================================

    for rt in route_tables:

        rt_id = rt.get("RouteTableId")

        vpc_id = rt.get("VpcId")

        label = f"RT\n{rt_id}"

        G.add_node(
            rt_id,
            label=label,
            color="violet",
            size=1500
        )

        G.add_edge(vpc_id, rt_id)

        for assoc in ensure_list(rt.get("Associations")):

            subnet_id = assoc.get("SubnetId")

            if subnet_id:
                G.add_edge(rt_id, subnet_id)

    # ========================================================
    # INTERNET GATEWAYS
    # ========================================================

    for igw in igws:

        igw_id = igw.get("InternetGatewayId")

        label = f"IGW\n{igw_id}"

        G.add_node(
            igw_id,
            label=label,
            color="red",
            size=2000
        )

        for attach in ensure_list(igw.get("Attachments")):

            vpc_id = attach.get("VpcId")

            if vpc_id:
                G.add_edge(vpc_id, igw_id)

    # ========================================================
    # NAT GATEWAYS
    # ========================================================

    for nat in nat_gateways:

        nat_id = nat.get("NatGatewayId")

        subnet_id = nat.get("SubnetId")

        label = f"NAT\n{nat_id}"

        G.add_node(
            nat_id,
            label=label,
            color="yellow",
            size=2000
        )

        if subnet_id:
            G.add_edge(subnet_id, nat_id)

    # ========================================================
    # SECURITY GROUPS
    # ========================================================

    for sg in security_groups:

        sg_id = sg.get("GroupId")

        vpc_id = sg.get("VpcId")

        name = sg.get("GroupName")

        inbound = len(
            ensure_list(sg.get("IpPermissions"))
        )

        outbound = len(
            ensure_list(sg.get("IpPermissionsEgress"))
        )

        label = (
            f"SG\n{name}\n"
            f"{sg_id}\n"
            f"In:{inbound} Out:{outbound}"
        )

        G.add_node(
            sg_id,
            label=label,
            color="pink",
            size=1500
        )

        if vpc_id:
            G.add_edge(vpc_id, sg_id)

    # ========================================================
    # PEERING
    # ========================================================

    for peer in peerings:

        requester = peer.get(
            "RequesterVpcInfo", {}
        ).get("VpcId")

        accepter = peer.get(
            "AccepterVpcInfo", {}
        ).get("VpcId")

        if requester and accepter:
            G.add_edge(
                requester,
                accepter
            )

    # ========================================================
    # TGW
    # ========================================================

    for tgw in tgws:

        tgw_id = tgw.get("TransitGatewayId")

        label = f"TGW\n{tgw_id}"

        G.add_node(
            tgw_id,
            label=label,
            color="cyan",
            size=3000
        )

    for att in tgw_attachments:

        tgw_id = att.get("TransitGatewayId")

        resource_id = att.get("ResourceId")

        if tgw_id and resource_id:
            G.add_edge(tgw_id, resource_id)

    # ========================================================
    # DRAW
    # ========================================================

    plt.figure(figsize=(26, 18))

    pos = nx.spring_layout(
        G,
        seed=42,
        k=2.5
    )

    node_colors = [
        G.nodes[n].get("color", "gray")
        for n in G.nodes
    ]

    node_sizes = [
        G.nodes[n].get("size", 1000)
        for n in G.nodes
    ]

    labels = {
        n: G.nodes[n].get("label", n)
        for n in G.nodes
    }

    nx.draw_networkx_nodes(
        G,
        pos,
        node_color=node_colors,
        node_size=node_sizes
    )

    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True
    )

    nx.draw_networkx_labels(
        G,
        pos,
        labels,
        font_size=7
    )

    plt.title(
        f"AWS Dependency Map - {region}",
        fontsize=18
    )

    plt.axis("off")

    output_file = (
        Path(OUTPUT_DIR) /
        f"region_{region}.png"
    )

    plt.savefig(
        output_file,
        bbox_inches="tight",
        dpi=300
    )

    plt.close()

    print(f"Saved: {output_file}")

print("\nDiagram generation complete.")
print(f"Output directory: {OUTPUT_DIR}")
```
