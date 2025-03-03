import unittest
from unittest.mock import patch, MagicMock
import os
import subprocess

from unix_manual_server import is_valid_command, safe_execute, get_command_documentation, list_common_commands, check_command_exists

class TestMCPServer(unittest.TestCase):

    @patch('subprocess.run')
    def test_is_valid_command_found(self, mock_run):
        # Simulate a successful command lookup (stdout non-empty)
        process_mock = MagicMock()
        process_mock.stdout = "/bin/ls"
        process_mock.returncode = 0
        mock_run.return_value = process_mock

        self.assertTrue(is_valid_command("ls"))
        mock_run.assert_called_once()  # Ensure subprocess.run was called

    @patch('subprocess.run')
    def test_is_valid_command_not_found(self, mock_run):
        # Simulate command not found (empty stdout)
        process_mock = MagicMock()
        process_mock.stdout = ""
        process_mock.returncode = 1
        mock_run.return_value = process_mock

        self.assertFalse(is_valid_command("nonexistent_command"))

    @patch('subprocess.run')
    def test_safe_execute_success(self, mock_run):
        # Simulate a successful execution returning output
        process_mock = MagicMock()
        process_mock.stdout = "output"
        process_mock.returncode = 0
        mock_run.return_value = process_mock

        result = safe_execute("echo hello", timeout=5)
        self.assertEqual(result.stdout, "output")
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_command_documentation_invalid_command(self, mock_run):
        # Test with an invalid command name that includes disallowed characters
        doc = get_command_documentation("invalid-command$")
        self.assertIn("Invalid command name", doc)
        # In this case, no subprocess call should be made
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_get_command_documentation_command_not_found(self, mock_run):
        # Simulate is_valid_command failure by returning empty output for command -v
        process_mock = MagicMock()
        process_mock.stdout = ""
        process_mock.returncode = 1
        mock_run.return_value = process_mock

        doc = get_command_documentation("nonexistent")
        self.assertIn("Command not found", doc)

    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('os.access')
    @patch('os.path.isdir')
    def test_list_common_commands(self, mock_isdir, mock_access, mock_exists, mock_listdir):
        # Simulate that each common directory exists and contains some commands.
        mock_exists.return_value = True
        mock_isdir.return_value = True
        # For simplicity, assume each directory returns the same list of files.
        mock_listdir.return_value = ['ls', 'cp', 'not_executable']
        # Simulate that only 'ls' and 'cp' are executable.
        def access_side_effect(path, mode):
            return os.path.basename(path) in ['ls', 'cp']
        mock_access.side_effect = access_side_effect

        output = list_common_commands()
        self.assertIn("ls", output)
        self.assertIn("cp", output)
        # The non-executable file should not be included.
        self.assertNotIn("not_executable", output)

    @patch('subprocess.run')
    def test_check_command_exists_with_version(self, mock_run):
        # Simulate that the command exists and returns version information.
        process_mock = MagicMock()
        process_mock.stdout = "v1.0"
        process_mock.returncode = 0
        mock_run.return_value = process_mock

        output = check_command_exists("ls")
        self.assertIn("exists", output)
        self.assertIn("v1.0", output)

    @patch('subprocess.run')
    def test_check_command_exists_not_found(self, mock_run):
        # Simulate a non-existent command via an empty output.
        process_mock = MagicMock()
        process_mock.stdout = ""
        process_mock.returncode = 1
        mock_run.return_value = process_mock

        output = check_command_exists("nonexistent")
        self.assertIn("does not exist", output)

if __name__ == '__main__':
    unittest.main()
