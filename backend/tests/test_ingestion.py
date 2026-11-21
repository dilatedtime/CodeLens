import io
import zipfile
import pytest
from app.ingestion import ingest, content_hash
from app.config import settings


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        for name, content in entries:
            z.writestr(name, content)
    return data.getvalue()


@pytest.mark.parametrize('path', ['../escape.py', '/absolute.py', 'C:/file.py', 'a\\b.py', 'a/../../escape.py'])
def test_archive_path_rejection(path):
    # Windows ZipInfo normalizes backslashes while writing; patch the serialized
    # entry so this fixture really contains the hostile path we intend to test.
    payload = archive([(path.replace('\\', '/'), 'x=1')])
    if '\\' in path:
        payload = payload.replace(path.replace('\\', '/').encode(), path.encode())
    with pytest.raises(ValueError):
        ingest('project.zip', payload)


def test_symlink_rejected():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        item = zipfile.ZipInfo('link.py')
        item.create_system = 3
        item.external_attr = 0o120777 << 16
        z.writestr(item, '/etc/passwd')
    with pytest.raises(ValueError, match='Symlinks'):
        ingest('x.zip', data.getvalue())


def test_ignored_files_and_hash():
    files, skipped = ingest('x.zip', archive([('src/a.py', 'x=1'), ('.env', 'SECRET=x'), ('venv/a.py', 'x=2'), ('readme.md', '# hi')]))
    assert files == {'src/a.py': 'x=1'}
    assert len(skipped) == 3
    assert content_hash(files) == content_hash(dict(files))
    assert content_hash(files) != content_hash({'src/a.py': 'x=2'})


def test_limits(monkeypatch):
    monkeypatch.setattr(settings, 'max_file_bytes', 3)
    with pytest.raises(ValueError, match='size'):
        ingest('main.py', b'x=1234')


def test_binary_and_bad_zip():
    for name, content in [('x.py', b'\x00'), ('x.zip', b'invalid')]:
        with pytest.raises(ValueError):
            ingest(name, content)


@pytest.mark.parametrize('path', ['CON.py', 'nested/NUL.py', 'main?.py'])
def test_windows_reserved_names(path):
    with pytest.raises(ValueError):
        ingest(path, b'x = 1')


def test_case_collision():
    with pytest.raises(ValueError, match='Duplicate'):
        ingest('x.zip', archive([('Main.py','x=1'),('main.py','x=2')]))
