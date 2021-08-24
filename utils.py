import hashlib
import os
import subprocess
from pathlib import Path
from typing import List, Set, Dict

from cryptography.fernet import Fernet
from fire import Fire
from pydantic import BaseModel


class Encoder(BaseModel):
    def run(self, contents: List[bytes]) -> List[bytes]:
        raise NotImplementedError

    def inverse(self, contents: List[bytes]) -> List[bytes]:
        raise NotImplementedError


class ReversedEncoder(Encoder):
    encoder: Encoder

    def run(self, contents: List[bytes]) -> List[bytes]:
        return self.encoder.inverse(contents)

    def inverse(self, contents: List[bytes]) -> List[bytes]:
        return self.encoder.run(contents)


class FernetEncoder(Encoder):
    key: str

    def run(self, contents: List[bytes]) -> List[bytes]:
        f = Fernet(self.key.encode())
        encoded = [f.encrypt(c) for c in contents]
        assert self.inverse(encoded) == contents
        return encoded

    def inverse(self, contents: List[bytes]) -> List[bytes]:
        f = Fernet(self.key.encode())
        return [f.decrypt(c) for c in contents]


def test_encoder():
    text = "This is my sentence"
    encoder = FernetEncoder(key=Fernet.generate_key().decode())
    x = encoder.run([text.encode()])[0]
    y = encoder.inverse([x])[0]
    x2 = encoder.run([y])[0]
    y2 = encoder.inverse([x2])[0]
    print(dict(key=encoder.key, text=text, x=x, y=y.decode(), x2=x2, y2=y2.decode()))


class Folder(BaseModel):
    path: str
    file_patterns: List[str]


def read_paths(paths: List[Path]) -> List[bytes]:
    contents = []
    for p in paths:
        with open(p, "rb") as f:
            contents.append(f.read())
    return contents


class Synchronizer(BaseModel):
    patterns: List[str]
    folder_in: Path
    folder_out: Path
    text_encoder: Encoder
    path_encoder: Encoder
    validate_encoding: bool
    path_to_hash: Dict[Path, str] = {}

    @staticmethod
    def glob(pattern: str, folder: Path) -> Set[Path]:
        depth = len(folder.parts)
        return set([Path(*p.parts[depth:]) for p in folder.glob(pattern)])

    @staticmethod
    def read_hash(path: Path) -> str:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def add_files(self, paths_map: Dict[Path, Path], folder_in: Path, folder_out: Path):
        texts = read_paths([folder_in / p for p in paths_map.keys()])
        encoded = self.text_encoder.run(texts)
        paths_out = [folder_out / p for p in paths_map.values()]
        for i, p in enumerate(paths_out):
            if not p.parent.exists():
                p.parent.mkdir(exist_ok=True, parents=True)
            with open(p, "wb") as f:
                f.write(encoded[i])
        if self.validate_encoding:
            assert self.text_encoder.inverse(read_paths(paths_out)) == texts

    def encode_paths(self, paths: List[Path]) -> List[Path]:
        encoded = self.path_encoder.run([str(p).encode() for p in paths])
        paths_out = [Path(e.decode()) for e in encoded]
        if self.validate_encoding:
            assert self.decode_paths(paths_out) == paths
        return paths_out

    def decode_paths(self, paths: List[Path]) -> List[Path]:
        decoded = self.path_encoder.inverse([str(p).encode() for p in paths])
        paths_out = [Path(d.decode()) for d in decoded]
        return paths_out

    def run_pattern(self, pattern: str, folder_in: Path, folder_out: Path):
        paths_in = sorted(self.glob(pattern, folder_in))
        paths_out = sorted(self.glob("*", folder_out))
        encoded = self.encode_paths(paths_in)
        decoded = self.decode_paths(paths_out)
        is_match = [p.resolve().match(pattern) for p in decoded]
        decoded = [p for i, p in enumerate(decoded) if is_match[i]]
        paths_out = [p for i, p in enumerate(paths_out) if is_match[i]]
        paths_map = {p: encoded[i] for i, p in enumerate(paths_in)}
        paths_map.update({decoded[i]: p for i, p in enumerate(paths_out)})

        for p in set(decoded) - set(paths_in):
            os.remove(folder_out / paths_map[p])
            self.path_to_hash.pop(p)
            print(dict(remove=p))

        to_add: Dict[Path, Path] = {}
        for p in paths_in:
            hash_in = self.read_hash(folder_in / p)
            if self.path_to_hash.get(p, "") != hash_in:
                to_add[p] = paths_map[p]
                self.path_to_hash[p] = hash_in
                print(dict(add=p))
        self.add_files(to_add, folder_in, folder_out)

    def run(self):
        for p in self.patterns:
            self.run_pattern(p, self.folder_in, self.folder_out)


class Config(BaseModel):
    repo_drive: str
    path_drive: str
    encode_key: str
    update_interval: int
    folders: List[Folder]


class ShellOutput(BaseModel):
    text: str
    error: str
    is_success: bool


def run_shell(command: str) -> ShellOutput:
    process = subprocess.run(command.split(), capture_output=True)
    return ShellOutput(
        text=process.stdout.decode(),
        error=process.stderr.decode(),
        is_success=process.returncode == 0,
    )


class GitRepo(BaseModel):
    root: str

    def clone(self, url: str):
        if not Path(self.root).exists():
            command = f"git clone {url} {self.root}"
            output = run_shell(command)
            assert output.is_success

    @property
    def prefix(self) -> str:
        path_full = Path(self.root).resolve(strict=True)
        return f"git -C {path_full}"

    def diff_staged(self) -> str:
        output = run_shell(f"{self.prefix} diff --staged")
        assert output.is_success
        return output.text

    def add(self, paths: List[Path]):
        for p in paths:
            path_full = p.resolve(strict=True)
            output = run_shell(f"{self.prefix} add --all {path_full}")
            assert output.is_success

    def commit(self, message: str):
        assert message
        assert "'" not in message
        output = run_shell(f"{self.prefix} commit --message '{message}'")
        assert output.is_success

    def push(self):
        output = run_shell(f"{self.prefix} push")
        assert output.is_success

    def pull(self):
        output = run_shell(f"{self.prefix} pull")
        assert output.is_success


def test_shell():
    git = GitRepo(root=".")
    git.add([Path("README.md")])
    print(dict(diff=git.diff_staged()))


def generate_key():
    print(Fernet.generate_key().decode())


if __name__ == "__main__":
    Fire()
