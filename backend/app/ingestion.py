import hashlib
import io
import json
import stat
import zipfile
from pathlib import PurePosixPath
from .config import settings

IGNORED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'site-packages'}


def safe_path(name: str) -> str:
    p = PurePosixPath(name)
    if not name or len(name) > 300 or '\\' in name or ':' in name or '\x00' in name or p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe file path')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if any(any(ord(c) < 32 or c in '<>"|?*' for c in part) or part.endswith((' ', '.')) or part.split('.')[0].upper() in reserved for part in p.parts):
        raise ValueError('Unsupported or reserved file path')
    return str(p)


def decode_source(data: bytes) -> str:
    if len(data) > settings.max_file_bytes:
        raise ValueError('Python file exceeds configured size limit')
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('Source files must be UTF-8')
    if '\x00' in content:
        raise ValueError('Binary source file rejected')
    return content


def ingest(name: str, data: bytes):
    if len(data) > settings.max_upload_bytes:
        raise ValueError('Upload exceeds configured size limit')
    name = safe_path(name)
    if name.endswith('.py'):
        return {name: decode_source(data)}, []
    if not name.endswith('.zip'):
        raise ValueError('Upload a .py or .zip file')
    files, skipped, total = {}, [], 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 300:
                raise ValueError('Archive has too many entries')
            for item in entries:
                # ZipInfo normalizes backslashes on Windows. Validate the
                # original archive name before accepting its normalized form.
                safe_path(item.orig_filename)
                path = safe_path(item.filename)
                if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                    raise ValueError('Symlinks and encrypted entries are not supported')
                total += item.file_size
                if total > settings.max_upload_bytes:
                    raise ValueError('Extracted archive exceeds size limit')
                if item.is_dir():
                    continue
                parts = PurePosixPath(path).parts
                if any(p in IGNORED or p.startswith('.env') for p in parts) or not path.endswith('.py'):
                    skipped.append(path)
                    continue
                if path.casefold() in {p.casefold() for p in files} or len(files) >= settings.max_files:
                    raise ValueError('Duplicate paths or too many Python files')
                if item.file_size > settings.max_file_bytes:
                    raise ValueError('Python file exceeds configured size limit')
                files[path] = decode_source(archive.read(item))
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise ValueError('Invalid or unsupported ZIP archive')
    if not files:
        raise ValueError('No supported Python files in archive')
    return files, skipped


def content_hash(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
