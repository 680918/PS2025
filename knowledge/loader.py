from pathlib import Path

from knowledge.models import KnowledgeDocument


SUPPORTED_EXTENSIONS = {".md", ".txt"}


def load_document(file_path):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"暂不支持的文件类型: {path.suffix}")

    content = path.read_text(encoding="utf-8")

    return KnowledgeDocument(
        title=path.stem,
        content=content,
        source=str(path),
    )
