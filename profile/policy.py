import yaml
from py_landlock import Landlock, AccessFs
from pathlib import Path
import enum
import os

def apply_security_policy(path):
    try:
        if path:
            policy = FileSystemPolicy()
            policy.load_file(path)
            policy.apply()
        else:
            print("[policy.apply_security_policy]: securityPolicyPath is not set")
    except Exception as e:
        print(f"[policy.apply_security_policy]: Unexpected exception: {e}")
        raise

class LandLockCompatibility(enum.Enum):
    BEST_EFFORT = 0
    HARD_REQUIREMENT = 1

class FileSystemPolicy:

    READ_ONLY_DIR_ACCESS = AccessFs.READ_DIR | AccessFs.READ_FILE
    READ_ONLY_FILE_ACCESS = AccessFs.READ_FILE
    READ_WRITE_DIR_ACCESS = (AccessFs.READ_FILE | AccessFs.READ_DIR
                             | AccessFs.WRITE_FILE | AccessFs.TRUNCATE
                             | AccessFs.MAKE_REG | AccessFs.MAKE_DIR
                             | AccessFs.MAKE_SYM | AccessFs.REMOVE_FILE
                             | AccessFs.REMOVE_DIR | AccessFs.MAKE_FIFO
                             | AccessFs.MAKE_SOCK)
    READ_WRITE_FILE_ACCESS = (AccessFs.READ_FILE | AccessFs.WRITE_FILE |
                              AccessFs.TRUNCATE)

    def __init__(self):
        self._compatibility = LandLockCompatibility.BEST_EFFORT
        self._read_only = []
        self._read_write = []

    def load_file(self, path: str|Path):
        print(f"[FileSystemPolicy.load_file] loading policy from file {path}")
        policy = None
        with open(path, "r") as f:
            policy = yaml.safe_load(f)
        self.load_dict(policy)

    def load_str(self, policy: str):
        policy = yaml.safe_load(policy)
        self.load_dict(policy)

    def load_dict(self, policy: dict):
        # 1. Determine the Project Root (Absolute path)
        ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

        fs = policy.get('filesystem_policy', {})
        
        # 2. Get your lists
        ro = fs.get('read_only', []) or []
        rw = fs.get('read_write', []) or []
        
        # 3. Handle 'include_workdir'
        if fs.get('include_workdir', False):
            rw.append(str(Path.cwd().resolve()))

        # 4. Define the Universal Resolver
        def resolve_path(p):
            path_obj = Path(p).expanduser()
            # If it's absolute, use as-is. If relative, anchor to ROOT_DIR
            final_path = path_obj if path_obj.is_absolute() else (ROOT_DIR / path_obj)
            
            # Resolve to canonical absolute path
            resolved = final_path.resolve()
            
            # 5. Security: Only return existing paths to prevent Landlock PathError
            return resolved if resolved.exists() else None

        # Apply and filter
        self._read_only = [p for p in (resolve_path(p) for p in ro) if p is not None]
        self._read_write = [p for p in (resolve_path(p) for p in rw) if p is not None]

    def apply(self):
        rod = list(filter(lambda p: p.is_dir(), self._read_only))
        rof = list(filter(lambda p: not p.is_dir(), self._read_only))
        rwd = list(filter(lambda p: p.is_dir(), self._read_write))
        rwf = list(filter(lambda p: not p.is_dir(), self._read_write))

        strict = self._compatibility == LandLockCompatibility.HARD_REQUIREMENT
        Landlock(strict=strict) \
            .allow_all_scope() \
            .allow_all_network() \
            .add_path_rule('/', access=AccessFs.EXECUTE) \
            .add_path_rule(*rwd, access=FileSystemPolicy.READ_WRITE_DIR_ACCESS) \
            .add_path_rule(*rwf, access=FileSystemPolicy.READ_WRITE_FILE_ACCESS) \
            .add_path_rule(*rod, access=FileSystemPolicy.READ_ONLY_DIR_ACCESS) \
            .add_path_rule(*rof, access=FileSystemPolicy.READ_ONLY_FILE_ACCESS) \
            .apply()

        print("[FileSystemPolicy.load_file] policy applied")
