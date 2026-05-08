import json
import os
from pathlib import Path
from graphviz import Digraph

# ============================================================
# AWS Network Dependency Mapper
# ============================================================

BASE_DIR = Path("aws-network-inventory")
OUTPUT_DIR = Path("AWS_Network_Diagrams")

OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# Region Selection
# ============================================================

all_regions = sorted([
    d.name for d in BASE_DIR.iterdir()
    if d.is_dir()
])

if not all_regions:
    print("No regions found in aws-network-inventory")
    exit(1)

print("")
print("Available regions:")
print(", ".join(all_regions))
print("")

regions_input = input(
    "Enter AWS regions (comma separated) or press Enter for ALL: "
).strip()

if regions_input:
    selected_regions = [
        r.strip() for r in regions_input.split(",")
        if r.strip() in all_regions
    ]
else:
    selected_regions = all_regions

if not selected_regions:
    print("No valid regions selected.")
    exit(1)

print("")
print(f"Generating diagrams for {len(selected_regions)} region(s)")
print("")

# ============================================================
# Helpers
# ============================================================

def safe_load_json(path):

    if not path.exists():
        print(f"Missing: {path}")
        return {}

    try:

        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    except Exception as e:

        print(f"Failed to load {path}: {e}")
        return {}

def get_name(tags):

    if not tags:
        return ""

    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value", "")

    return ""

def shorten(text, length=24):

    if not text:
        return ""

    if len(text) <= length:
        return text

    return text[:length] + "..."

# ============================================================
# Diagram Styles
# ============================================================

GRAPH_ATTR = {
    "fontsize": "18",
    "fontname": "Arial",
    "rankdir": "LR",
    "splines": "polyline",
    "nodesep": "0.5",
    "ranksep": "1.0"
}

NODE_ATTR = {
    "shape": "box",
    "style": "rounded,filled",
    "fillcolor": "#F8F9FA",
    "fontname": "Arial",
    "fontsize": "10"
}

EDGE_ATTR = {
    "fontname": "Arial",
    "fontsize": "9"
}

# ============================================================
# Region Processing
# ============================================================

