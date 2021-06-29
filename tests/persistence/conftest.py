import os
import shutil
import time

import pytest

import localstack.config
from localstack.utils.aws import aws_stack
from tests import runtime

TIMEOUT = 30


class PersistentRuntime:
    data_dir: str

    def __init__(self, rt, data_dir) -> None:
        super().__init__()
        self.runtime = rt
        self.data_dir = data_dir


@pytest.fixture
def persistent_runtime(tmpdir):
    try:
        os.environ['DATA_DIR'] = str(tmpdir.realpath())
        localstack.config.DATA_DIR = str(tmpdir.realpath())
        if not runtime.start(timeout=TIMEOUT):
            raise IOError('did not startup localstack in time')
        time.sleep(0.5)
        yield PersistentRuntime(runtime, tmpdir)
    finally:
        runtime.reset()
        shutil.rmtree(localstack.config.DATA_DIR, ignore_errors=True)

@pytest.fixture
def dynamodb():
    service = aws_stack.connect_to_service('dynamodb')
    yield service
