"""Launcher behavior tests; standard library only, no installed app required."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('folio_start', Path(__file__).resolve().parents[1] / 'start.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class StartupTests(unittest.TestCase):
    def test_existing_servers_are_reused_without_spawning(self):
        with patch.object(launcher, 'port_open', return_value=True), patch.object(launcher, 'ready', return_value=True), patch.object(launcher.subprocess, 'Popen') as spawn:
            launcher.serve(Path(sys.executable), no_browser=True)
            spawn.assert_not_called()

    def test_unrelated_port_is_never_terminated(self):
        with patch.object(launcher, 'port_open', side_effect=lambda port:port==8000), patch.object(launcher.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                launcher.serve(Path(sys.executable), no_browser=True)
            spawn.assert_not_called()

    def test_invalid_language_cannot_be_used_as_download_path(self):
        with self.assertRaises(ValueError):
            launcher.install_languages(['../../outside'])

    def test_npm_entrypoint_with_spaces_uses_no_shell_on_windows(self):
        with tempfile.TemporaryDirectory(prefix='folio windows path ') as directory:
            npm = Path(directory) / 'npm.cmd'
            cli = npm.parent/'node_modules/npm/bin/npm-cli.js'
            cli.parent.mkdir(parents=True);cli.touch()
            with patch.object(launcher,'WINDOWS',True),patch.object(launcher,'require_tool',return_value='node.exe'),patch.object(launcher.subprocess,'run') as call:
                launcher.run([str(npm),'ci'])
                self.assertEqual(call.call_args.args[0],['node.exe',str(cli),'ci'])
                self.assertNotIn('shell',call.call_args.kwargs)

    @unittest.skipIf(os.name=='nt','POSIX process-group termination; Windows tree cleanup needs a Windows runner.')
    def test_owned_process_group_stops(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
        try:
            launcher.stop_process(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()

if __name__=='__main__':unittest.main()
