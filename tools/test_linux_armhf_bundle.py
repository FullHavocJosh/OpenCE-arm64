import os

import pytest

from tools.linux_armhf_bundle import bundle


def make_sysroot(root, loader=True):
    lib = root / 'usr' / 'lib' / 'arm-linux-gnueabihf'
    (lib / 'dri').mkdir(parents=True)
    if loader:
        (lib / 'ld-linux-armhf.so.3').write_bytes(b'ld')
    (lib / 'libfoo.so.1').write_bytes(b'foo')
    os.symlink('libfoo.so.1', lib / 'libfoo.so')
    (lib / 'libx.a').write_bytes(b'x')
    (lib / 'dri' / 'msm_dri.so').write_bytes(b'dri')
    vendor = root / 'usr' / 'share' / 'glvnd' / 'egl_vendor.d'
    vendor.mkdir(parents=True)
    (vendor / '50_mesa.json').write_text('{}')
    return root


def test_bundle_layout(tmp_path):
    sysroot = make_sysroot(tmp_path / 'sysroot')
    probe = tmp_path / 'probe'
    probe.write_bytes(b'probe')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'stale').write_text('old')

    bundle(sysroot, probe, out)

    assert not (out / 'stale').exists()
    assert (out / 'lib' / 'ld-linux-armhf.so.3').read_bytes() == b'ld'
    assert (out / 'lib' / 'libfoo.so.1').exists()
    assert (out / 'lib' / 'dri' / 'msm_dri.so').exists()
    assert not (out / 'lib' / 'libx.a').exists()
    assert (out / 'lib' / 'libfoo.so').is_symlink()
    assert os.readlink(out / 'lib' / 'libfoo.so') == 'libfoo.so.1'
    assert (out / 'share' / 'glvnd' / 'egl_vendor.d' / '50_mesa.json').exists()
    assert (out / 'armhf_probe').read_bytes() == b'probe'
    launch = out / 'launch'
    assert os.access(launch, os.X_OK)
    text = launch.read_text()
    assert 'ld-linux-armhf.so.3' in text
    assert '--library-path "$d/lib:$d/lib/pulseaudio"' in text


def test_bundle_sdl_lib(tmp_path):
    sysroot = make_sysroot(tmp_path / 'sysroot')
    lib = sysroot / 'usr' / 'lib' / 'arm-linux-gnueabihf'
    (lib / 'libSDL3.so.0.2.10').write_bytes(b'debian')
    os.symlink('libSDL3.so.0.2.10', lib / 'libSDL3.so.0')
    probe = tmp_path / 'probe'
    probe.write_bytes(b'probe')
    sdl = tmp_path / 'sdl'
    sdl.mkdir()
    (sdl / 'libSDL3.so.0.4.16').write_bytes(b'source')
    os.symlink('libSDL3.so.0.4.16', sdl / 'libSDL3.so.0')
    os.symlink('libSDL3.so.0', sdl / 'libSDL3.so')

    plain = tmp_path / 'plain'
    bundle(sysroot, probe, plain)
    assert (plain / 'lib' / 'libSDL3.so.0').read_bytes() == b'debian'

    out = tmp_path / 'out'
    bundle(sysroot, probe, out, sdl)
    assert (out / 'lib' / 'libSDL3.so.0').read_bytes() == b'source'
    assert os.readlink(out / 'lib' / 'libSDL3.so.0') == 'libSDL3.so.0.4.16'
    assert (out / 'lib' / 'libSDL3.so').is_symlink()
    assert not (out / 'lib' / 'libSDL3.so.0.2.10').exists()
    assert (out / 'lib' / 'libfoo.so.1').exists()


def test_bundle_missing_loader(tmp_path):
    sysroot = make_sysroot(tmp_path / 'sysroot', loader=False)
    probe = tmp_path / 'probe'
    probe.write_bytes(b'probe')
    with pytest.raises(FileNotFoundError, match='ld-linux-armhf.so.3'):
        bundle(sysroot, probe, tmp_path / 'out')
