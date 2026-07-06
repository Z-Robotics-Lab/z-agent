# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Process-singleton ROS2 runtime.

Owns ONE MultiThreadedExecutor and ONE spin thread for the entire
process lifetime.  Replaces the pattern where each ROS2 proxy calls
``rclpy.spin(node)`` in its own thread, which triggers the
``Executor is already spinning`` crash in rclpy's global default executor.

Usage::

    from zeno.hardware.ros2.runtime import get_ros2_runtime

    runtime = get_ros2_runtime()
    runtime.add_node(my_node)
    ...
    runtime.remove_node(my_node)
    # shutdown is registered with atexit automatically
"""
from __future__ import annotations

import atexit
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------

_runtime: Ros2Runtime | None = None
_singleton_lock: threading.Lock = threading.Lock()


# ---------------------------------------------------------------------------
# Ros2Runtime
# ---------------------------------------------------------------------------


class Ros2Runtime:
    """Process-singleton holder for rclpy executor + nodes.

    Do not instantiate directly — use :func:`get_ros2_runtime`.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._executor: Any | None = None
        self._spin_thread: threading.Thread | None = None
        self._nodes: set[Any] = set()
        self._we_inited_rclpy: bool = False
        self._atexit_registered: bool = False
        self._is_running: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_node(self, node: Any) -> None:
        """Register *node* with the shared executor.

        Idempotent on the same node object.  Starts the singleton spin
        thread on the first call.  Thread-safe.
        """
        # Deferred import so ``import runtime`` works without rclpy installed.
        import rclpy  # noqa: PLC0415
        import rclpy.executors  # noqa: PLC0415

        with self._lock:
            # --- rclpy lifecycle ---
            # Guard: only init once per runtime instance.  We track
            # _we_inited_rclpy ourselves rather than relying on rclpy.ok()
            # which may remain False on mock objects during tests.
            if not self._we_inited_rclpy and not rclpy.ok():
                rclpy.init()
                self._we_inited_rclpy = True
                logger.debug("rclpy.init() called by Ros2Runtime")

            # --- executor ---
            if self._executor is None:
                self._executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
                logger.debug("MultiThreadedExecutor created (num_threads=4)")

            # --- spin thread ---
            if self._spin_thread is None:
                self._spin_thread = threading.Thread(
                    target=self._spin_loop,
                    daemon=True,
                    name="ros2-runtime-spin",
                )
                self._spin_thread.start()
                self._is_running = True
                logger.debug("Spin thread started")

            # --- atexit registration (once only) ---
            if not self._atexit_registered:
                atexit.register(self.shutdown)
                self._atexit_registered = True

            # --- register node ---
            if node not in self._nodes:
                self._executor.add_node(node)
                self._nodes.add(node)
                logger.debug("Node added: %s", node)

    def _spin_loop(self) -> None:
        """Spin-thread body: run the executor, swallowing the post-shutdown race.

        When :meth:`shutdown` calls ``executor.shutdown()``, the executor's
        internal thread pool is torn down while this thread may still be mid
        ``spin_once`` and about to submit a callback — rclpy then raises
        ``RuntimeError: cannot schedule new futures after shutdown``. Because
        ``shutdown`` clears ``_is_running`` FIRST, that exception is expected
        teardown noise (debug), not a crash (warning).
        """
        executor = self._executor
        try:
            executor.spin()
        except Exception:  # noqa: BLE001 — see docstring
            if self._is_running:
                logger.warning("Spin thread crashed while running", exc_info=True)
            else:
                logger.debug("Spin thread exited during shutdown", exc_info=True)

    def remove_node(self, node: Any) -> None:
        """Unregister *node* from the executor.

        Does NOT destroy the node — the caller owns it.  Thread-safe.
        """
        with self._lock:
            if self._executor is not None and node in self._nodes:
                self._executor.remove_node(node)
                self._nodes.discard(node)
                logger.debug("Node removed: %s", node)

    def shutdown(self) -> None:
        """Stop executor, join spin thread, call rclpy.shutdown if we initialised it.

        Called at process exit via atexit or by explicit teardown code.
        Thread-safe; safe to call multiple times (idempotent after first call).
        """
        with self._lock:
            executor = self._executor
            spin_thread = self._spin_thread

            # Mark not-running FIRST so _spin_loop treats the RuntimeError that
            # executor.shutdown() races into the spinning thread ("cannot
            # schedule new futures after shutdown") as expected teardown noise,
            # not a crash.
            self._is_running = False

            if executor is not None:
                try:
                    executor.shutdown()
                    logger.debug("Executor shut down")
                except Exception:  # noqa: BLE001
                    logger.warning("Exception during executor.shutdown()", exc_info=True)
                self._executor = None

            # Join AFTER executor.shutdown() (which is what makes spin() return);
            # the wrapper has by now swallowed any post-shutdown RuntimeError.
            if spin_thread is not None:
                spin_thread.join(timeout=2.0)
                self._spin_thread = None
                logger.debug("Spin thread joined")

            if self._we_inited_rclpy:
                try:
                    import rclpy  # noqa: PLC0415

                    rclpy.shutdown()
                    logger.debug("rclpy.shutdown() called")
                except Exception:  # noqa: BLE001
                    logger.warning("Exception during rclpy.shutdown()", exc_info=True)
                self._we_inited_rclpy = False

            self._is_running = False

    @property
    def is_running(self) -> bool:
        """True while the spin thread is active."""
        return self._is_running


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_ros2_runtime() -> Ros2Runtime:
    """Return the process-singleton :class:`Ros2Runtime` (lazy, thread-safe)."""
    global _runtime  # noqa: PLW0603

    if _runtime is None:
        with _singleton_lock:
            if _runtime is None:
                _runtime = Ros2Runtime()
                logger.debug("Ros2Runtime singleton created")

    return _runtime
