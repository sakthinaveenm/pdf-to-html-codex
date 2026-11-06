"""Shared, standard-library-only setup and process supervisor for both launchers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == 'nt'
DEFAULT_LANGUAGES = 'eng,tam,hin,tel,mal,kan,ben,mar,guj,pan,san,ara,urd,chi_sim,jpn,kor,fra,deu,spa'
# Official upstream release, deliberately fixed rather than a moving main branch.
TESSDATA_RELEASE = '4.1.0'


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess:
    # Invoke npm's JS entrypoint directly on Windows: no shell or batch quoting.
    invocation = command
    if WINDOWS and command[0].lower().endswith(('.cmd', '.bat')):
        cli = Path(command[0]).parent / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js'
        if Path(command[0]).name.lower() != 'npm.cmd' or not cli.is_file():
            raise RuntimeError(f'Cannot locate npm-cli.js beside {command[0]}. Repair the Node.js installation.')
        invocation = [require_tool('node'), str(cli), *command[1:]]
    return subprocess.run(invocation, cwd=cwd, check=True, text=True, capture_output=capture)


def require_tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'{name} is missing from PATH. Run the macOS/Windows launcher to install prerequisites.')
    return found


def languages() -> set[str]:
    result = run([require_tool('tesseract'), '--list-langs'], capture=True)
    return {line.strip() for line in result.stdout.splitlines()[1:] if re.fullmatch(r'[a-zA-Z0-9_/]+', line.strip())}


def install_languages(requested: list[str]) -> None:
    if any(not re.fullmatch(r'[a-z_]+', code) for code in requested):
        raise ValueError('OCR language codes must contain only lowercase letters and underscores.')
    installed = languages()
    missing = set(requested) - installed
    if not missing:
        verify_ocr(requested)
        print(f'OCR verified: {len(installed)} installed language packs.', flush=True)
        return
    # Keep system installations untouched. Include existing requested packs in a local
    # directory because TESSDATA_PREFIX selects a single data directory.
    destination = ROOT / '.launcher' / 'tessdata'
    destination.mkdir(parents=True, exist_ok=True)
    for code in sorted(set(requested) | {'osd'}):
        target = destination / f'{code}.traineddata'
        if target.is_file() and target.stat().st_size > 1000:
            continue
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{TESSDATA_RELEASE}/{code}.traineddata'
        temporary = target.with_suffix('.download')
        print(f'Installing OCR language: {code}', flush=True)
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            if temporary.stat().st_size <= 1000:
                raise RuntimeError(f'Downloaded language pack {code} is incomplete.')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    os.environ['TESSDATA_PREFIX'] = str(destination)
    missing = set(requested) - languages()
    if missing:
        raise RuntimeError(f'Tesseract could not load packs: {", ".join(sorted(missing))}')
    verify_ocr(requested)
    print('Requested OCR packs verified.', flush=True)


def verify_ocr(requested: list[str]) -> None:
    if not requested:
        raise ValueError('Specify at least one OCR language, or use --skip-ocr.')
    with tempfile.TemporaryDirectory(prefix='folio-start-') as temporary:
        image = Path(temporary) / 'blank.pgm'
        image.write_bytes(b'P5\n300 100\n255\n' + b'\xff' * 30000)
        # Unlike --list-langs, a real OCR invocation verifies that weights load.
        run([require_tool('tesseract'), str(image), 'stdout', '-l', '+'.join(requested), '--psm', '6'], capture=True)


def setup(args: argparse.Namespace) -> Path:
    uv, node, npm = require_tool('uv'), require_tool('node'), require_tool('npm.cmd' if WINDOWS else 'npm')
    major = int(run([node, '-p', 'process.versions.node.split(".")[0]'], capture=True).stdout.strip())
    if major < 24:
        raise RuntimeError('Node.js 24 or newer is required by this launcher. Rerun the OS launcher to install it.')
    print('Checking locked Python dependencies...', flush=True)
    sync = [uv, 'sync', '--locked', '--project', str(ROOT / 'backend')]
    if not args.lightweight:
        sync += ['--extra', 'docling']
    # A foreign virtual environment must not redirect or override the project environment.
    os.environ.pop('UV_PROJECT_ENVIRONMENT', None)
    os.environ.pop('VIRTUAL_ENV', None)
    run(sync)
    python = ROOT / 'backend' / '.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
    smoke = 'import fastapi, uvicorn, pydantic, sqlalchemy, alembic, pypdf, pdfplumber, pypdfium2, bs4, lxml, nh3, PIL, psutil; assert pydantic.VERSION.startswith("2.")'
    if not args.lightweight:
        smoke += '; from docling.document_converter import DocumentConverter'
    try:
        run([str(python), '-c', smoke], capture=True)
        run([uv, 'pip', 'check', '--python', str(python)], capture=True)
    except subprocess.CalledProcessError:
        print('Python package verification failed; reinstalling the locked environment once...', flush=True)
        run(sync + ['--reinstall'])
        run([str(python), '-c', smoke])
        run([uv, 'pip', 'check', '--python', str(python)])
    if not args.lightweight and not args.skip_marker:
        print('Checking isolated Marker dependencies...', flush=True)
        run([uv,'sync','--locked','--project',str(ROOT/'engines'/'marker')])
        marker_python=ROOT/'engines'/'marker'/'.venv'/('Scripts/python.exe' if WINDOWS else 'bin/python')
        run([str(marker_python),'-c','from marker.converters.pdf import PdfConverter; from marker.models import create_model_dict'],capture=True)
        # Preserve the environment path, including its python symlink.
        os.environ['PDF_MARKER_PYTHON']=str(marker_python.absolute())
    print('Python dependencies verified.', flush=True)

    frontend = ROOT / 'frontend'
    stamp = ROOT / '.launcher' / 'frontend.sha256'
    digest = hashlib.sha256((frontend / 'package-lock.json').read_bytes() + (frontend / 'package.json').read_bytes() + str(major).encode()).hexdigest()
    valid = stamp.is_file() and stamp.read_text().strip() == digest
    if valid:
        try:
            run([npm, 'ls', '--all', '--include=dev', '--include=optional'], cwd=frontend, capture=True)
        except subprocess.CalledProcessError:
            valid = False
    if not valid:
        print('Installing locked frontend dependencies...', flush=True)
        run([npm, 'ci', '--include=dev', '--include=optional'], cwd=frontend)
    try:
        run([npm, 'run', 'build'], cwd=frontend)
    except subprocess.CalledProcessError:
        # npm ls verifies metadata; an actual build also catches missing/corrupt files.
        print('Frontend verification failed; reinstalling dependencies once...', flush=True)
        run([npm, 'ci', '--include=dev', '--include=optional'], cwd=frontend)
        run([npm, 'run', 'build'], cwd=frontend)
    stamp.parent.mkdir(exist_ok=True)
    stamp.write_text(digest + '\n')
    env_file = ROOT / '.env'
    if not env_file.exists():
        shutil.copyfile(ROOT / '.env.example', env_file)
        print('Created .env from .env.example.', flush=True)
    if not args.skip_ocr:
        install_languages([code for code in args.languages.split(',') if code])
    else:
        print('OCR setup skipped. Scanned PDFs require a working Tesseract installation.', flush=True)
    return python


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def ready(url: str, *, backend: bool = False) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read(100_000).decode('utf-8')
            return json.loads(body).get('status') == 'ok' if backend else '<title>Folio' in body
    except (OSError, ValueError, urllib.error.URLError):
        return False


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if WINDOWS:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        if not WINDOWS:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)


def serve(python: Path, *, no_browser: bool) -> None:
    url = 'http://127.0.0.1:5173'
    health = 'http://127.0.0.1:8000/api/v1/health'
    occupied = [port for port in (8000, 5173) if port_open(port)]
    if occupied:
        if len(occupied) == 2 and ready(health, backend=True) and ready(url):
            print(f'Folio is already running: {url}', flush=True)
            if not no_browser:
                webbrowser.open(url)
            return
        raise RuntimeError(f'Ports {occupied} are already in use. Stop the existing server(s) and retry; the launcher will not terminate unrelated processes.')
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'backend') + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    node = require_tool('node')
    commands = [
        [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
        [node, str(ROOT / 'frontend' / 'node_modules' / 'vite' / 'bin' / 'vite.js'), '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    ]
    processes: list[subprocess.Popen] = []
    log_handles = []
    log_dir = ROOT / '.launcher' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        for name, command in zip(('backend', 'frontend'), commands):
            logfile = (log_dir / f'{name}.log').open('w', encoding='utf-8')
            log_handles.append(logfile)
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
            processes.append(subprocess.Popen(command, cwd=ROOT if name == 'backend' else ROOT / 'frontend', env=env, stdout=logfile, stderr=subprocess.STDOUT, **options))
        deadline = time.monotonic() + 90
        while not (ready(health, backend=True) and ready(url)):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError(f'A server stopped during startup. See logs in {log_dir}')
            if time.monotonic() > deadline:
                raise RuntimeError(f'Servers did not become ready within 90 seconds. See {log_dir}')
            time.sleep(.5)
        print(f'\nFolio is ready: {url}\nAPI docs: http://127.0.0.1:8000/docs\nLogs: {log_dir}\nKeep this window open. Press Ctrl+C to stop both servers.', flush=True)
        if not no_browser:
            webbrowser.open(url)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
        raise RuntimeError(f'A server exited unexpectedly. See {log_dir}')
    finally:
        for process in reversed(processes):
            stop_process(process)
        for handle in log_handles:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lightweight', action='store_true', help='Use the smaller backend profile without Docling; Marker is never auto-installed.')
    parser.add_argument('--skip-marker', action='store_true', help='Skip automatic setup of the isolated Marker profile.')
    parser.add_argument('--skip-ocr', action='store_true', help='Skip installing/checking Tesseract and language packs.')
    parser.add_argument('--languages', default=DEFAULT_LANGUAGES, help='Comma-separated Tesseract packs to verify/install.')
    parser.add_argument('--setup-only', action='store_true', help='Install/verify dependencies without starting servers.')
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser automatically.')
    args = parser.parse_args()
    os.chdir(ROOT)
    # SIGTERM from a terminal supervisor must also run the child-process cleanup.
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if not args.setup_only and any(port_open(port) for port in (8000, 5173)):
            # Do not resynchronize files underneath a running server.
            serve(Path(sys.executable), no_browser=args.no_browser)
            return 0
        python = setup(args)
        if args.setup_only:
            print('Setup complete. All requested dependencies passed verification.', flush=True)
        else:
            serve(python, no_browser=args.no_browser)
        return 0
    except KeyboardInterrupt:
        print('\nStopped.', flush=True)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'\nStartup failed: {exc}', file=sys.stderr, flush=True)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
