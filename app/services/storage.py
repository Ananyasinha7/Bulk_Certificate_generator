import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, job_id: UUID, certificate_id: UUID, data: bytes) -> str:
        relative = f"{job_id}/{certificate_id}.pdf"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return relative

    def path(self, relative: str) -> Path:
        return self.root / relative

    def archive(self, entries: Iterable[tuple[str, str]]) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as handle:
            with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, relative in entries:
                    archive.write(self.path(relative), name)
        return Path(handle.name)
