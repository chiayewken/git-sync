# git-sync

Synchronize files from local machine to remote server using GitHub

## Install

```
conda env create --file environment.yml
```

## Usage

On your local machine:

- Edit `config_sample.json` and copy to `config.json`

```
{
  "repo_drive": "YOUR_REPO_URL",
  "path_drive": "../drive",
  "encode_key": "YOUR_KEY",
  "update_interval": 1,
  "folders": [
    {
      "path": "YOUR_PROJECT_FOLDER",
      "file_patterns": ["**/*.py", "**/*.sh"]
    }
  ]
}
```

- YOUR_REPO_URL: Create a private GitHub repo
- YOUR_KEY: `python utils.py generate_key`
- YOUR_PROJECT_FOLDER: Project that you want to synchronize

```
python upload.py
```

On the remote server:

- Follow steps to install
- Copy `config.json` from previous steps
- `python download.py`
