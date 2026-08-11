from pathlib import Path

PROMPT_DIR = Path(__file__).parent

PROMPT_FILE = "v1.txt"
PROMPT_PATH = PROMPT_DIR / PROMPT_FILE

PROMPT = PROMPT_PATH.read_text()

PROMPT_VERSION = int(PROMPT_FILE.removeprefix("v").removesuffix(".txt"))


def load_prompt(version: int) -> str:
    path = PROMPT_DIR / f"v{version}.txt"
    return path.read_text()


def get_next_prompt_version() -> int:
    versions = []

    for path in PROMPT_DIR.glob("v*.txt"):
        version = int(path.stem.removeprefix("v"))
        versions.append(version)

    return max(versions, default=0) + 1


def write_to_prompt_txt(
    version: int,
    content: str,
) -> None:
    path = PROMPT_DIR / f"v{version}.txt"
    path.write_text(content)


def delete_prompt_txt(version: int) -> None:
    path = PROMPT_DIR / f"v{version}.txt"
    path.unlink(missing_ok=True)
