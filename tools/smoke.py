#!/usr/bin/env python3
"""Boot a trusted built SDK image in an isolated Google Emulator AVD and record evidence."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET


def port_pair():
    for port in range(5554, 5586, 2):
        sockets = []
        try:
            for candidate in (port, port + 1):
                sock = socket.socket()
                sock.bind(('127.0.0.1', candidate))
                sockets.append(sock)
            return port
        except OSError:
            continue
        finally:
            for sock in sockets:
                sock.close()
    raise RuntimeError('No available emulator console/ADB port pair')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--grpcurl', type=Path, help='Also verify authenticated gRPC and snapshot save/load')
    parser.add_argument('--proto', type=Path, help='Matching emulator_controller.proto for --grpcurl')
    args = parser.parse_args()
    if bool(args.grpcurl) != bool(args.proto):
        parser.error('--grpcurl and --proto must be supplied together')
    image = args.image.resolve()
    emulator = args.emulator.resolve()
    adb = args.adb.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(image) as archive:
        properties = [name for name in archive.namelist() if name.endswith('/source.properties')]
        if len(properties) != 1:
            raise ValueError('Expected one SDK ABI directory')
        abi = properties[0].split('/')[0]
        metadata = dict(line.split('=', 1) for line in archive.read(properties[0]).decode().splitlines() if '=' in line)
        if metadata.get('SystemImage.Abi') != abi:
            raise ValueError('ABI metadata mismatch')
        expected = 'arm64-v8a' if platform.machine().lower() in ('arm64', 'aarch64') else 'x86_64'
        if abi != expected:
            raise ValueError(f'Hardware acceleration requires {expected} guest on this host')
        for member in archive.infolist():
            path = Path(member.filename)
            if path.is_absolute() or '..' in path.parts or ((member.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError(f'Unsafe archive member {member.filename}')
        with tempfile.TemporaryDirectory(prefix='avd-smoke-', dir=output) as temp:
            root = Path(temp)
            archive.extractall(root / 'images')
            avd_home = root / 'avd'
            avd = avd_home / 'smoke.avd'
            avd.mkdir(parents=True)
            (avd_home / 'smoke.ini').write_text(f'avd.ini.encoding=UTF-8\npath={avd}\ntarget=android-36\n')
            config = {
                'AvdId': 'smoke', 'avd.ini.displayname': 'LineageOS smoke test',
                'image.sysdir.1': str(root / 'images' / abi) + '/',
                'abi.type': abi, 'hw.cpu.arch': 'arm64' if abi == 'arm64-v8a' else 'x86_64',
                'hw.cpu.ncore': '4', 'hw.ramSize': '4096', 'disk.dataPartition.size': '4G',
                'hw.lcd.width': '1080', 'hw.lcd.height': '2400', 'hw.lcd.density': '420',
                'hw.mainKeys': 'no', 'hw.gpu.enabled': 'yes', 'hw.gpu.mode': 'swiftshader',
                'hw.keyboard': 'yes', 'hw.camera.back': 'none', 'hw.camera.front': 'none',
                'fastboot.forceColdBoot': 'yes', 'showDeviceFrame': 'no',
            }
            (avd / 'config.ini').write_text(''.join(f'{key}={value}\n' for key, value in config.items()))
            env = dict(os.environ, ANDROID_AVD_HOME=str(avd_home), ANDROID_USER_HOME=str(root / 'android-user'))
            sdk_root = emulator.parent.parent
            if not (sdk_root / 'platforms').is_dir():
                sdk_root = root / 'sdk'
                (sdk_root / 'platforms').mkdir(parents=True)
                (sdk_root / 'emulator').symlink_to(emulator.parent, target_is_directory=True)
                (sdk_root / 'platform-tools').symlink_to(adb.parent, target_is_directory=True)
            env['ANDROID_SDK_ROOT'] = str(sdk_root)
            env['ANDROID_HOME'] = str(sdk_root)
            runtime = root / 'runtime'
            runtime.mkdir(mode=0o700)
            env.update(XDG_RUNTIME_DIR=str(runtime), TMPDIR=str(runtime), TMP=str(runtime), TEMP=str(runtime))
            grpc_args = []
            grpc_port = None
            if args.grpcurl:
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    grpc_port = sock.getsockname()[1]
                grpc_args = ['-grpc', str(grpc_port), '-grpc-use-token']
            port = port_pair()
            # A dedicated ADB server avoids altering a developer's existing server or devices.
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                adb_port = sock.getsockname()[1]
            env['ANDROID_ADB_SERVER_PORT'] = str(adb_port)
            serial = f'emulator-{port}'

            def run_adb(*arguments, timeout=20, check=True, binary=False):
                result = subprocess.run([str(adb), '-P', str(adb_port), '-s', serial, *arguments],
                                        env=env, capture_output=True, text=not binary, timeout=timeout, check=False)
                if check and result.returncode:
                    raise RuntimeError(f'ADB {arguments} failed: {result.stdout!r} {result.stderr!r}')
                return result

            subprocess.run([str(adb), '-P', str(adb_port), 'start-server'], env=env, check=True, capture_output=True)
            process = None
            started = time.monotonic()
            try:
                with (output / f'{abi}-emulator.log').open('wb') as log:
                    process = subprocess.Popen([str(emulator), '-avd', 'smoke', '-port', str(port),
                                                '-no-window', '-no-snapshot-save', '-no-boot-anim', '-no-audio', '-no-metrics',
                                                '-gpu', 'swiftshader', '-accel', 'on', *grpc_args], env=env, stdout=log, stderr=subprocess.STDOUT)
                    while time.monotonic() - started < args.timeout:
                        if process.poll() is not None:
                            raise RuntimeError(f'Emulator exited with code {process.returncode}; see log')
                        result = run_adb('shell', 'getprop', 'sys.boot_completed', timeout=5, check=False)
                        if result.returncode == 0 and result.stdout.strip() == '1':
                            break
                        time.sleep(2)
                    else:
                        raise TimeoutError('Android boot did not complete before the deadline')
                    boot_seconds = round(time.monotonic() - started, 1)
                    kernel = run_adb('shell', 'uname', '-r').stdout.strip()
                    manager = run_adb('shell', 'pm', 'path', 'com.rifsxd.ksunext').stdout.strip()
                    if '6.12.' not in kernel or 'ksunext-v3.3.0' not in kernel:
                        raise ValueError(f'Unexpected kernel release: {kernel}')
                    if '/product/app/KernelSU_Next/' not in manager:
                        raise ValueError(f'Manager is not preinstalled in product: {manager}')
                    hardening = run_adb('shell', 'cat', '/sys/devices/system/cpu/syscall_hardening', check=False).stdout.strip()
                    if abi == 'x86_64' and hardening != 'Syscall hardening: Disabled':
                        raise ValueError(f'Imported syscall boot option was not preserved: {hardening}')
                    diagnostics = {
                        'current_user': run_adb('shell', 'am', 'get-current-user', check=False).stdout,
                        'users': run_adb('shell', 'pm', 'list', 'users', check=False).stdout,
                        'manager_package': run_adb('shell', 'dumpsys', 'package', 'com.rifsxd.ksunext', check=False).stdout,
                    }
                    (output / f'{abi}-package-diagnostics.json').write_text(json.dumps(diagnostics, indent=2))
                    run_adb('shell', 'am', 'start', '-W', '-n', 'com.rifsxd.ksunext/com.rifsxd.ksunext.ui.MainActivity')
                    time.sleep(5)
                    manager_pid = run_adb('shell', 'pidof', 'com.rifsxd.ksunext').stdout.strip()
                    if not manager_pid:
                        raise ValueError('KernelSU Manager did not remain running after launch')
                    run_adb('shell', 'uiautomator', 'dump', '/sdcard/avd-smoke.xml', timeout=45)
                    hierarchy = run_adb('exec-out', 'cat', '/sdcard/avd-smoke.xml').stdout
                    (output / f'{abi}-manager-ui.xml').write_text(hierarchy)
                    texts = {node.get('text') for node in ET.fromstring(hierarchy).iter('node')}
                    if 'Working' not in texts:
                        raise ValueError('KernelSU Manager does not report Working; inspect UI evidence')
                    screenshot = run_adb('exec-out', 'screencap', '-p', binary=True).stdout
                    if not screenshot.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise ValueError('Screenshot was not a PNG')
                    (output / f'{abi}-boot.png').write_bytes(screenshot)
                    evidence = {'abi': abi, 'revision': metadata.get('Pkg.Revision'), 'api': metadata.get('AndroidVersion.ApiLevel'),
                                'kernel': kernel, 'guest_online_cpus': run_adb('shell', 'cat', '/sys/devices/system/cpu/online').stdout.strip(), 'manager': manager, 'manager_running': bool(manager_pid), 'manager_kernel_status': 'Working', 'syscall_hardening': hardening,
                                'boot_seconds': boot_seconds, 'scenario_seconds': round(time.monotonic() - started, 1), 'hardware_acceleration': True,
                                'emulator_version': subprocess.check_output([str(emulator), '-version'], env=env, text=True).splitlines()[0]}
                    if args.grpcurl:
                        discovery = None
                        for candidate in runtime.rglob('*.ini'):
                            fields = dict(line.split('=', 1) for line in candidate.read_text().splitlines() if '=' in line)
                            if fields.get('grpc.port') == str(grpc_port) and fields.get('grpc.token'):
                                discovery = candidate
                                break
                        if not discovery:
                            raise RuntimeError('No authenticated discovery file for the private gRPC port')
                        probe = Path(__file__).with_name('grpc_snapshot_probe.py')
                        subprocess.run([sys.executable, str(probe), '--discovery', str(discovery),
                                        '--proto', str(args.proto.resolve()), '--adb', str(adb),
                                        '--adb-server-port', str(adb_port), '--serial', serial,
                                        '--avd-dir', str(avd), '--output', str(output),
                                        '--grpcurl', str(args.grpcurl.resolve())], env=env, check=True)
                        evidence['grpc_and_snapshots'] = 'passed'
                    (output / f'{abi}-smoke.json').write_text(json.dumps(evidence, indent=2) + '\n')
                    print(json.dumps(evidence, indent=2))
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                subprocess.run([str(adb), '-P', str(adb_port), 'kill-server'], env=env, capture_output=True)


if __name__ == '__main__':
    main()