for region in selected_regions:

    print(f"Processing region: {region}")

    region_dir = BASE_DIR / region

    output_region = OUTPUT_DIR / region

    output_region.mkdir(exist_ok=True)

    # ========================================================
    # Load Files
    # ========================================================

    vpcs = safe_load_json(
        region_dir / "vpcs.json"
    ).get("Vpcs", [])

    subnets = safe_load_json(
        region_dir / "subnets.json"
    ).get("Subnets", [])

    route_tables = safe_load_json(
        region_dir / "route_tables.json"
    ).get("RouteTables", [])

    igws = safe_load_json(
        region_dir / "igws.json"
    ).get("InternetGateways", [])

    nat_gateways = safe_load_json(
        region_dir / "nat.json"
    ).get("NatGateways", [])

    security_groups = safe_load_json(
        region_dir / "security_groups.json"
    ).get("SecurityGroups", [])

    peerings = safe_load_json(
        region_dir / "vpc_peering.json"
    ).get("VpcPeeringConnections", [])

    tgws = safe_load_json(
        region_dir / "tgws.json"
    ).get("TransitGateways", [])

    tgw_attachments = safe_load_json(
        region_dir / "tgw_attachments.json"
    ).get("TransitGatewayAttachments", [])

    # ========================================================
    # Build Lookup Maps
    # ========================================================

    subnet_map = {
        s["SubnetId"]: s
        for s in subnets
    }

    vpc_map = {
        v["VpcId"]: v
        for v in vpcs
    }

    # ========================================================
    # PAGE 1 - VPC CONNECTIVITY
    # ========================================================

    dot = Digraph(
        name=f"{region}_vpc_connectivity",
        format="png"
    )

    dot.attr(**GRAPH_ATTR)
    dot.attr("node", **NODE_ATTR)
    dot.attr("edge", **EDGE_ATTR)

    dot.attr(
        label=f"{region} - VPC Connectivity",
        labelloc="t"
    )

    # ------------------------
    # VPC Clusters
    # ------------------------

    for vpc in vpcs:

        vpc_id = vpc["VpcId"]

        vpc_name = get_name(vpc.get("Tags"))

        cidr = vpc.get("CidrBlock", "")

        with dot.subgraph(
            name=f"cluster_{vpc_id}"
        ) as c:

            c.attr(
                label=f"{vpc_name or vpc_id}\n{cidr}",
                style="rounded"
            )

            c.node(
                vpc_id,
                f"VPC\n{vpc_id}\n{cidr}",
                fillcolor="#D6EAF8"
            )

            # Subnets
            for subnet in subnets:

                if subnet["VpcId"] != vpc_id:
                    continue

                subnet_id = subnet["SubnetId"]

                subnet_name = get_name(
                    subnet.get("Tags")
                )

                az = subnet.get(
                    "AvailabilityZone",
                    ""
                )

                subnet_cidr = subnet.get(
                    "CidrBlock",
                    ""
                )

                label = (
                    f"{subnet_name or subnet_id}\n"
                    f"{az}\n"
                    f"{subnet_cidr}"
                )

                c.node(
                    subnet_id,
                    label,
                    fillcolor="#D5F5E3"
                )

                c.edge(vpc_id, subnet_id)

            # IGWs
            for igw in igws:

                attachments = igw.get(
                    "Attachments",
                    []
                )

                attached = any(
                    a.get("VpcId") == vpc_id
                    for a in attachments
                )

                if attached:

                    igw_id = igw["InternetGatewayId"]

                    c.node(
                        igw_id,
                        f"IGW\n{igw_id}",
                        fillcolor="#FCF3CF"
                    )

                    c.edge(vpc_id, igw_id)

            # NAT Gateways
            for nat in nat_gateways:

                if nat.get("VpcId") != vpc_id:
                    continue

                nat_id = nat["NatGatewayId"]

                c.node(
                    nat_id,
                    f"NAT\n{nat_id}",
                    fillcolor="#FADBD8"
                )

                subnet_id = nat.get("SubnetId")

                if subnet_id:
                    c.edge(subnet_id, nat_id)

    # ------------------------
    # Peering
    # ------------------------

    for peering in peerings:

        requester = peering.get(
            "RequesterVpcInfo",
            {}
        ).get("VpcId")

        accepter = peering.get(
            "AccepterVpcInfo",
            {}
        ).get("VpcId")

        peering_id = peering.get(
            "VpcPeeringConnectionId",
            ""
        )

        if requester and accepter:

            dot.edge(
                requester,
                accepter,
                label=f"Peering\n{peering_id}",
                style="dashed"
            )

    # ------------------------
    # TGW Attachments
    # ------------------------

    for tgw in tgws:

        tgw_id = tgw["TransitGatewayId"]

        dot.node(
            tgw_id,
            f"TGW\n{tgw_id}",
            fillcolor="#E8DAEF"
        )

    for attachment in tgw_attachments:

        tgw_id = attachment.get(
            "TransitGatewayId"
        )

        resource_id = attachment.get(
            "ResourceId"
        )

        if tgw_id and resource_id:

            dot.edge(
                resource_id,
                tgw_id,
                label="attachment"
            )

    dot.render(
        output_region / "vpc_connectivity",
        cleanup=True
    )

    # ========================================================
    # PAGE 2 - ROUTE DEPENDENCIES
    # ========================================================

    route_dot = Digraph(
        name=f"{region}_route_dependencies",
        format="png"
    )

    route_dot.attr(**GRAPH_ATTR)

    route_dot.attr("node", **NODE_ATTR)

    route_dot.attr("edge", **EDGE_ATTR)

    route_dot.attr(
        label=f"{region} - Route Dependencies",
        labelloc="t"
    )

    for rt in route_tables:

        rt_id = rt["RouteTableId"]

        route_dot.node(
            rt_id,
            f"Route Table\n{rt_id}",
            fillcolor="#D6EAF8"
        )

        # Associations
        for assoc in rt.get("Associations", []):

            subnet_id = assoc.get("SubnetId")

            if subnet_id:

                subnet = subnet_map.get(
                    subnet_id,
                    {}
                )

                subnet_label = (
                    subnet.get("SubnetId", "")
                    + "\n"
                    + subnet.get("CidrBlock", "")
                )

                route_dot.node(
                    subnet_id,
                    subnet_label,
                    fillcolor="#D5F5E3"
                )

                route_dot.edge(
                    subnet_id,
                    rt_id,
                    label="associated"
                )

        # Routes
        for route in rt.get("Routes", []):

            destination = route.get(
                "DestinationCidrBlock",
                "local"
            )

            targets = [
                route.get("GatewayId"),
                route.get("NatGatewayId"),
                route.get("TransitGatewayId"),
                route.get("VpcPeeringConnectionId")
            ]

            for target in targets:

                if not target:
                    continue

                route_dot.node(
                    target,
                    target
                )

                route_dot.edge(
                    rt_id,
                    target,
                    label=destination
                )

    route_dot.render(
        output_region / "route_dependencies",
        cleanup=True
    )

    # ========================================================
    # PAGE 3 - SECURITY GROUP RELATIONSHIPS
    # ========================================================

    sg_dot = Digraph(
        name=f"{region}_security_groups",
        format="png"
    )

    sg_dot.attr(**GRAPH_ATTR)

    sg_dot.attr("node", **NODE_ATTR)

    sg_dot.attr("edge", **EDGE_ATTR)

    sg_dot.attr(
        label=f"{region} - Security Group Relationships",
        labelloc="t"
    )

    for sg in security_groups:

        sg_id = sg["GroupId"]

        sg_name = sg.get("GroupName", "")

        sg_dot.node(
            sg_id,
            f"{sg_name}\n{sg_id}",
            fillcolor="#F9E79F"
        )

    # Inbound relationships
    for sg in security_groups:

        sg_id = sg["GroupId"]

        for perm in sg.get("IpPermissions", []):

            protocol = perm.get("IpProtocol", "")

            from_port = perm.get("FromPort", "")

            to_port = perm.get("ToPort", "")

            label = f"{protocol}:{from_port}-{to_port}"

            for pair in perm.get(
                "UserIdGroupPairs",
                []
            ):

                source_sg = pair.get("GroupId")

                if source_sg:

                    sg_dot.edge(
                        source_sg,
                        sg_id,
                        label=label
                    )

    sg_dot.render(
        output_region / "security_groups",
        cleanup=True
    )

    # ========================================================
    # PAGE 4 - DEPENDENCY MAP
    # ========================================================

    dep_dot = Digraph(
        name=f"{region}_dependency_map",
        format="png"
    )

    dep_dot.attr(**GRAPH_ATTR)

    dep_dot.attr("node", **NODE_ATTR)

    dep_dot.attr("edge", **EDGE_ATTR)

    dep_dot.attr(
        label=f"{region} - Dependency Map",
        labelloc="t"
    )

    # VPC -> Subnet
    for subnet in subnets:

        dep_dot.edge(
            subnet["VpcId"],
            subnet["SubnetId"]
        )

    # Subnet -> RouteTable
    for rt in route_tables:

        rt_id = rt["RouteTableId"]

        for assoc in rt.get("Associations", []):

            subnet_id = assoc.get("SubnetId")

            if subnet_id:

                dep_dot.edge(
                    subnet_id,
                    rt_id
                )

        # RouteTable -> targets
        for route in rt.get("Routes", []):

            targets = [
                route.get("GatewayId"),
                route.get("NatGatewayId"),
                route.get("TransitGatewayId")
            ]

            for target in targets:

                if target:

                    dep_dot.edge(
                        rt_id,
                        target
                    )

    # NAT -> Subnet
    for nat in nat_gateways:

        nat_id = nat["NatGatewayId"]

        subnet_id = nat.get("SubnetId")

        if subnet_id:

            dep_dot.edge(
                subnet_id,
                nat_id
            )

    dep_dot.render(
        output_region / "dependency_map",
        cleanup=True
    )

