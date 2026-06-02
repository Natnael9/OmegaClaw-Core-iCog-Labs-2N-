import yaml
from py_landlock import Landlock, AccessFs
from pathlib import Path
import enum
import os

class LandLockCompatibility(enum.Enum):
    BEST_EFFORT = 0,
    HARD_REQUIREMENT = 1,

class FileSystemPolicy:

    READ_ONLY_DIR_ACCESS = AccessFs.READ_DIR | AccessFs.READ_FILE
    READ_ONLY_FILE_ACCESS = AccessFs.READ_FILE
    READ_WRITE_DIR_ACCESS = (AccessFs.READ_FILE | AccessFs.READ_DIR
                             | AccessFs.WRITE_FILE | AccessFs.TRUNCATE
                             | AccessFs.MAKE_REG | AccessFs.MAKE_DIR
                             | AccessFs.MAKE_SYM | AccessFs.REMOVE_FILE
                             | AccessFs.REMOVE_DIR)
    READ_WRITE_FILE_ACCESS = (AccessFs.READ_FILE | AccessFs.WRITE_FILE |
                              AccessFs.TRUNCATE)

    def __init__(self):
        self._strict = LandLockCompatibility.BEST_EFFORT
        self._read_only = []
        self._read_write = []

    def load_file(self, path: str|Path):
        policy = None
        with open(path, "r") as f:
            policy = yaml.safe_load(f)
        self.load_dict(policy)

    def load_str(self, policy: str):
        policy = yaml.safe_load(policy)
        self.load_dict(policy)

    def load_dict(self, policy: dict):
        version = policy.get('version')
        assert version == 1

        self._strict = LandLockCompatibility.BEST_EFFORT
        ll = policy.get('landlock')
        if ll:
            comp = ll.get('compatibility')
            if comp:
                self._strict = LandLockCompatibility[comp.upper()]

        fs = policy.get('filesystem_policy')

        ro = []
        rw = []
        if fs:
            ro = fs.get('read_only', [])
            if ro is None:
                ro = []
            rw = fs.get('read_write', [])
            if rw is None:
                ro = []
            if policy.get('include_workdir'):
                rw.append(os.getcwd())
        self._read_only = [Path(f'{p}') for p in ro]
        self._read_write = [Path(f'{p}') for p in rw]

    def apply(self):
        rod = list(filter(lambda p: p.is_dir(), self._read_only))
        rof = list(filter(lambda p: p.is_file(), self._read_only))
        rwd = list(filter(lambda p: p.is_dir(), self._read_write))
        rwf = list(filter(lambda p: p.is_file(), self._read_write))

        Landlock(strict=self._strict) \
            .add_path_rule(*rwd, access=FileSystemPolicy.READ_WRITE_DIR_ACCESS) \
            .add_path_rule(*rwf, access=FileSystemPolicy.READ_WRITE_FILE_ACCESS) \
            .add_path_rule(*rod, access=FileSystemPolicy.READ_ONLY_DIR_ACCESS) \
            .add_path_rule(*rof, access=FileSystemPolicy.READ_ONLY_FILE_ACCESS) \
            .apply()

# Unit tests

import pytest
import tempfile
import multiprocessing

_TEST_POLICY_YAML = """
version: 1
filesystem_policy:
  include_workdir: true
  read_only:
  - {dir}/ro_dir
  - {dir}/ro_file
  read_write:
  - .pytest_cache
  - {dir}/rw_dir
  - {dir}/rw_file
landlock:
  compatibility: hard_requirement
"""

@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Fixture creates the test directory structure"""
    dir = tmp_path_factory.mktemp("dir")
    Path(f"{dir}/ro_dir").mkdir()
    temp_file(f"{dir}/ro_dir/file", "Read only file")
    temp_file(f"{dir}/ro_file", "Read only file")
    Path(f"{dir}/rw_dir").mkdir()
    temp_file(f"{dir}/rw_dir/file", "Read-write file")
    temp_file(f"{dir}/rw_file", "Read-write file")
    return dir

def apply_policy_to_dir(dir):
    """Apply _TEST_POLICY_YAML file policy to the passed dir"""
    text = _TEST_POLICY_YAML.format(dir=dir)
    policy = FileSystemPolicy()
    policy.load_str(text)
    policy.apply()

def run_in_separate_process(func, args):
    """Run func(queue, *args) in a separate process

    It is expected that func puts tuple (Bool, str) into the queue to return
    the result. First element of the tuple means if the test was successful,
    second element of the tuple contains error message if first element is
    False. This is required to allow applying test policy in subprocess only
    without restricting the test harness by the policy.
    """
    q = multiprocessing.Queue()
    proc = multiprocessing.Process(target=exception_catcher, args=(q, func, args))
    proc.start()
    proc.join()
    (passed, message) = q.get()
    assert passed, message

def exception_catcher(q, func, args):
    """Trampoline used to catch any exceptions thrown by func(q, *args)
    call."""
    try:
        func(q, *args)
    except Exception as e:
        q.put((False, f"Unexpected exception: {repr(e)}"))

def temp_file(path, text):
    with open(path, "w") as f:
        f.write(text)

def test_read_write_dir(temp_dir):
    run_in_separate_process(process_test_read_write_dir, (temp_dir,))

def process_test_read_write_dir(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        # new dir
        Path(f"{temp_dir}/rw_dir/new_dir").mkdir()
        with open(f"{temp_dir}/rw_dir/new_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/rw_dir/new_dir/new_file").unlink()
        Path(f"{temp_dir}/rw_dir/new_dir").rmdir()

        # new file
        with open(f"{temp_dir}/rw_dir/new_file", "w") as f:
            f.write("Hello, world!")
        Path(f"{temp_dir}/rw_dir/new_file").unlink()

        # old file write
        with open(f"{temp_dir}/rw_dir/file", "w") as f:
            f.write("Hello, world!")

        # old file remove
        Path(f"{temp_dir}/rw_dir/file").unlink()
    except PermissionError:
        q.put((False, f"Cannot write to read-write directory"))
    q.put((True, None))

def test_read_only_dir(temp_dir):
    run_in_separate_process(process_test_read_only_dir, (temp_dir,))

def process_test_read_only_dir(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        Path(f"{temp_dir}/ro_dir/new_dir").mkdir()
        q.put((False, "Can create subdir in the read-only dir"))
    except PermissionError as e:
        pass
    try:
        with open(f"{temp_dir}/ro_dir/new_file", "w") as f:
            f.write("Hello, world!")
        q.put((False, "Can create file in the read-only dir"))
    except PermissionError as e:
        pass
    q.put((True, None))

def test_read_only_file(temp_dir):
    run_in_separate_process(process_test_read_only_file, (temp_dir,))

def process_test_read_only_file(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        with open(f"{temp_dir}/ro_file", "w") as f:
            f.write("Hello, world!")
        q.put((False, "Can write to read-only file"))
    except PermissionError as e:
        pass
    q.put((True, None))

def test_read_write_file(temp_dir):
    run_in_separate_process(process_test_read_write_file, (temp_dir,))

def process_test_read_write_file(q, temp_dir):
    apply_policy_to_dir(temp_dir)
    try:
        with open(f"{temp_dir}/rw_file", "w") as f:
            f.write("Hello, world!")
    except PermissionError:
        q.put((False, f"Cannot write to read-write file"))
    q.put((True, None))
