network_security_group_rules = [
    {
        "name": "SSH",
        "protocol": "*",
        "source_port_range": "*",
        "destination_port_range": "22",
        "source_address_prefix": "*",
        "destination_address_prefix": "*",
        "access": "Allow",
        "priority": 300,
        "direction": "Inbound"
    },
    {
        "name": "AllowAnyCustom1234Inbound",
        "protocol": "*",
        "source_port_range": "*",
        "destination_port_range": "1234",
        "source_address_prefix": "*",
        "destination_address_prefix": "*",
        "access": "Allow",
        "priority": 310,
        "direction": "Inbound"
    },
    {
        "name": "AllowAnyCustom1235Inbound",
        "protocol": "*",
        "source_port_range": "*",
        "destination_port_range": "1235",
        "source_address_prefix": "*",
        "destination_address_prefix": "*",
        "access": "Allow",
        "priority": 320,
        "direction": "Inbound"
    },
    {
        "name": "AllowAnyCustom4222Inbound",
        "protocol": "*",
        "source_port_range": "*",
        "destination_port_range": "4222",
        "source_address_prefix": "*",
        "destination_address_prefix": "*",
        "access": "Allow",
        "priority": 330,
        "direction": "Inbound"
    }
]