# ============================================================
# GLOBAL OVERVIEW
# ============================================================

print("")
print("Generating global overview...")

global_dot = Digraph(
    "global_overview",
    format="png"
)

global_dot.attr(**GRAPH_ATTR)

global_dot.attr(
    label="AWS Global VPC Connectivity",
    labelloc="t"
)

for region in selected_regions:

    region_dir = BASE_DIR / region

    vpcs = safe_load_json(
        region_dir / "vpcs.json"
    ).get("Vpcs", [])

    peerings = safe_load_json(
        region_dir / "vpc_peering.json"
    ).get("VpcPeeringConnections", [])

    with global_dot.subgraph(
        name=f"cluster_{region}"
    ) as c:

        c.attr(label=region)

        for vpc in vpcs:

            vpc_id = vpc["VpcId"]

            cidr = vpc.get(
                "CidrBlock",
                ""
            )

            c.node(
                vpc_id,
                f"{vpc_id}\n{cidr}"
            )

    for peering in peerings:

        requester = peering.get(
            "RequesterVpcInfo",
            {}
        ).get("VpcId")

        accepter = peering.get(
            "AccepterVpcInfo",
            {}
        ).get("VpcId")

        if requester and accepter:

            global_dot.edge(
                requester,
                accepter,
                style="dashed"
            )

global_dot.render(
    OUTPUT_DIR / "global_overview",
    cleanup=True
)

print("")
print("Diagram generation complete.")
print("")
print("Output:")
print(f"  {OUTPUT_DIR.resolve()}")
print("")
print("Generated:")
print("  - global_overview.png")
print("  - vpc_connectivity.png")
print("  - route_dependencies.png")
print("  - security_groups.png")
print("  - dependency_map.png")
print("")
print("Per-region diagrams located in:")
print("  AWS_Network_Diagrams/<region>/")
