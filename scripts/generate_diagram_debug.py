import json
from pathlib import Path
from diagrams import Diagram, Cluster
from diagrams.aws.network import VPC, PublicSubnet, PrivateSubnet, NATGateway, InternetGateway

BASE_DIR = Path("aws-network-inventory")
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

    text = path.read_text(encoding="utf-8-sig")
    debug(f"[SIZE] {path.name}: {len(text)} chars")

    if not text.strip():
        debug(f"[EMPTY] {path}")
        return {}

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            debug(f"[OK] {path.name}: top-level keys = {list(data.keys())}")
            return data
        debug(f"[WARN] {path.name}: JSON root is not an object")
        return {}
    except json.JSONDecodeError as e:
        debug(f"[INVALID JSON] {path}: {e}")
        raise ValueError(f"Invalid JSON in {path}: {e}") from e


def is_public(subnet_id, route_tables):
    for rt in route_tables.get("RouteTables", []):
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                for route in rt.get("Routes", []):
                    if str(route.get("GatewayId", "")).startswith("igw-"):
                        return True
    return False


script_dir = Path(__file__).resolve().parent
cwd = Path.cwd().resolve()
debug(f"[SCRIPT DIR] {script_dir}")
debug(f"[CWD] {cwd}")
debug(f"[BASE_DIR RAW] {BASE_DIR}")
debug(f"[BASE_DIR RESOLVED FROM CWD] {(cwd / BASE_DIR).resolve()}")

if not BASE_DIR.exists() or not BASE_DIR.is_dir():
    raise FileNotFoundError(
        f"Base directory not found: {(cwd / BASE_DIR).resolve()}\n"
        f"Run the script from the folder that contains '{BASE_DIR}', or change BASE_DIR to an absolute path."
    )

for region_dir in sorted(p for p in BASE_DIR.iterdir() if p.is_dir()):
    region = region_dir.name
    debug(f"\n[REGION] {region}")

    vpcs = load_json(region_dir / "vpcs.json").get("Vpcs", [])
    subnets = load_json(region_dir / "subnets.json").get("Subnets", [])
    route_tables = load_json(region_dir / "route_tables.json")
    igws = load_json(region_dir / "igws.json").get("InternetGateways", [])
    nats = load_json(region_dir / "nat.json").get("NatGateways", [])

    debug(
        f"[COUNTS] VPCs={len(vpcs)} Subnets={len(subnets)} "
        f"RouteTables={len(route_tables.get('RouteTables', []))} "
        f"IGWs={len(igws)} NATs={len(nats)}"
    )

    if not vpcs:
        debug(f"[SKIP] {region}: no VPCs found")
        continue

    with Diagram(f"AWS Network - {region}", filename=f"diagram_{region}", show=False):
        for vpc in vpcs:
            vpc_id = vpc.get("VpcId", "unknown-vpc")
            with Cluster(f"VPC {vpc_id}"):
                vpc_node = VPC(vpc_id)
                subnet_nodes = {}

                for subnet in subnets:
                    if subnet.get("VpcId") != vpc_id:
                        continue

                    subnet_id = subnet.get("SubnetId", "unknown-subnet")
                    node = PublicSubnet(subnet_id) if is_public(subnet_id, route_tables) else PrivateSubnet(subnet_id)
                    subnet_nodes[subnet_id] = node
                    vpc_node >> node

                for igw in igws:
                    for att in igw.get("Attachments", []):
                        if att.get("VpcId") == vpc_id:
                            igw_id = igw.get("InternetGatewayId", "unknown-igw")
                            igw_node = InternetGateway(igw_id)
                            vpc_node >> igw_node

                for nat in nats:
                    if nat.get("VpcId") != vpc_id:
                        continue

                    nat_id = nat.get("NatGatewayId", "unknown-nat")
                    nat_node = NATGateway(nat_id)

                    subnet_id = nat.get("SubnetId")
                    if subnet_id in subnet_nodes:
                        subnet_nodes[subnet_id] >> nat_node
