import os
import tempfile
import unittest

from urh.util import DecoderInstaller


class TestDecoderInstaller(unittest.TestCase):
    def test_packaged_windows(self):
        with tempfile.TemporaryDirectory(prefix="URH NG O'Neil ") as base:
            decoders = os.path.join(base, "decoders")
            os.makedirs(os.path.join(decoders, "windows-x64"))
            script = os.path.join(decoders, "install-decoders.ps1")
            open(script, "w").close()

            program, args, folder = DecoderInstaller.get_install_command(
                frozen=True, platform="win32", base_dir=base
            )
            self.assertEqual(program, "powershell.exe")
            self.assertEqual(folder, decoders)
            # Paths are separate arguments, so spaces and quotes need no escaping
            self.assertIn(script, args)
            self.assertEqual(args[args.index("-SourceDir") + 1], decoders)
            self.assertIn("-Silent", args)

    def test_packaged_without_decoders(self):
        with tempfile.TemporaryDirectory() as base:
            program, args, folder = DecoderInstaller.get_install_command(
                frozen=True, platform="win32", base_dir=base
            )
            self.assertIsNone(program)
            self.assertEqual(folder, os.path.join(base, "decoders"))

    def test_source_tree(self):
        # Running from the repository uses data/windows and data/decoders
        program, args, folder = DecoderInstaller.get_install_command(
            frozen=False, platform="win32"
        )
        self.assertEqual(program, "powershell.exe")
        self.assertTrue(os.path.isdir(folder))
        self.assertTrue(args[args.index("-File") + 1].endswith("install-decoders.ps1"))

        program, args, folder = DecoderInstaller.get_install_command(
            frozen=False, platform="linux"
        )
        self.assertEqual(program, "sh")
        self.assertTrue(args[0].endswith("install.sh"))
