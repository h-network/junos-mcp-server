# Test Methodology

## Lab Topology

5 Junos routers in a ring topology with OSPF:

```
          R1 (10.0.0.1)
         /              \
   ge-0/0/0          ge-0/0/1
       /                  \
R5 (10.0.0.5)        R4 (10.0.0.4)
      \                  /
   ge-0/0/1          ge-0/0/1
        \              /
   R3 (10.0.0.3) -- R2 (10.0.0.2)
       ge-0/0/0 -- ge-0/0/0
```

- All links are point-to-point with /30 subnets
- Each router has a loopback (lo0) with 10.0.0.X/32
- OSPF area 0.0.0.0 on all interfaces
- NETCONF over SSH enabled on port 830
- Authentication: SSH key (ed25519)

## Test Commands

7 commands representing typical daily network operations:

| # | Command | Type |
|---|---|---|
| 1 | `show ospf interface` | Protocol state |
| 2 | `show ospf database` | LSDB inspection |
| 3 | `show ospf neighbor` | Adjacency check |
| 4 | `show route 10.0.14.0` | Route lookup |
| 5 | `show chassis hardware` | Inventory |
| 6 | `show route 10.0.15.0 extensive` | Detailed route |
| 7 | `show route forwarding-table all destination 10.0.15.0` | FIB lookup |

## Three Scenarios Tested

### Scenario 1: Original Code (No Pool)
Simulates the current Juniper MCP server behavior:
- Fresh `Device()` connection per command per router
- Sequential execution (one router at a time)
- 35 SSH handshakes total (7 commands x 5 routers)

```python
for cmd in COMMANDS:
    for router_name in ROUTERS:
        with Device(**connect_params) as dev:  # new SSH each time
            dev.cli(cmd)
```

### Scenario 2: Connection Pool + Sequential
Uses the connection pool but executes one router at a time:
- Pool reuses SSH sessions across calls
- 5 SSH handshakes total (one per router, reused)
- Sequential execution

```python
# MCP tool: execute_junos_command (one router per call)
for cmd in COMMANDS:
    for router in ROUTERS:
        session.call_tool('execute_junos_command', {
            'router_name': router, 'command': cmd
        })
```

### Scenario 3: Connection Pool + Parallel
Uses the connection pool with batch parallel execution:
- Pool reuses SSH sessions
- 5 SSH handshakes total
- All 5 routers queried simultaneously per command

```python
# MCP tool: execute_junos_command_batch (all routers at once)
for cmd in COMMANDS:
    session.call_tool('execute_junos_command_batch', {
        'router_names': ROUTERS, 'command': cmd
    })
```

## Benchmark Script

The benchmark was run using a Python MCP client connecting to the server via streamable-http transport. The pool was warmed up with a single `show version` call before measurements to ensure the comparison isolates command execution time (not initial connection).

For the original code scenario, PyEZ `Device()` was used directly with the same connection parameters, bypassing the pool entirely.

All scenarios ran back-to-back in the same session to minimize environmental variance.

## How to Reproduce

```bash
# 1. Start the MCP server
.venv/bin/python jmcp.py -f devices.json -t streamable-http -H 127.0.0.1 -p 30030

# 2. Run the benchmark
.venv/bin/python benchmark/benchmark.py
```
