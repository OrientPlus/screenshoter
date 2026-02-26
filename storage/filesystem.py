from pathlib import Path
from os import getenv
from rabbit.models import StorageJob


class Storage:
    def __init__(self):
        path = getenv("STORAGE_DIR", "/runtime")
        self._base_save_directory = Path(path)
        self._base_save_directory.mkdir(parents=True, exist_ok=True)

    def save(self, job: StorageJob) -> None:
        scr_bytes = self._decode_image(job.image_hex, job.job_id)
        scr_path = self._build_path(job.job_id)

        self._write_file(scr_path, scr_bytes, job.job_id)

    @staticmethod
    def _decode_image(image_hex: str, job_id: str) -> bytes:
        try:
            return bytes.fromhex(image_hex)

        except ValueError as e:
            raise ValueError(
                f"Job {job_id}: invalid image hex value: {e}"
            ) from e

    def _build_path(self, job_id: str) -> Path:
        return self._base_save_directory / f"{Path(job_id).name}.png"

    @staticmethod
    def _write_file(scr_path: Path, scr_bytes: bytes, job_id: str) -> None:
        tmp_path = scr_path.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(scr_bytes)
            tmp_path.rename(scr_path)

        except OSError as e:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise OSError(
                f"Job {job_id}: error write file {scr_path}: {e}"
            ) from e
