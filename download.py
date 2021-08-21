import json
import os
import time
from pathlib import Path
from typing import Dict

from fire import Fire
from tqdm import tqdm

from utils import FernetEncoder, GitRepo, Config, Synchronizer, ReversedEncoder


class ReversedSynchronizer(Synchronizer):
    # Assumes files with previously encoded with non-deterministic encryption
    def run_pattern(self, pattern: str, folder_in: Path, folder_out: Path):
        # paths_in = sorted(self.glob(pattern, folder_in))
        # paths_out = sorted(self.glob(pattern, folder_out))
        # encoded = self.encode_paths(paths_in)
        # paths_map = {encoded[i]: p for i, p in enumerate(paths_in)}

        paths_in = sorted(self.glob("*", folder_in))
        paths_out = sorted(self.glob(pattern, folder_out))
        encoded = self.encode_paths(paths_in)
        is_match = [p.resolve().match(pattern) for p in encoded]
        paths_in = [p for i, p in enumerate(paths_in) if is_match[i]]
        encoded = [p for i, p in enumerate(encoded) if is_match[i]]
        paths_map = {encoded[i]: p for i, p in enumerate(paths_in)}

        for p in set(paths_out) - set(encoded):
            os.remove(folder_out / p)
            self.path_to_hash.pop(p)
            print(dict(remove=p))

        to_add: Dict[Path, Path] = {}
        for p, p_in in paths_map.items():
            hash_in = self.read_hash(folder_in / p_in)
            if self.path_to_hash.get(p, "") != hash_in:
                to_add[p_in] = p
                self.path_to_hash[p] = hash_in
                print(dict(add=p))
        self.add_files(to_add, folder_in, folder_out)


def main(path_config: str = "config.json"):
    with open(path_config) as f:
        config = Config(**json.load(f))

    git = GitRepo(root=".")
    encoder = ReversedEncoder(encoder=FernetEncoder(key=config.encode_key))
    path_drive = Path(config.path_drive).resolve(strict=True)
    synchronizers = []

    for f in config.folders:
        folder_out = Path(f.path).resolve()
        folder_in = path_drive / folder_out.name
        synchronizers.append(
            ReversedSynchronizer(
                patterns=f.file_patterns,
                folder_in=folder_in,
                folder_out=folder_out,
                text_encoder=encoder,
                path_encoder=encoder,
                validate_encoding=False,
            )
        )

    for _ in tqdm(range(int(1e6))):
        try:
            git.pull()
            for s in synchronizers:
                s.run()
        except AssertionError as e:
            print(e)
            time.sleep(60)

        time.sleep(config.update_interval)


if __name__ == "__main__":
    Fire(main)
