# Test Setup

## Infrastructure

### AI/Compute Server — h-oracle (192.168.178.100)

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 9 9950X3D — 16 cores / 32 threads |
| RAM | 96 GB DDR5 |
| GPU | 2x NVIDIA GeForce RTX 5090 (64 GB VRAM total) |
| Role | Ollama LLM inference server |
| Model | gpt-oss:120b-agent (116.8B params, MXFP4 quantization) |

### Secondary Compute — h-titan (192.168.178.101)

| Component | Spec |
|---|---|
| CPU | Intel Core i9-10900 — 10 cores / 20 threads |
| RAM | 128 GB DDR4 |
| GPU | NVIDIA RTX 4070 Ti (12 GB) + RTX 3090 (24 GB) |
| Storage | 1TB Kingston NVMe + 2TB Lexar NVMe |
| Role | Additional compute, model hosting |

### MCP Server Host — macOS workstation

| Component | Spec |
|---|---|
| Python | 3.11.15 |
| Transport | streamable-http (127.0.0.1:30030) |
| Connection Pool | idle_timeout=300s |

### Network Lab — 5x Junos Routers (virtual)

| Router | Management IP | Loopback | Links |
|---|---|---|---|
| R1 | 192.168.178.125 | 10.0.0.1/32 | ge-0/0/0 → R5, ge-0/0/1 → R4 |
| R2 | 192.168.178.123 | 10.0.0.2/32 | ge-0/0/0 → R3, ge-0/0/1 → R4 |
| R3 | 192.168.178.114 | 10.0.0.3/32 | ge-0/0/0 → R2, ge-0/0/1 → R5 |
| R4 | 192.168.178.124 | 10.0.0.4/32 | ge-0/0/0 → R1, ge-0/0/1 → R2 |
| R5 | 192.168.178.120 | 10.0.0.5/32 | ge-0/0/0 → R1, ge-0/0/1 → R3 |

- NETCONF over SSH on port 830
- Authentication: ed25519 SSH key
- OSPF area 0 on all interfaces
- Ring topology: R1 — R4 — R2 — R3 — R5 — R1

## Tools Used

| Tool | Purpose |
|---|---|
| [h-cli / h-ssh](https://github.com/h-network/h-cli) | Lab router provisioning (user creation, SSH keys, NETCONF, OSPF config) |
| [junos-mcp-server](https://github.com/Juniper/junos-mcp-server) | MCP server under test (modified with connection pool) |
| Ollama | Local LLM inference (gpt-oss:120b-agent) |
| PyEZ (junos-eznc) | NETCONF/SSH library for Junos devices |

## Network Diagram

```
                    ┌──────────┐
                    │    R1    │
                    │ 10.0.0.1 │
                    └──┬───┬──┘
              ge-0/0/0 │   │ ge-0/0/1
                       │   │
              ge-0/0/0 │   │ ge-0/0/0
                  ┌────┴┐ ┌┴────┐
                  │  R5  │ │  R4  │
                  │.0.5  │ │.0.4  │
                  └──┬──┘ └──┬──┘
            ge-0/0/1 │       │ ge-0/0/1
                     │       │
            ge-0/0/1 │       │ ge-0/0/1
                  ┌──┴──┐ ┌──┴──┐
                  │  R3  │ │  R2  │
                  │.0.3  │ │.0.2  │
                  └──┬──┘ └──┬──┘
            ge-0/0/0 │       │ ge-0/0/0
                     └───────┘

    All links: OSPF area 0, point-to-point /30 subnets
    Loopbacks: 10.0.0.X/32, passive OSPF
```
