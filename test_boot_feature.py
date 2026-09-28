import sys
import BetaBasic
import CPM
import unittest

class TestBootFeature(unittest.TestCase):
    def test_keywords(self):
        self.assertIn("BOOT", BetaBasic.SINGLE_KEYWORDS)
        self.assertIn("BOOT", BetaBasic.VALID_COMMANDS)
        self.assertIn("BOOT", BetaBasic.VALID_STATEMENTS)
        self.assertIn("BOOT", CPM.SINGLE_KEYWORDS)

    def test_cpm_boot_spec(self):
        cpm = CPM.CPMSystem()
        cpm.running = True
        cpm.cmd_boot("SPEC")
        self.assertFalse(cpm.running)

    def test_cpm_boot_disk(self):
        cpm = CPM.CPMSystem()
        cpm.running = True
        cpm.cmd_boot("")
        self.assertTrue(cpm.running)

    def test_forth_boot(self):
        forth = BetaBasic.ForthEngine()
        self.assertIn("BOOT", forth.dictionary)

    def test_basic_boot_no_media(self):
        BetaBasic.handle_boot_command("")

    def test_basic_boot_with_ramdisk(self):
        BetaBasic.ramdisk_files["DISK.BAS"] = b'10 PRINT "RAMDISK BOOT OK"\n'
        try:
            BetaBasic.handle_boot_command("M:")
            found = any("RAMDISK BOOT OK" in str(line) for line in BetaBasic.program.values())
            self.assertTrue(found, "Program from RAM disk should have been loaded")
        finally:
            if "DISK.BAS" in BetaBasic.ramdisk_files:
                del BetaBasic.ramdisk_files["DISK.BAS"]
            BetaBasic.program.clear()

    def test_basic_boot_drive_args(self):
        BetaBasic.handle_boot_command("1")
        BetaBasic.handle_boot_command("A:")
        BetaBasic.handle_boot_command("M1")
        BetaBasic.handle_boot_command("B")

if __name__ == "__main__":
    unittest.main()
