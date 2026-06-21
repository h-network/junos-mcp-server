#!/usr/bin/env python3
"""Unit tests for the SSH/NETCONF ConnectionPool lifecycle.

Focus: reload must drop pooled connections WITHOUT killing the pool's
idle-cleanup thread, while shutdown must stop it.
"""

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import jmcp


class ConnectionPoolLifecycleTests(unittest.TestCase):
    def setUp(self):
        # Explicit idle_timeout so the test is independent of JMCP_POOL_IDLE_TIMEOUT.
        self.pool = jmcp.ConnectionPool(idle_timeout=300)

    def tearDown(self):
        # Always stop the background cleanup thread after each test.
        self.pool.close_all(shutdown=True)

    def _inject_fake_connection(self, name="R1"):
        fake_device = MagicMock()
        self.pool._connections[name] = {
            "device": fake_device,
            "lock": threading.Lock(),
            "last_used": 1.0,
        }
        return fake_device

    def test_pool_starts_with_running_cleanup_thread(self):
        self.assertTrue(self.pool._running)
        self.assertTrue(self.pool._cleanup_thread.is_alive())

    def test_reload_keeps_cleanup_thread_alive(self):
        # Regression: close_all(shutdown=False) is the reload path. It must NOT
        # disable the idle-cleanup loop (old code set _running=False here, which
        # permanently killed the janitor for the rest of the process's life).
        self.pool.close_all(shutdown=False)
        self.assertTrue(self.pool._running)
        self.assertTrue(self.pool._cleanup_thread.is_alive())

    def test_shutdown_stops_cleanup(self):
        self.pool.close_all(shutdown=True)
        self.assertFalse(self.pool._running)

    def test_reload_closes_and_clears_connections(self):
        fake_device = self._inject_fake_connection("R1")
        self.pool.close_all(shutdown=False)
        fake_device.close.assert_called_once()
        self.assertEqual(self.pool._connections, {})


if __name__ == "__main__":
    unittest.main()
