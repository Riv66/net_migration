import json
import os
from diagrams import Diagram, Cluster
from diagrams.aws.network import VPC, PublicSubnet, PrivateSubnet, NATGateway, InternetGateway

BASE_DIR = "aws-network-inventory"

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def is_public(subnet_id, route_tables):
    for rt in route_tables.get("RouteTables", []):
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                for route in rt.get("Routes", []):
                    if route.get("GatewayId", "").startswith("igw-"):
                        return True
    return False

for region in os.listdir(BASE_DIR):
    region_path = os.path.join(BASE_DIR, region)

    vpcs = load_json(f"{region_path}/vpcs.json").get("Vpcs", [])
    subnets = load_json(f"{region_path}/subnets.json").get("Subnets", [])
    route_tables = load_json(f"{region_path}/route_tables.json")
    igws = load_json(f"{region_path}/igws.json").get("InternetGateways", [])
    nats = load_json(f"{region_path}/nat.json").get("NatGateways", [])

    with Diagram(f"AWS Network - {region}", filename=f"diagram_{region}", show=False):

        for vpc in vpcs:
            with Cluster(f"VPC {vpc['VpcId']}"):
                vpc_node = VPC(vpc["VpcId"])

                subnet_nodes = {}

                for subnet in subnets:
                    if subnet["VpcId"] != vpc["VpcId"]:
                        continue

                    if is_public(subnet["SubnetId"], route_tables):
                        node = PublicSubnet(subnet["SubnetId"])
                    else:
                        node = PrivateSubnet(subnet["SubnetId"])

                    subnet_nodes[subnet["SubnetId"]] = node
                    vpc_node >> node

                igw_nodes = []
                for igw in igws:
                    for att in igw.get("Attachments", []):
                        if att["VpcId"] == vpc["VpcId"]:
                            igw_node = InternetGateway(igw["InternetGatewayId"])
                            vpc_node >> igw_node
                            igw_nodes.append(igw_node)

                nat_nodes = {}
                for nat in nats:
                    if nat["VpcId"] != vpc["VpcId"]:
                        continue

                    nat_node = NATGateway(nat["NatGatewayId"])
                    nat_nodes[nat["NatGatewayId"]] = nat_node

                    subnet_id = nat.get("SubnetId")
                    if subnet_id in subnet_nodes:
                        subnet_nodes[subnet_id] >> nat_node
