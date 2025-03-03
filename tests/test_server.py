import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unix_manual_server

@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run"""
    with patch('subprocess.run') as mock_run:
        yield mock_run

@pytest.fixture
def mock_os_path_exists():
    """Fixture to mock os.path.exists"""
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        yield mock_exists

@pytest.fixture
def mock_os_path_isdir():
    """Fixture to mock os.path.isdir"""
    with patch('os.path.isdir') as mock_isdir:
        mock_isdir.return_value = True
        yield mock_isdir

@pytest.fixture
def mock_os_path_isfile():
    """Fixture to mock os.path.isfile"""
    with patch('os.path.isfile') as mock_isfile:
        mock_isfile.return_value = True
        yield mock_isfile

@pytest.fixture
def mock_os_access():
    """Fixture to mock os.access"""
    with patch('os.access') as mock_access:
        mock_access.return_value = True
        yield mock_access

@pytest.fixture
def mock_os_listdir():
    """Fixture to mock os.listdir"""
    with patch('os.listdir') as mock_listdir:
        mock_listdir.return_value = ['ls', 'cat', 'grep']
        yield mock_listdir

@pytest.fixture
def mock_logger():
    """Fixture to mock the logger"""
    with patch('unix_manual_server.logger') as mock_logger:
        yield mock_logger

def test_get_command_path_success(mock_subprocess_run, mock_logger):
    """Test get_command_path when command is found"""
    # Configure the mock to return a valid path
    process_mock = MagicMock()
    process_mock.stdout = "/usr/bin/ls\n"
    process_mock.returncode = 0
    mock_subprocess_run.return_value = process_mock

    result = unix_manual_server.get_command_path("ls")

    assert result == "/usr/bin/ls"
    mock_subprocess_run.assert_called_once()
    mock_logger.debug.assert_any_call("Searching for command path: ls")
    mock_logger.debug.assert_any_call("Found command path: /usr/bin/ls")

def test_get_command_path_not_found(mock_subprocess_run, mock_logger):
    """Test get_command_path when command is not found"""
    # Configure the mock to return empty output
    process_mock = MagicMock()
    process_mock.stdout = "\n"
    process_mock.returncode = 1
    mock_subprocess_run.return_value = process_mock

    result = unix_manual_server.get_command_path("nonexistent-command")

    assert result is None
    mock_subprocess_run.assert_called_once()
    mock_logger.warning.assert_called_with("Command not found: nonexistent-command")

def test_get_command_path_exception(mock_subprocess_run, mock_logger):
    """Test get_command_path when subprocess raises exception"""
    # Configure the mock to raise an exception
    mock_subprocess_run.side_effect = subprocess.SubprocessError("Test error")

    result = unix_manual_server.get_command_path("ls")

    assert result is None
    mock_subprocess_run.assert_called_once()
    mock_logger.error.assert_called_once()

def test_safe_execute_success(mock_subprocess_run, mock_logger):
    """Test safe_execute when command succeeds"""
    # Configure the mock to return successful execution
    process_mock = MagicMock()
    process_mock.stdout = "Success output"
    process_mock.returncode = 0
    mock_subprocess_run.return_value = process_mock

    result = unix_manual_server.safe_execute(["ls", "-l"])

    assert result == process_mock
    mock_subprocess_run.assert_called_once_with(
        ["ls", "-l"],
        capture_output=True,
        text=True,
        timeout=10,
        shell=False
    )
    mock_logger.debug.assert_any_call("Executing command: ['ls', '-l'] with timeout=10")
    mock_logger.debug.assert_any_call("Command exit code: 0")
    mock_logger.debug.assert_any_call("Command stdout first 100 chars: Success output")

def test_safe_execute_timeout(mock_subprocess_run, mock_logger):
    """Test safe_execute when command times out"""
    # Configure the mock to raise TimeoutExpired
    mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd="ls", timeout=10)

    result = unix_manual_server.safe_execute(["ls", "-l"])

    assert result is None
    mock_subprocess_run.assert_called_once()
    mock_logger.warning.assert_called_once()

def test_safe_execute_error(mock_subprocess_run, mock_logger):
    """Test safe_execute when command raises error"""
    # Configure the mock to raise SubprocessError
    mock_subprocess_run.side_effect = subprocess.SubprocessError("Test error")

    result = unix_manual_server.safe_execute(["ls", "-l"])

    assert result is None
    mock_subprocess_run.assert_called_once()
    mock_logger.error.assert_called_once()

def test_search_help_documentation_with_h(mock_logger):
    """Test search_help_documentation with -h option"""
    with patch('unix_manual_server.safe_execute') as mock_safe_execute:
        # First call (--help) returns output that doesn't match help pattern
        help_mock1 = MagicMock()
        help_mock1.returncode = 0
        help_mock1.stdout = "Some output that doesn't look like help"

        # Second call (-h) returns valid help that matches pattern
        help_mock2 = MagicMock()
        help_mock2.returncode = 0
        help_mock2.stdout = "Usage: command\nOptions available"

        mock_safe_execute.side_effect = [help_mock1, help_mock2]

        # We need to patch re.search to control the regex matching behavior
        with patch('re.search') as mock_re_search:
            # Make the first regex check for --help fail, second for -h succeed
            mock_re_search.side_effect = [False, False, True]

            result = unix_manual_server.search_help_documentation("command", "/usr/bin/command")

            assert "Help output for 'command'" in result
            assert "Usage: command" in result
            mock_logger.info.assert_called_with("Found help documentation using -h for command")

def test_search_help_documentation_with_help_subcommand(mock_logger):
    """Test search_help_documentation with help subcommand"""
    with patch('unix_manual_server.safe_execute') as mock_safe_execute:
        # First two calls return outputs that don't match help pattern
        help_mock1 = MagicMock()
        help_mock1.returncode = 0
        help_mock1.stdout = "Some output that doesn't look like help"

        help_mock2 = MagicMock()
        help_mock2.returncode = 0
        help_mock2.stdout = "Another output that doesn't look like help"

        # Third call returns valid help
        help_mock3 = MagicMock()
        help_mock3.returncode = 0
        help_mock3.stdout = "Usage: command\nOptions available"

        mock_safe_execute.side_effect = [help_mock1, help_mock2, help_mock3]

        # We need to patch re.search to control the regex matching behavior
        with patch('re.search') as mock_re_search:
            # First four regex checks fail (two for --help, two for -h), last one succeeds
            mock_re_search.side_effect = [False, False, False, False, True]

            result = unix_manual_server.search_help_documentation("command", "/usr/bin/command")

            assert "Help output for 'command'" in result
            assert "Usage: command" in result
            mock_logger.info.assert_called_with("Found help documentation using help subcommand for command")

def test_search_help_documentation_no_help_found(mock_logger):
    """Test search_help_documentation when no help found"""
    with patch('unix_manual_server.safe_execute') as mock_safe_execute:
        # All calls return no match
        help_mock = MagicMock()
        help_mock.returncode = 0
        help_mock.stdout = "Some output that doesn't look like help"

        mock_safe_execute.return_value = help_mock

        # Mock regex search to always return False
        with patch('re.search') as mock_re_search:
            mock_re_search.return_value = False

            result = unix_manual_server.search_help_documentation("command", "/usr/bin/command")

            assert result == ""
            assert mock_safe_execute.call_count == 3
            mock_logger.warning.assert_called_with("No help documentation found for command")

def test_get_command_documentation_with_script_path(mock_logger):
    """Test that script paths like 'python script.py' are handled correctly"""
    with patch('unix_manual_server.get_command_path') as mock_get_path, \
         patch('unix_manual_server.search_help_documentation') as mock_search_help, \
         patch('unix_manual_server.safe_execute') as mock_safe_execute:

        command = "python script.py"

        # Configure mocks
        mock_get_path.return_value = "/usr/bin/python"

        # We expect it to try the subcommand first (script.py)
        mock_safe_execute.return_value = None  # subcommand help fails

        # Then fall back to main command
        mock_search_help.return_value = "Help output for 'python':\n\nPYTHON HELP CONTENT"

        result = unix_manual_server.get_command_documentation(command, prefer_economic=True)

        assert "Help output for 'python'" in result
        mock_logger.debug.assert_any_call("Detected subcommand: 'script.py', will try 'python script.py' first")

@pytest.mark.parametrize(
    "command,has_subcommand,subcommand_help_succeeds,expected_result",
    [
        # Command with subcommand and help for subcommand succeeds
        ("uv run test.py", True, True, "Help output for 'uv run'"),
        # Command with subcommand but help for subcommand fails, fallback to main command
        ("git commit file.txt", True, False, "Help output for 'git'"),
        # Command without subcommand
        ("ls -la", False, False, "Help output for 'ls'"),
    ]
)
def test_get_command_documentation_with_subcommand(command, has_subcommand, subcommand_help_succeeds,
                                                  expected_result, mock_logger):
    """Test get_command_documentation with subcommands"""
    with patch('unix_manual_server.get_command_path') as mock_get_path, \
         patch('unix_manual_server.search_help_documentation') as mock_search_help, \
         patch('unix_manual_server.safe_execute') as mock_safe_execute:

        # Configure mocks
        mock_get_path.return_value = "/usr/bin/{}".format(command.split()[0])

        if has_subcommand:
            if subcommand_help_succeeds:
                # Subcommand help succeeds
                subcommand_help_mock = MagicMock()
                subcommand_help_mock.returncode = 0
                subcommand_help_mock.stdout = "SUBCOMMAND HELP CONTENT"

                # The first three calls will be for the subcommand with --help, -h, help
                # Return success for the first one to simulate --help working
                mock_safe_execute.side_effect = [subcommand_help_mock, None, None]
            else:
                # Subcommand help fails, main command help succeeds
                mock_safe_execute.return_value = None
                mock_search_help.return_value = f"Help output for '{command.split()[0]}':\n\nMAIN COMMAND HELP CONTENT"
        else:
            # No subcommand, main command help succeeds
            mock_search_help.return_value = f"Help output for '{command.split()[0]}':\n\nMAIN COMMAND HELP CONTENT"

        result = unix_manual_server.get_command_documentation(command, prefer_economic=True)

        assert expected_result in result

        if has_subcommand:
            mock_logger.debug.assert_any_call(f"Detected subcommand: '{command.split()[1]}', will try '{command.split()[0]} {command.split()[1]}' first")

@pytest.mark.parametrize(
    "command,valid_name,command_exists,prefer_economic,man_section,expected_result",
    [
        # Valid command, economic approach succeeds
        ("ls", True, True, True, None, "Help output for 'ls'"),
        # Valid command, man approach succeeds
        ("ls", True, True, False, None, "Manual page for 'ls'"),
        # Valid command with man section
        ("ls", True, True, False, 1, "Manual page for 'ls'"),
        # Invalid command name
        ("invalid;command", False, False, True, None, "Invalid command name: 'invalid;command'"),
        # Command not found
        ("nonexistent", True, False, True, None, "Command not found: 'nonexistent'"),
        # Economic approach fails, man succeeds as fallback
        ("ls-fallback", True, True, True, None, "Manual page for 'ls-fallback'"),
        # Both approaches fail
        ("ls-all-fail", True, True, True, None, "No documentation available for 'ls-all-fail'"),
    ]
)
def test_get_command_documentation(command, valid_name, command_exists, prefer_economic,
                                   man_section, expected_result, mock_logger):
    """Test get_command_documentation with various scenarios"""
    with patch('unix_manual_server.get_command_path') as mock_get_path, \
         patch('unix_manual_server.search_help_documentation') as mock_search_help, \
         patch('subprocess.run') as mock_run, \
         patch('unix_manual_server.safe_execute') as mock_safe_execute:

        # Configure mocks based on parameters
        if not valid_name:
            # Return early due to invalid name check
            result = unix_manual_server.get_command_documentation(command, prefer_economic, man_section)
            assert "Invalid command name" in result
            return

        if not command_exists:
            mock_get_path.return_value = None
            result = unix_manual_server.get_command_documentation(command, prefer_economic, man_section)
            assert "Command not found" in result
            return

        # Command exists
        mock_get_path.return_value = f"/usr/bin/{command.split()[0]}"

        if command == "ls-fallback":
            # Economic approach fails, man succeeds
            mock_search_help.return_value = ""
            # Mock the man page command success
            man_result = MagicMock()
            man_result.returncode = 0
            man_result.stdout = "MAN PAGE CONTENT"

            col_result = MagicMock()
            col_result.stdout = "FORMATTED MAN PAGE"

            mock_run.side_effect = [man_result, col_result]

            # This is key - direct --help should also fail in this scenario
            mock_safe_execute.return_value = None
        elif command == "ls-all-fail":
            # Both approaches fail
            mock_search_help.return_value = ""
            # Man command fails
            man_result = MagicMock()
            man_result.returncode = 1
            man_result.stderr = "No manual entry"

            mock_run.return_value = man_result
            # Direct --help fails too
            mock_safe_execute.return_value = None
        else:
            # Standard success case
            if prefer_economic:
                mock_search_help.return_value = f"Help output for '{command}':\n\nHELP CONTENT"
            else:
                mock_search_help.return_value = ""
                man_result = MagicMock()
                man_result.returncode = 0
                man_result.stdout = "MAN PAGE CONTENT"

                col_result = MagicMock()
                col_result.stdout = "FORMATTED MAN PAGE"

                mock_run.side_effect = [man_result, col_result]

        result = unix_manual_server.get_command_documentation(command, prefer_economic, man_section)

        assert expected_result in result

def test_list_common_commands(mock_os_path_exists, mock_os_path_isdir,
                               mock_os_path_isfile, mock_os_access,
                               mock_os_listdir, mock_logger):
    """Test list_common_commands"""
    result = unix_manual_server.list_common_commands()

    assert "Common Unix commands available on this system:" in result
    assert "ls" in result
    assert "cat" in result
    assert "grep" in result
    assert "Total commands found:" in result
    mock_logger.info.assert_any_call("Listing common commands")
    mock_logger.info.assert_any_call("Found 3 unique commands")

def test_list_common_commands_directory_error(mock_os_path_exists, mock_os_path_isdir, mock_logger):
    """Test list_common_commands with error listing directory"""
    with patch('os.listdir') as mock_listdir:
        mock_listdir.side_effect = OSError("Permission denied")

        result = unix_manual_server.list_common_commands()

        assert "Common Unix commands available on this system:" in result
        assert "Total commands found: 0" in result
        mock_logger.error.assert_called()

@pytest.mark.parametrize(
    "command,valid_name,command_exists,version_output,expected_result",
    [
        # Valid command with version info
        ("ls", True, True, "ls version 8.32", "Command 'ls' exists at /usr/bin/ls.\nVersion information: ls version 8.32"),
        # Valid command without version info
        ("ls-no-version", True, True, None, "Command 'ls-no-version' exists on this system at /usr/bin/ls-no-version."),
        # Invalid command name
        ("invalid;command", False, False, None, "Invalid command name: 'invalid;command'"),
        # Command not found
        ("nonexistent", True, False, None, "Command 'nonexistent' does not exist or is not in the PATH."),
    ]
)
def test_check_command_exists(command, valid_name, command_exists, version_output,
                              expected_result, mock_logger):
    """Test check_command_exists with various scenarios"""
    with patch('unix_manual_server.get_command_path') as mock_get_path, \
         patch('unix_manual_server.safe_execute') as mock_safe_execute:

        # Configure mocks based on parameters
        if not valid_name:
            # Return early due to invalid name check
            result = unix_manual_server.check_command_exists(command)
            assert "Invalid command name" in result
            return

        if not command_exists:
            mock_get_path.return_value = None
            result = unix_manual_server.check_command_exists(command)
            assert "does not exist" in result
            return

        # Command exists
        mock_get_path.return_value = f"/usr/bin/{command.split()[0]}"

        if version_output:
            # Command has version info
            version_mock = MagicMock()
            version_mock.returncode = 0
            version_mock.stdout = version_output
            mock_safe_execute.return_value = version_mock
        else:
            # Command has no version info
            version_mock = MagicMock()
            version_mock.returncode = 1
            version_mock.stdout = ""
            mock_safe_execute.return_value = version_mock

        result = unix_manual_server.check_command_exists(command)

        assert expected_result in result

def test_main_success():
    """Test main function successful execution"""
    with patch('unix_manual_server.mcp.run') as mock_run, \
         patch('unix_manual_server.logger') as mock_logger:
        unix_manual_server.main()
        mock_run.assert_called_once()
        mock_logger.info.assert_called_with("Starting unix-manual-server")

def test_main_exception():
    """Test main function with exception"""
    with patch('unix_manual_server.mcp.run') as mock_run, \
         patch('unix_manual_server.logger') as mock_logger:
        mock_run.side_effect = Exception("Test error")
        unix_manual_server.main()
        mock_run.assert_called_once()
        mock_logger.critical.assert_called_once()
