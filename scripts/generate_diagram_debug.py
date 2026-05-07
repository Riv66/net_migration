import json
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.network import (
    InternetGateway,
    NATGateway,
    PrivateSubnet,
    PublicSubnet,
    RouteTable,
    TransitGateway,
    VPC,
)
from diagrams.aws.security import IAMRole

BASE_DIR = Path(__file__).resolve().parent / "aws-network-inventory"
DEBUG = True


def debug(msg):
    if DEBUG:
        print(msg)


def load_json(path):
    path = Path(path)
    debug(f"[LOAD] {path.resolve()}")

    if not path.exists():
        debug(f"[MISSING] {path}")
        return {}

    if not path.is_file():
        debug(f"[NOT A FILE] {path}")
        return {}

    encodings = ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"]

    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            debug(f"[SIZE] {path.name}: {len(text)} chars using {encoding}")

            if not text.strip():
                debug(f"[EMPTY] {path}")
                return {}

            data = json.loads(text)

            if isinstance(data, dict):
                debug(f"[OK] {path.name}: top-level keys = {list(data.keys())} using {encoding}")
                return data

            debug(f"[WARN] {path.name}: JSON root is not an object using {encoding}")
            return {}

        except UnicodeDecodeError:
            debug(f"[DECODE FAIL] {path.name} with {encoding}")
            continue
        except json.JSONDecodeError as e:
            debug(f"[INVALID JSON] {path} with {encoding}: {e}")
            raise ValueError(f"Invalid JSON in {path}: {e}") from e

    raise ValueError(f"Could not decode file with supported encodings: {path}")


def load_optional(region_dir, filename, top_key):
    data = load_json(region_dir / filename)
    return data.get(top_key, []) if isinstance(data, dict) else []


def is_public(subnet_id, route_tables):
    for rt in route_tables.get("RouteTables", []):
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                for route in rt.get("Routes", []):
                    if str(route.get("GatewayId", "")).startswith("igw-"):
                        return True
    return False


def route_table_for_subnet(subnet_id, route_tables):
    for rt in route_tables.get("RouteTables", []):
        rt_id = rt.get("RouteTableId", "unknown-rt")
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                return rt_id
    return None


def vpc_account_id(vpc):
    return (
        vpc.get("OwnerId")
        or vpc.get("AccountId")
        or vpc.get("AwsAccountId")
        or "unknown-account"
    )


script_dir = Path(__file__).resolve().parent
cwd = Path.cwd().resolve()

debug(f"[SCRIPT DIR] {script_dir}")
debug(f"[CWD] {cwd}")
debug(f"[BASE_DIR] {BASE_DIR}")

if not BASE_DIR.exists() or not BASE_DIR.is_dir():
    raise FileNotFoundError(
        f"Base directory not found: {BASE_DIR}\n"
        f"Place 'aws-network-inventory' beside this script or update BASE_DIR."
    )

