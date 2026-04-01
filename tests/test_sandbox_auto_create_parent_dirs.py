import os
import shlex

os.environ["DEBUG"] = "false"

from src.infra.backend.daytona import DaytonaBackend
from src.infra.backend.e2b import E2BBackend


class _E2BFilesStub:
    def __init__(self, created_dirs: set[str]):
        self.created_dirs = created_dirs
        self.writes: list[tuple[str, str | bytes]] = []

    def write(self, path: str, data: str | bytes, format: str | None = None):
        parent = os.path.dirname(path) or "/"
        if parent not in self.created_dirs:
            raise FileNotFoundError(parent)
        self.writes.append((path, data))


class _E2BCommandsStub:
    def __init__(self, created_dirs: set[str]):
        self.created_dirs = created_dirs
        self.commands: list[str] = []

    def run(self, cmd: str, timeout: int):
        self.commands.append(cmd)
        parts = shlex.split(cmd)
        if len(parts) == 3 and parts[:2] == ["mkdir", "-p"]:
            self.created_dirs.add(parts[2])

        class _Result:
            stdout = ""
            stderr = ""
            exit_code = 0

        return _Result()


class _E2BSandboxStub:
    def __init__(self):
        self.created_dirs = {"/", "/tmp"}
        self.commands = _E2BCommandsStub(self.created_dirs)
        self.files = _E2BFilesStub(self.created_dirs)
        self.sandbox_id = "e2b-test"


class _DaytonaFSStub:
    def __init__(self, created_dirs: set[str]):
        self.created_dirs = created_dirs
        self.uploaded_destinations: list[str] = []

    def upload_files(self, uploads):
        for upload in uploads:
            parent = os.path.dirname(upload.destination) or "/"
            if parent not in self.created_dirs:
                raise FileNotFoundError(parent)
            self.uploaded_destinations.append(upload.destination)


class _DaytonaProcessStub:
    def __init__(self, created_dirs: set[str]):
        self.created_dirs = created_dirs
        self.commands: list[str] = []

    def exec(self, command: str, timeout: int, env: dict | None = None):
        self.commands.append(command)
        mkdir_command = command.split(" && ", 1)[0]
        parts = shlex.split(mkdir_command)
        if len(parts) == 3 and parts[:2] == ["mkdir", "-p"]:
            self.created_dirs.add(parts[2])

        class _Result:
            result = ""
            exit_code = 0

        return _Result()


class _DaytonaSandboxStub:
    def __init__(self):
        self.created_dirs = {"/", "/tmp", "/tmp/__daytona_transfer__"}
        self.fs = _DaytonaFSStub(self.created_dirs)
        self.process = _DaytonaProcessStub(self.created_dirs)
        self.id = "daytona-test"

    def get_work_dir(self):
        return "/workspace"


def test_e2b_write_creates_missing_parent_directories():
    backend = E2BBackend(sandbox=_E2BSandboxStub())

    result = backend.write("/home/user/generated/nested/file.txt", "hello")

    assert result.error is None
    assert result.path == "/home/user/generated/nested/file.txt"
    assert '/home/user/generated/nested' in backend._sandbox.created_dirs
    assert backend._sandbox.files.writes == [("/home/user/generated/nested/file.txt", "hello")]


def test_e2b_upload_files_creates_missing_parent_directories():
    backend = E2BBackend(sandbox=_E2BSandboxStub())

    responses = backend.upload_files([("/home/user/generated/nested/file.txt", b"hello")])

    assert responses[0].error is None
    assert '/home/user/generated/nested' in backend._sandbox.created_dirs
    assert backend._sandbox.files.writes == [("/home/user/generated/nested/file.txt", b"hello")]


def test_daytona_upload_files_creates_missing_parent_directories_for_ascii_paths():
    backend = DaytonaBackend(sandbox=_DaytonaSandboxStub())

    responses = backend.upload_files([("/workspace/generated/nested/file.txt", b"hello")])

    assert responses[0].error is None
    assert "/workspace/generated/nested" in backend._sandbox.created_dirs
    assert backend._sandbox.fs.uploaded_destinations == ["/workspace/generated/nested/file.txt"]


def test_e2b_write_quotes_parent_directory_commands():
    backend = E2BBackend(sandbox=_E2BSandboxStub())
    target_path = '/home/user/generated/with"quote/file.txt'

    backend.write(target_path, "hello")

    expected = f"mkdir -p {shlex.quote(os.path.dirname(target_path))}"
    assert backend._sandbox.commands.commands[0] == expected


def test_daytona_upload_quotes_parent_directory_commands():
    backend = DaytonaBackend(sandbox=_DaytonaSandboxStub())
    target_path = '/workspace/generated/with"quote/file.txt'

    backend.upload_files([(target_path, b"hello")])

    expected = f"mkdir -p {shlex.quote(os.path.dirname(target_path))}"
    assert backend._sandbox.process.commands[0] == expected
