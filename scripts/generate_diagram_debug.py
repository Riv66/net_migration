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
    VPCRouter,
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
        f"Base directory not 
