from hashlib import sha256
from pathlib import Path


def compute_file_checksum(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute a stable SHA-256 checksum for a file."""
    digest = sha256()

    with open(file_path, "rb") as file_obj:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()
