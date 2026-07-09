import sys

from charybdis.parallel import MAX_WORKERS, pool_workers


def test_pool_workers_forces_serial_inside_pytest():
    assert pool_workers(31) == 1


def test_pool_workers_caps_standalone_processes(monkeypatch):
    with monkeypatch.context() as context:
        context.delitem(sys.modules, "pytest", raising=False)
        context.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert pool_workers(1000) == MAX_WORKERS == 31
        assert pool_workers(0) == 1
