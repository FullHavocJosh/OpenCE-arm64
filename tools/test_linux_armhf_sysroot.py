import os

import tools.linux_armhf_sysroot as sysroot
from tools.linux_armhf_sysroot import (
    MIRROR,
    dependency_names,
    is_skipped,
    parse_index,
    resolve,
)


def test_parse_index():
    index_text = """Package: libc6
Version: 2.40-1
Depends: libgcc-s1

Package: libgcc-s1
Version: 14-1
Depends:

"""
    index = parse_index(index_text)
    assert 'libc6' in index
    assert index['libc6']['Version'] == '2.40-1'
    assert index['libgcc-s1']['Version'] == '14-1'


def test_dependency_names():
    deps = dependency_names('libc6 (>= 2.34), a | b, c:any (>= 1)')
    assert deps == ['libc6', 'a', 'c']


def test_dependency_names_empty():
    assert dependency_names('') == []
    assert dependency_names('   ') == []


def test_is_skipped():
    assert is_skipped('debconf') is True
    assert is_skipped('tzdata') is True
    assert is_skipped('python3-foo') is True
    assert is_skipped('libpython3-dev') is True
    assert is_skipped('libc6') is False


def test_transitive_closure():
    index_text = """Package: libc6
Version: 1
Depends: libgcc-s1

Package: libgcc-s1
Version: 1
Depends: libfoo

Package: libfoo
Version: 1
Depends:

"""
    index = parse_index(index_text)
    result = resolve(index, ['libc6'], [])
    assert result == ['libc6', 'libfoo', 'libgcc-s1']


def test_dev_root_not_expanded():
    index_text = """Package: libc6-dev
Version: 1
Depends: libc6

Package: libc6
Version: 1
Depends:

"""
    index = parse_index(index_text)
    result = resolve(index, [], ['libc6-dev'])
    # dev roots taken alone, no Depends expanded
    assert result == ['libc6-dev']


def test_skip_rule():
    index_text = """Package: libc6
Version: 1
Depends: debconf

Package: debconf
Version: 1
Depends:

"""
    index = parse_index(index_text)
    result = resolve(index, ['libc6'], [])
    # debconf should be skipped
    assert 'debconf' not in result
    assert result == ['libc6']


MAKE_INDEX = """Package: libc6
Version: 2.40-1
SHA256: aaa
Filename: pool/main/g/glibc/libc6.deb

Package: libc6-dev
Version: 2.40-1
SHA256: bbb
Filename: pool/main/g/glibc/libc6-dev.deb

"""


def test_stamp_text_sorted():
    entries = [
        {'Package': 'b', 'Version': '2', 'SHA256': 'y'},
        {'Package': 'a', 'Version': '1', 'SHA256': 'x'},
    ]
    assert sysroot.stamp_text(entries) == 'a 1 x\nb 2 y\n'


def test_make_writes_stamp_last_and_is_idempotent(tmp_path, monkeypatch):
    downloads = []

    def fake_download(urls, digest):
        downloads.append((urls, digest))
        assert not (tmp_path / 'stamp').exists()
        return urls[0].encode()

    def fake_deb_data(deb):
        return deb

    def fake_extract(archive, destination, strip=0):
        (destination / (archive.decode().rsplit('/', 1)[1])).write_text('x')

    monkeypatch.setattr(sysroot, 'fetch_index', lambda: MAKE_INDEX)
    monkeypatch.setattr(sysroot, 'download', fake_download)
    monkeypatch.setattr(sysroot, 'deb_data', fake_deb_data)
    monkeypatch.setattr(sysroot, 'extract', fake_extract)
    monkeypatch.setattr(sysroot, 'RUNTIME_ROOTS', ['libc6'])
    monkeypatch.setattr(sysroot, 'DEV_ROOTS', ['libc6-dev'])

    sysroot.make(tmp_path)
    assert [d[1] for d in downloads] == ['aaa', 'bbb']
    assert downloads[0][0] == [MIRROR + 'pool/main/g/glibc/libc6.deb']
    assert (tmp_path / 'sysroot' / 'libc6.deb').is_file()
    assert (tmp_path / 'sysroot' / 'lib').is_symlink()
    assert os.readlink(tmp_path / 'sysroot' / 'lib') == 'usr/lib'
    assert (tmp_path / 'stamp').read_text() == (
        'libc6 2.40-1 aaa\nlibc6-dev 2.40-1 bbb\n'
    )

    sysroot.make(tmp_path)
    assert len(downloads) == 2
