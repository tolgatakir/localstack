"""
Module for starting and stopping localstack instances in a thread. Useful for writing integration tests or test
fixtures.
"""
import logging
import multiprocessing as mp
import os
import threading

from localstack import config
from localstack.constants import ENV_INTERNAL_TEST_RUN
from localstack.services import infra
from localstack.utils.analytics.profiler import profiled
from localstack.utils.common import safe_requests

LOG = logging.getLogger(__name__)

_started = mp.Event()  # event indicating whether localstack has been started
_stop = mp.Event()  # event that can be triggered to stop localstack
_stopped = mp.Event()  # event indicating that localstack has been stopped
_startup_monitor_event = mp.Event()  # event that can be triggered to start localstack

_runtime_thread = None

_cmd_lock = mp.Lock()


def start(wait=True, timeout=None):
    global _runtime_thread

    with _cmd_lock:
        if _startup_monitor_event.is_set():
            _started.wait(timeout=timeout)
            return

        _runtime_thread = threading.Thread(target=_run_startup_monitor).start()

        _startup_monitor_event.set()
        if wait:
            _started.wait(timeout=timeout)


def stop():
    _stop.set()
    _startup_monitor_event.set()


def join(timeout=None):
    global _runtime_thread

    if _runtime_thread is None:
        _startup_monitor_event.wait(timeout=None)

    if _runtime_thread is None:
        return

    _runtime_thread.join(timeout=timeout)
    _stopped.wait()


def reset():
    global _runtime_thread

    stop()
    join()
    _runtime_thread = None
    _started.clear()
    _stop.clear()
    _stopped.clear()
    _startup_monitor_event.clear()


def _run_startup_monitor() -> None:
    """
    The startup monitor is a thread that waits for the _startup_monitor_event and, once the event is true, starts a
    localstack instance in it's own thread context.
    """
    LOG.info('waiting on localstack_start signal')
    _startup_monitor_event.wait()

    if _stop.is_set():
        # this is called if _trigger_stop() is called before any test has requested the localstack_runtime fixture.
        LOG.info('ending startup_monitor')
        _stopped.set()
        return

    LOG.info('running localstack')
    _run_localstack()


def _run_localstack():
    """
    Start localstack and block until it terminates. Terminate localstack by calling _trigger_stop().
    """
    # configure
    os.environ[ENV_INTERNAL_TEST_RUN] = '1'
    safe_requests.verify_ssl = False
    config.FORCE_SHUTDOWN = False

    def watchdog():
        LOG.info('waiting stop event')
        _stop.wait()  # triggered by _trigger_stop()
        LOG.info('stopping infra')
        infra.stop_infra()

    def start_profiling(*args):
        if not config.USE_PROFILER:
            return

        @profiled()
        def profile_func():
            # keep profiler active until tests have finished
            _stopped.wait()

        print('Start profiling...')
        profile_func()
        print('Done profiling...')

    monitor = threading.Thread(target=watchdog)
    monitor.start()

    LOG.info('starting localstack infrastructure')
    infra.start_infra(asynchronous=True)

    threading.Thread(target=start_profiling).start()

    LOG.info('waiting for infra to be ready')
    infra.INFRA_READY.wait()  # wait for infra to start (threading event)
    _started.set()  # set conftest inter-process Event

    LOG.info('waiting for shutdown')
    try:
        LOG.info('waiting for watchdog to join')
        monitor.join()
    finally:
        LOG.info('ok bye')
        _stopped.set()
