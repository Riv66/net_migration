# generate_advanced_diagram.py
#
# Advanced AWS network relationship visualizer
#
# Features:
# - VPCs
# - Public/private subnet detection
# - Route table -> subnet associations
# - Internet gateways
# - NAT gateways
# - Security Groups -> ENIs
# - VPC Peering
# - Transit Gateway + attachments
# - Multi-account overlays
#
# Requirements:
#   pip install diagrams graphviz
#
# System requirement:
#   Graphviz installed:
#   https://graphviz.org/download/
#
# Expected inventory structure:
#
# aws-network-inventory/
#   ACCOUNT_ID/
#       REGION/
#           vpcs.json
#           subnets.json
#           route_tables.json
#           igws.json
#           nat.json
#           security_groups.json
#           network_interfaces.json
#           vpc_peering.json
#           tgws.json
#           tgw_attachments.json
#
# Example:
# python generate_advanced_diagram.py

import json
import os

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import (
    VPC,
    PublicSubnet,
    PrivateSubnet,
    NATGateway,
    InternetGateway,
    TransitGateway,
    VPCPeering,
    RouteTable,
    ElasticNetworkInterface,
)
from diagrams.aws.security import SecurityIdentityCompliance
from diagrams.aws.general import General


BASE_DIR = "aws-network-inventory"


def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_name(tags, default):
    if not tags:
        return default

    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value")

    return default


def is_public(subnet_id, route_tables):
    """
    Detect if subnet routes to IGW
    """
    for rt in route_tables.get("RouteTables", []):
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                for route in rt.get("Routes", []):
                    gateway = route.get("GatewayId", "")
                    if gateway.startswith("igw-"):
                        return True
    return False


# Global maps
vpc_nodes = {}
subnet_nodes = {}
sg_nodes = {}
eni_nodes = {}
tgw_nodes = {}
account_regions = []


