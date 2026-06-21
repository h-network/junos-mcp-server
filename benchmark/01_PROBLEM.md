# The Problem: SSH Connection Overhead

## Current Behavior

The Junos MCP server opens a **fresh SSH/NETCONF session for every single tool call** and tears it down immediately after. This means every command pays the full cost of:

1. TCP handshake
2. SSH key exchange
3. NETCONF subsystem negotiation
4. Authentication
5. Command execution
6. Connection teardown

### Code Path (before fix)

```python
# jmcp.py - _run_junos_cli_command()
def _run_junos_cli_command(router_name, command, timeout=360):
    device_info = devices[router_name]
    connect_params = prepare_connection_params(device_info, router_name)
    with Device(**connect_params) as junos_device:  # <-- opens SSH
        junos_device.timeout = timeout
        op = junos_device.cli(command, warning=False)
        return op
    # <-- closes SSH immediately
```

Every handler (`execute_junos_command`, `get_junos_config`, `gather_device_facts`, `load_and_commit_config`, etc.) follows this same pattern.

## Why This Matters

In an MCP/LLM context, a single conversation typically involves **many sequential commands** to the same device:

```
User: "Check the OSPF status on R1"
  -> show ospf neighbor        (SSH open + close)
  -> show ospf interface       (SSH open + close)
  -> show ospf database        (SSH open + close)

User: "Now check the routes"
  -> show route 10.0.14.0      (SSH open + close)
  -> show route 10.0.15.0      (SSH open + close)

User: "Compare with R2"
  -> show ospf neighbor on R2  (SSH open + close)
  -> show route on R2          (SSH open + close)
```

Each of those SSH handshakes takes **~600-700ms** — pure overhead that adds up fast.

## Measured Impact

A typical daily operations workflow (7 commands across 5 routers = 35 operations):

| Metric | Value |
|---|---|
| Total SSH handshakes | 35 |
| Time per handshake | ~600-700ms |
| Total connection overhead | ~21-24 seconds |
| Actual command execution time | ~1.2 seconds |
| **Overhead ratio** | **~95% wasted on SSH setup** |

The server spends 95% of its time opening and closing SSH connections, not executing commands.

## Scaling the Problem

| Routers | Commands | SSH Handshakes | Estimated Overhead |
|---|---|---|---|
| 5 | 7 | 35 | ~24 seconds |
| 10 | 7 | 70 | ~48 seconds |
| 50 | 7 | 350 | ~4 minutes |
| 100 | 10 | 1000 | ~12 minutes |

For enterprise networks with 50+ devices, this makes the MCP server impractical for interactive LLM use.
