import json
import shutil
import time
from pathlib import Path

from fire import Fire
from tqdm import tqdm

from utils import FernetEncoder, GitRepo, Config, Synchronizer


def main(path_config: str = "config.json"):
    with open(path_config) as f:
        config = Config(**json.load(f))

    git = GitRepo(root=config.path_drive)
    git.clone(config.repo_drive)
    encoder = FernetEncoder(key=config.encode_key)
    path_drive = Path(config.path_drive).resolve()
    synchronizers = []

    for f in config.folders:
        folder_in = Path(f.path).resolve(strict=True)
        folder_out = path_drive / folder_in.name
        synchronizers.append(
            Synchronizer(
                patterns=f.file_patterns,
                folder_in=folder_in,
                folder_out=folder_out,
                text_encoder=encoder,
                path_encoder=encoder,
                validate_encoding=True,
            )
        )

    for _ in tqdm(range(int(1e6))):
        try:
            for s in synchronizers:
                s.run()

            git.add([path_drive])
            if git.diff_staged():
                git.commit(message="Sync")
                git.push()
        except AssertionError as e:
            print(e)
            time.sleep(60)

        time.sleep(config.update_interval)


if __name__ == "__main__":
    Fire(main)