with Diagram(
    "AWS Advanced Network Topology",
    filename="aws_advanced_topology",
    direction="LR",
    show=False,
):

    # ==========================================
    # Multi-account processing
    # ==========================================

    for account in os.listdir(BASE_DIR):

        account_path = os.path.join(BASE_DIR, account)

        if not os.path.isdir(account_path):
            continue

        with Cluster(f"AWS Account {account}"):

            for region in os.listdir(account_path):

                region_path = os.path.join(account_path, region)

                if not os.path.isdir(region_path):
                    continue

                print(f"Processing account={account} region={region}")

                # --------------------------------------
                # Load inventory
                # --------------------------------------

                vpcs = load_json(
                    f"{region_path}/vpcs.json"
                ).get("Vpcs", [])

                subnets = load_json(
                    f"{region_path}/subnets.json"
                ).get("Subnets", [])

                route_tables = load_json(
                    f"{region_path}/route_tables.json"
                )

                igws = load_json(
                    f"{region_path}/igws.json"
                ).get("InternetGateways", [])

                nats = load_json(
                    f"{region_path}/nat.json"
                ).get("NatGateways", [])

                sgs = load_json(
                    f"{region_path}/security_groups.json"
                ).get("SecurityGroups", [])

                enis = load_json(
                    f"{region_path}/network_interfaces.json"
                ).get("NetworkInterfaces", [])

                peerings = load_json(
                    f"{region_path}/vpc_peering.json"
                ).get("VpcPeeringConnections", [])

                tgws = load_json(
                    f"{region_path}/tgws.json"
                ).get("TransitGateways", [])

                tgw_attachments = load_json(
                    f"{region_path}/tgw_attachments.json"
                ).get("TransitGatewayAttachments", [])

                # ==========================================
                # Region cluster
                # ==========================================

                with Cluster(f"Region {region}"):

                    # ==========================================
                    # VPCs
                    # ==========================================

                    for vpc in vpcs:

                        vpc_id = vpc["VpcId"]
                        vpc_name = get_name(vpc.get("Tags"), vpc_id)

                        with Cluster(f"VPC {vpc_name}"):

                            vpc_node = VPC(vpc_name)
                            vpc_nodes[vpc_id] = vpc_node

                            # --------------------------------------
                            # Route Tables
                            # --------------------------------------

                            rt_nodes = {}

                            for rt in route_tables.get("RouteTables", []):

                                if rt["VpcId"] != vpc_id:
                                    continue

                                rt_id = rt["RouteTableId"]

                                rt_node = RouteTable(rt_id)
                                rt_nodes[rt_id] = rt_node

                                vpc_node >> rt_node

                            # --------------------------------------
                            # Subnets
                            # --------------------------------------

                            for subnet in subnets:

                                if subnet["VpcId"] != vpc_id:
                                    continue

                                subnet_id = subnet["SubnetId"]

                                subnet_name = get_name(
                                    subnet.get("Tags"),
                                    subnet_id,
                                )

                                if is_public(
                                    subnet_id,
                                    route_tables,
                                ):
                                    subnet_node = PublicSubnet(
                                        subnet_name
                                    )
                                else:
                                    subnet_node = PrivateSubnet(
                                        subnet_name
                                    )

                                subnet_nodes[subnet_id] = subnet_node

                                vpc_node >> subnet_node

                                # --------------------------------------
                                # Route Table Associations
                                # --------------------------------------

                                for rt in route_tables.get(
                                    "RouteTables", []
                                ):
                                    for assoc in rt.get(
                                        "Associations", []
                                    ):

                                        if (
                                            assoc.get("SubnetId")
                                            == subnet_id
                                        ):
                                            rt_id = rt[
                                                "RouteTableId"
                                            ]

                                            if rt_id in rt_nodes:
                                                rt_nodes[
                                                    rt_id
                                                ] >> Edge(
                                                    label="association"
                                                ) >> subnet_node

                            # --------------------------------------
                            # Internet Gateways
                            # --------------------------------------

                            for igw in igws:

                                for attachment in igw.get(
                                    "Attachments", []
                                ):

                                    if (
                                        attachment["VpcId"]
                                        == vpc_id
                                    ):

                                        igw_id = igw[
                                            "InternetGatewayId"
                                        ]

                                        igw_node = (
                                            InternetGateway(
                                                igw_id
                                            )
                                        )

                                        vpc_node >> igw_node

                            # --------------------------------------
                            # NAT Gateways
                            # --------------------------------------

                            for nat in nats:

                                if nat["VpcId"] != vpc_id:
                                    continue

                                nat_id = nat["NatGatewayId"]

                                nat_node = NATGateway(nat_id)

                                subnet_id = nat.get("SubnetId")

                                if (
                                    subnet_id
                                    in subnet_nodes
                                ):
                                    subnet_nodes[
                                        subnet_id
                                    ] >> nat_node

                            # --------------------------------------
                            # Security Groups
                            # --------------------------------------

                            for sg in sgs:

                                if sg["VpcId"] != vpc_id:
                                    continue

                                sg_id = sg["GroupId"]

                                sg_name = get_name(
                                    sg.get("Tags"),
                                    sg["GroupName"],
                                )

                                sg_node = (
                                    SecurityIdentityCompliance(
                                        sg_name
                                    )
                                )

                                sg_nodes[sg_id] = sg_node

                                vpc_node >> sg_node

                            # --------------------------------------
                            # ENIs
                            # --------------------------------------

                            for eni in enis:

                                eni_id = eni[
                                    "NetworkInterfaceId"
                                ]

                                eni_node = (
                                    ElasticNetworkInterface(
                                        eni_id
                                    )
                                )

                                eni_nodes[eni_id] = eni_node

                                subnet_id = eni.get(
                                    "SubnetId"
                                )

                                if (
                                    subnet_id
                                    in subnet_nodes
                                ):
                                    subnet_nodes[
                                        subnet_id
                                    ] >> eni_node

                                # SG -> ENI
                                for group in eni.get(
                                    "Groups", []
                                ):

                                    sg_id = group["GroupId"]

                                    if sg_id in sg_nodes:
                                        sg_nodes[
                                            sg_id
                                        ] >> Edge(
                                            label="attached"
                                        ) >> eni_node

                    # ==========================================
                    # Transit Gateways
                    # ==========================================

                    for tgw in tgws:

                        tgw_id = tgw[
                            "TransitGatewayId"
                        ]

                        tgw_node = TransitGateway(
                            tgw_id
                        )

                        tgw_nodes[tgw_id] = tgw_node

                    # TGW attachments
                    for attachment in tgw_attachments:

                        tgw_id = attachment.get(
                            "TransitGatewayId"
                        )

                        resource_id = attachment.get(
                            "ResourceId"
                        )

                        if (
                            tgw_id in tgw_nodes
                            and resource_id
                            in vpc_nodes
                        ):

                            tgw_nodes[
                                tgw_id
                            ] >> vpc_nodes[
                                resource_id
                            ]

    # ==========================================
    # VPC Peering
    # ==========================================

    for account in os.listdir(BASE_DIR):

        account_path = os.path.join(BASE_DIR, account)

        if not os.path.isdir(account_path):
            continue

        for region in os.listdir(account_path):

            region_path = os.path.join(
                account_path,
                region,
            )

            peerings = load_json(
                f"{region_path}/vpc_peering.json"
            ).get("VpcPeeringConnections", [])

            for peering in peerings:

                requester = peering[
                    "RequesterVpcInfo"
                ]["VpcId"]

                accepter = peering[
                    "AccepterVpcInfo"
                ]["VpcId"]

                peering_id = peering[
                    "VpcPeeringConnectionId"
                ]

                if (
                    requester in vpc_nodes
                    and accepter in vpc_nodes
                ):

                    peering_node = VPCPeering(
                        peering_id
                    )

                    vpc_nodes[
                        requester
                    ] >> peering_node >> vpc_nodes[
                        accepter
                    ]


print("Diagram generation complete.")
print("Output: aws_advanced_topology.png")