for region_dir in sorted(p for p in BASE_DIR.iterdir() if p.is_dir()):
    region = region_dir.name
    debug(f"\\n[REGION] {region}")

    vpcs = load_optional(region_dir, "vpcs.json", "Vpcs")
    subnets = load_optional(region_dir, "subnets.json", "Subnets")
    route_tables_data = load_json(region_dir / "route_tables.json")
    route_tables = route_tables_data if isinstance(route_tables_data, dict) else {}
    igws = load_optional(region_dir, "igws.json", "InternetGateways")
    nats = load_optional(region_dir, "nat.json", "NatGateways")

    security_groups = load_optional(region_dir, "security_groups.json", "SecurityGroups")
    enis = load_optional(region_dir, "network_interfaces.json", "NetworkInterfaces")
    vpc_peerings = load_optional(region_dir, "vpc_peering.json", "VpcPeeringConnections")
    transit_gateways = load_optional(region_dir, "transit_gateways.json", "TransitGateways")
    tgw_attachments = load_optional(
        region_dir,
        "transit_gateway_attachments.json",
        "TransitGatewayAttachments",
    )
    accounts = load_optional(region_dir, "accounts.json", "Accounts")

    debug(
        f"[COUNTS] "
        f"VPCs={len(vpcs)} "
        f"Subnets={len(subnets)} "
        f"RTs={len(route_tables.get('RouteTables', []))} "
        f"IGWs={len(igws)} "
        f"NATs={len(nats)} "
        f"SGs={len(security_groups)} "
        f"ENIs={len(enis)} "
        f"Peerings={len(vpc_peerings)} "
        f"TGWs={len(transit_gateways)} "
        f"TGW_Attachments={len(tgw_attachments)}"
    )

    if not vpcs:
        debug(f"[SKIP] {region}: no VPCs found")
        continue

    with Diagram(
        f"AWS Network - {region}",
        filename=f"diagram_{region}",
        show=False,
        direction="LR",
        outformat="png",
    ):
        vpc_nodes = {}
        subnet_nodes = {}
        rt_nodes = {}
        sg_nodes = {}
        eni_nodes = {}
        tgw_nodes = {}

        account_ids = set()
        for vpc in vpcs:
            account_ids.add(vpc_account_id(vpc))

        if accounts:
            account_labels = {
                str(a.get("AccountId", "unknown-account")): (
                    a.get("AccountName")
                    or a.get("Name")
                    or str(a.get("AccountId", "unknown-account"))
                )
                for a in accounts
            }
        else:
            account_labels = {acc: acc for acc in account_ids}

        for account_id in sorted(account_ids):
            account_label = account_labels.get(account_id, account_id)

            with Cluster(f"Account {account_label}"):
                account_vpcs = [v for v in vpcs if vpc_account_id(v) == account_id]

                for vpc in account_vpcs:
                    vpc_id = vpc.get("VpcId", "unknown-vpc")

                    with Cluster(f"VPC {vpc_id}"):
                        vpc_node = VPC(vpc_id)
                        vpc_nodes[vpc_id] = vpc_node

                        for rt in route_tables.get("RouteTables", []):
                            if rt.get("VpcId") != vpc_id:
                                continue

                            rt_id = rt.get("RouteTableId", "unknown-rt")
                            rt_node = RouteTable(rt_id)
                            rt_nodes[rt_id] = rt_node
                            vpc_node >> Edge(label="contains") >> rt_node

                        for subnet in subnets:
                            if subnet.get("VpcId") != vpc_id:
                                continue

                            subnet_id = subnet.get("SubnetId", "unknown-subnet")

                            if is_public(subnet_id, route_tables):
                                subnet_node = PublicSubnet(subnet_id)
                            else:
                                subnet_node = PrivateSubnet(subnet_id)

                            subnet_nodes[subnet_id] = subnet_node
                            vpc_node >> Edge(label="contains") >> subnet_node

                            rt_id = route_table_for_subnet(subnet_id, route_tables)
                            if rt_id and rt_id in rt_nodes:
                                rt_nodes[rt_id] >> Edge(
                                    label="association",
                                    style="dashed",
                                ) >> subnet_node

                        for igw in igws:
                            for att in igw.get("Attachments", []):
                                if att.get("VpcId") == vpc_id:
                                    igw_id = igw.get("InternetGatewayId", "unknown-igw")
                                    igw_node = InternetGateway(igw_id)
                                    vpc_node >> Edge(label="attached") >> igw_node

                        for nat in nats:
                            if nat.get("VpcId") != vpc_id:
                                continue

                            nat_id = nat.get("NatGatewayId", "unknown-nat")
                            nat_node = NATGateway(nat_id)

                            subnet_id = nat.get("SubnetId")
                            if subnet_id in subnet_nodes:
                                subnet_nodes[subnet_id] >> Edge(label="hosts") >> nat_node

                        with Cluster(f"Security / ENIs {vpc_id}"):
                            for sg in security_groups:
                                if sg.get("VpcId") != vpc_id:
                                    continue

                                sg_id = sg.get("GroupId") or sg.get("GroupName", "unknown-sg")
                                sg_node = IAMRole(f"SG {sg_id}")
                                sg_nodes[sg_id] = sg_node

                            for eni in enis:
                                if eni.get("VpcId") != vpc_id:
                                    continue

                                eni_id = eni.get("NetworkInterfaceId", "unknown-eni")
                                eni_node = EC2(f"ENI {eni_id}")
                                eni_nodes[eni_id] = eni_node

                                subnet_id = eni.get("SubnetId")
                                if subnet_id in subnet_nodes:
                                    subnet_nodes[subnet_id] >> Edge(label="hosts") >> eni_node

                                for sg_ref in eni.get("Groups", []):
                                    sg_id = sg_ref.get("GroupId")
                                    if sg_id in sg_nodes:
                                        sg_nodes[sg_id] >> Edge(
                                            label="attached",
                                            style="dashed",
                                        ) >> eni_node

        if transit_gateways:
            with Cluster("Transit Gateways"):
                for tgw in transit_gateways:
                    tgw_id = tgw.get("TransitGatewayId", "unknown-tgw")
                    tgw_node = TransitGateway(tgw_id)
                    tgw_nodes[tgw_id] = tgw_node

        for att in tgw_attachments:
            tgw_id = att.get("TransitGatewayId")
            resource_type = att.get("ResourceType")
            resource_id = att.get("ResourceId")
            state = att.get("State", "unknown")

            if state not in {"available", "pending", "pendingAcceptance"}:
                continue

            if resource_type == "vpc" and tgw_id in tgw_nodes and resource_id in vpc_nodes:
                vpc_nodes[resource_id] >> Edge(
                    label="tgw-attachment",
                    style="bold",
                ) >> tgw_nodes[tgw_id]

        for peering in vpc_peerings:
            status = peering.get("Status", {}).get("Code")
            if status not in {"active", "pending-acceptance", "provisioning"}:
                continue

            requester = peering.get("RequesterVpcInfo", {}).get("VpcId")
            accepter = peering.get("AccepterVpcInfo", {}).get("VpcId")
            peering_id = peering.get("VpcPeeringConnectionId", "pcx-unknown")

            if requester in vpc_nodes and accepter in vpc_nodes and requester != accepter:
                vpc_nodes[requester] >> Edge(
                    label=f"peering {peering_id}",
                    style="dashed",
                ) >> vpc_nodes[accepter]

    debug(f"[DONE] diagram_{region}.png")
