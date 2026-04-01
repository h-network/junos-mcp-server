#!/usr/bin/env python3
"""
Junos MCP Server — Connection Pool Benchmark

Compares three scenarios:
  1. Original: fresh SSH connection per command (no pool)
  2. Pool + Sequential: reused connections, one router at a time
  3. Pool + Parallel: reused connections, all routers simultaneously

Prerequisites:
  - MCP server running: python jmcp.py -f devices.json -t streamable-http -H 127.0.0.1 -p 30030
  - devices.json configured with reachable Junos routers
  - NETCONF enabled on all routers

Usage:
  python benchmark/benchmark.py [--server http://127.0.0.1:30030/mcp] [--devices devices.json]
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Add parent dir so we can import utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jnpr.junos import Device
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from utils.config import prepare_connection_params

COMMANDS = [
    "show ospf interface | no-more",
    "show ospf database | no-more",
    "show ospf neighbor | no-more",
    "show route 10.0.14.0 | no-more",
    "show chassis hardware | no-more",
    "show route 10.0.15.0 extensive | no-more",
    "show route forwarding-table all destination 10.0.15.0 | no-more",
]


def clean_cmd(cmd):
    return cmd.replace(" | no-more", "")


def run_original(devices, routers):
    """Scenario 1: Original code — fresh SSH per command per router."""
    results = []
    total_start = time.time()
    for cmd in COMMANDS:
        cmd_start = time.time()
        for router_name in routers:
            device_info = devices[router_name]
            connect_params = prepare_connection_params(device_info, router_name)
            with Device(**connect_params) as dev:
                dev.timeout = 360
                dev.cli(cmd, warning=False)
        cmd_dur = round(time.time() - cmd_start, 3)
        results.append((clean_cmd(cmd), cmd_dur))
    total = round(time.time() - total_start, 3)
    return results, total


async def run_pooled(server_url, routers):
    """Scenarios 2 & 3: Pool+Sequential and Pool+Parallel."""
    async with streamablehttp_client(server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Warm up pool
            await session.call_tool(
                "execute_junos_command_batch",
                {"router_names": routers, "command": "show version | no-more"},
            )

            # Scenario 2: Pool + Sequential
            seq_results = []
            seq_start = time.time()
            for cmd in COMMANDS:
                cmd_start = time.time()
                for router in routers:
                    await session.call_tool(
                        "execute_junos_command",
                        {"router_name": router, "command": cmd},
                    )
                cmd_dur = round(time.time() - cmd_start, 3)
                seq_results.append((clean_cmd(cmd), cmd_dur))
            seq_total = round(time.time() - seq_start, 3)

            # Scenario 3: Pool + Parallel
            par_results = []
            par_start = time.time()
            for cmd in COMMANDS:
                result = await session.call_tool(
                    "execute_junos_command_batch",
                    {"router_names": routers, "command": cmd},
                )
                data = json.loads(result.content[0].text)
                duration = data["summary"]["total_duration"]
                par_results.append((clean_cmd(cmd), duration))
            par_total = round(time.time() - par_start, 3)

            return seq_results, seq_total, par_results, par_total


def print_results(routers, orig_results, orig_total, seq_results, seq_total, par_results, par_total):
    n_routers = len(routers)
    n_commands = len(COMMANDS)
    n_ops = n_routers * n_commands

    print()
    print("=" * 110)
    print("JUNOS MCP SERVER — CONNECTION POOL BENCHMARK")
    print("{} routers x {} commands = {} device operations".format(n_routers, n_commands, n_ops))
    print("=" * 110)
    print()

    hdr = "{:<45} {:>14} {:>14} {:>14}".format(
        "Command", "Original", "Pool+Seq", "Pool+Parallel"
    )
    print(hdr)
    print("-" * 110)

    for i, (cmd, orig_t) in enumerate(orig_results):
        seq_t = seq_results[i][1]
        par_t = par_results[i][1]
        row = "{:<45} {:>13.3f}s {:>13.3f}s {:>13.3f}s".format(
            cmd, orig_t, seq_t, par_t
        )
        print(row)

    print("-" * 110)

    orig_sum = round(sum(t for _, t in orig_results), 3)
    seq_sum = round(sum(t for _, t in seq_results), 3)
    par_sum = round(sum(t for _, t in par_results), 3)

    row = "{:<45} {:>13.3f}s {:>13.3f}s {:>13.3f}s".format(
        "TOTAL", orig_sum, seq_sum, par_sum
    )
    print(row)
    print()

    print("SPEEDUP vs Original:")
    print(
        "  Pool + Sequential:  {:.1f}x faster".format(
            orig_sum / seq_sum if seq_sum > 0 else 0
        )
    )
    print(
        "  Pool + Parallel:    {:.1f}x faster".format(
            orig_sum / par_sum if par_sum > 0 else 0
        )
    )
    print()

    print("CONNECTION OVERHEAD:")
    print(
        "  Original: {} SSH handshakes (connect + disconnect per call)".format(n_ops)
    )
    print(
        "  Pool:     {} SSH handshakes (reused across all {} calls)".format(
            n_routers, n_ops
        )
    )
    print("  Saved:   {} SSH handshakes".format(n_ops - n_routers))


def main():
    parser = argparse.ArgumentParser(description="Junos MCP Server Connection Pool Benchmark")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:30030/mcp",
        help="MCP server URL (default: http://127.0.0.1:30030/mcp)",
    )
    parser.add_argument(
        "--devices",
        default="devices.json",
        help="Path to devices.json (default: devices.json)",
    )
    args = parser.parse_args()

    devices_path = Path(args.devices)
    if not devices_path.is_absolute():
        devices_path = Path(__file__).resolve().parent.parent / devices_path

    with open(devices_path) as f:
        devices = json.load(f)

    routers = list(devices.keys())
    print("Routers: {}".format(", ".join(routers)))
    print()

    print("Running Scenario 1: Original (no pool, fresh SSH each time)...")
    orig_results, orig_total = run_original(devices, routers)

    print("Running Scenario 2 & 3: Pool+Sequential and Pool+Parallel...")
    seq_results, seq_total, par_results, par_total = asyncio.run(
        run_pooled(args.server, routers)
    )

    print_results(
        routers, orig_results, orig_total, seq_results, seq_total, par_results, par_total
    )


if __name__ == "__main__":
    main()
