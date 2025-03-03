import os
import re
import subprocess
import logging
from mcp.server.fastmcp import FastMCP

# Configure logging
# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, "unix-manual-server.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("unix-manual-server")
logger.info(f"Logging to: {log_file}")

# Create an MCP server instance
mcp = FastMCP("unix-manual-server")

def get_command_path(command):
    """Get the full absolute path to a command by filtering shell output."""
    logger.debug(f"Searching for command path: {command}")
    try:
        # Use the user's shell (defaulting to /bin/zsh) with login to load the full environment.
        user_shell = os.environ.get('SHELL', '/bin/zsh')
        logger.debug(f"Using shell: {user_shell}")
        result = subprocess.run(
            [user_shell, "-l", "-c", f"command -v {command} 2>/dev/null"],
            capture_output=True,
            text=True
        )
        # Process the output line by line and return the first line that is a valid absolute path.
        for line in result.stdout.splitlines():
            if re.match(r'^/', line):
                path = line.strip()
                logger.debug(f"Found command path: {path}")
                return path
        logger.warning(f"Command not found: {command}")
        return None
    except subprocess.SubprocessError as e:
        logger.error(f"Error finding command path for {command}: {str(e)}")
        return None

def safe_execute(cmd_args, timeout=10):
    """Safely execute a command directly (not through shell) and return its output."""
    logger.debug(f"Executing command: {cmd_args} with timeout={timeout}")
    try:
        # Execute command directly without shell
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False  # Explicitly set shell=False for security
        )
        logger.debug(f"Command exit code: {result.returncode}")
        # Add debug output to see first 100 chars of stdout
        if result.stdout:
            logger.debug(f"Command stdout first 100 chars: {result.stdout[:100].replace('\n', '\\n')}")
        return result
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after {timeout} seconds: {cmd_args}")
        return None
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.error(f"Error executing command {cmd_args}: {str(e)}")
        return None

def search_help_documentation(main_command, command_path):
    """Search for help documentation using --help, -h, or help options."""
    logger.info(f"Searching for help documentation for command: {main_command} at {command_path}")

    # Try --help
    logger.debug(f"Trying --help for {main_command}")
    help_result = safe_execute([command_path, "--help"], timeout=5)
    if help_result and help_result.returncode < 2 and help_result.stdout.strip():
        # Verify this is actual help text, not just command execution output
        output = help_result.stdout.strip()
        # Most help text contains words like "usage", "options", or "help"
        # Adding additional terms "USAGE" and checking for version string patterns
        if (re.search(r'usage|options|help|Usage|Options|Help|USAGE|OPTIONS|HELP|USAGE:|VERSION|Version', output, re.IGNORECASE) or
            re.search(r'\d+\.\d+\.\d+', output)):  # Version number pattern
            logger.info(f"Found help documentation using --help for {main_command}")
            return f"Help output for '{main_command}':\n\n{output}"
        else:
            # Add debug output to see what we're getting
            logger.debug(f"--help output did not match help text pattern:\n{output[:200]}...")

    # Try -h
    logger.debug(f"Trying -h for {main_command}")
    help_result = safe_execute([command_path, "-h"], timeout=5)
    if help_result and help_result.returncode < 2 and help_result.stdout.strip():
        output = help_result.stdout.strip()
        if (re.search(r'usage|options|help|Usage|Options|Help|USAGE|OPTIONS|HELP|USAGE:|VERSION|Version', output, re.IGNORECASE) or
            re.search(r'\d+\.\d+\.\d+', output)):  # Version number pattern
            logger.info(f"Found help documentation using -h for {main_command}")
            return f"Help output for '{main_command}':\n\n{output}"
        else:
            logger.debug(f"-h output did not match help text pattern:\n{output[:200]}...")

    # Try help
    logger.debug(f"Trying help subcommand for {main_command}")
    help_result = safe_execute([command_path, "help"], timeout=5)
    if help_result and help_result.returncode < 2 and help_result.stdout.strip():
        output = help_result.stdout.strip()
        if re.search(r'usage|options|help|Usage|Options|Help|USAGE|OPTIONS|HELP', output, re.IGNORECASE):
            logger.info(f"Found help documentation using help subcommand for {main_command}")
            return f"Help output for '{main_command}':\n\n{output}"
        else:
            logger.debug(f"help subcommand output did not match help text pattern:\n{output[:200]}...")

    # If we get here, no valid help documentation was found
    logger.warning(f"No help documentation found for {main_command}")
    return ""

@mcp.tool()
def get_command_documentation(command: str, prefer_economic: bool = True, man_section: int = None) -> str:
    """
    Get documentation for a command in Unix-like system.

    Args:
        command: The command to get documentation for (no arguments)
        prefer_economic: Whether to prefer the economic approach (--help/-h/help) [default: True]
        man_section: Specific manual section to look in (1-9) [optional]

    Returns:
        The command documentation as a string
    """
    logger.info(f"Getting documentation for command: '{command}', prefer_economic={prefer_economic}, man_section={man_section}")

    # Parse the command input to separate main command from subcommands/arguments
    parts = command.strip().split()
    main_command = parts[0]  # Extract the base command
    logger.debug(f"Main command: {main_command}")

    # Validate command name (basic check to prevent injection)
    if not re.match(r'^[a-zA-Z0-9_\.-]+$', main_command):
        logger.warning(f"Invalid command name: '{main_command}'")
        return f"Invalid command name: '{main_command}'"

    # Get full path to command
    command_path = get_command_path(main_command)
    if not command_path:
        logger.warning(f"Command not found: '{main_command}'")
        return f"Command not found: '{main_command}'"

    # Try economic approach for the main command
    if prefer_economic:
        logger.debug(f"Trying economic approach first for {main_command}")
        help_result = search_help_documentation(main_command, command_path)
        if help_result:
            return help_result

        # Direct check if the previous function failed but command exists
        # Try direct approach for well-known patterns
        if command_path:
            # Try --help directly
            help_cmd = safe_execute([command_path, "--help"], timeout=5)
            if help_cmd and help_cmd.stdout and help_cmd.returncode < 2:
                logger.info(f"Found help docs by direct --help check for {main_command}")
                return f"Help output for '{main_command}':\n\n{help_cmd.stdout.strip()}"

    # Use man as fallback or if economic approach not preferred
    logger.debug(f"Trying man page for {main_command}")
    # Execute man directly without going through shell
    man_args = ["man"]
    if man_section is not None and 1 <= man_section <= 9:
        man_args.append(str(man_section))
        logger.debug(f"Using man section {man_section}")
    man_args.append(main_command)

    try:
        # Use col to strip formatting from man output
        logger.debug(f"Executing man command: {man_args}")
        man_result = subprocess.run(
            man_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        # Pipe the man output through col to remove formatting
        if man_result.returncode == 0:
            logger.debug("Man command succeeded, processing with col")
            col_result = subprocess.run(
                ["col", "-b"],
                input=man_result.stdout,
                capture_output=True,
                text=True
            )
            man_text = col_result.stdout
            logger.info(f"Successfully retrieved man page for {main_command}")
            return f"Manual page for '{main_command}':\n\n{man_text}"
        else:
            logger.warning(f"Man command failed with exit code {man_result.returncode}, stderr: {man_result.stderr}")
    except Exception as e:
        logger.error(f"Error executing man command for {main_command}: {str(e)}")

    # If we tried man first and it failed, try economic approach as fallback
    if not prefer_economic:
        logger.debug(f"Man failed, trying economic approach as fallback for {main_command}")
        help_result = search_help_documentation(main_command, command_path)
        if help_result:
            return help_result

    # If everything failed
    logger.warning(f"All documentation methods failed for '{command}'")
    return f"No documentation available for '{command}'"

@mcp.tool()
def list_common_commands() -> str:
    """
    List common Unix commands available on the system.

    Returns:
        A list of common Unix commands
    """
    logger.info("Listing common commands")
    # Define common directories in PATH that contain commands
    common_dirs = ['/bin', '/usr/bin', '/usr/local/bin']
    logger.debug(f"Searching in directories: {common_dirs}")

    commands = []
    for directory in common_dirs:
        if os.path.exists(directory) and os.path.isdir(directory):
            logger.debug(f"Scanning directory: {directory}")
            # List only executable files
            try:
                for file in os.listdir(directory):
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                        commands.append(file)
            except Exception as e:
                logger.error(f"Error listing directory {directory}: {str(e)}")

    # Remove duplicates and sort
    commands = sorted(set(commands))
    logger.info(f"Found {len(commands)} unique commands")

    # Return a formatted string with command categories
    result = "Common Unix commands available on this system:\n\n"

    # File operations
    file_cmds = [cmd for cmd in commands if cmd in ['ls', 'cp', 'mv', 'rm', 'mkdir', 'touch', 'chmod', 'chown', 'find', 'grep']]
    if file_cmds:
        logger.debug(f"File operation commands found: {len(file_cmds)}")
        result += "File Operations:\n" + ", ".join(file_cmds) + "\n\n"

    # Text processing
    text_cmds = [cmd for cmd in commands if cmd in ['cat', 'less', 'more', 'head', 'tail', 'grep', 'sed', 'awk', 'sort', 'uniq', 'wc']]
    if text_cmds:
        logger.debug(f"Text processing commands found: {len(text_cmds)}")
        result += "Text Processing:\n" + ", ".join(text_cmds) + "\n\n"

    # System information
    sys_cmds = [cmd for cmd in commands if cmd in ['ps', 'top', 'htop', 'df', 'du', 'free', 'uname', 'uptime', 'who', 'whoami']]
    if sys_cmds:
        logger.debug(f"System info commands found: {len(sys_cmds)}")
        result += "System Information:\n" + ", ".join(sys_cmds) + "\n\n"

    # Network tools
    net_cmds = [cmd for cmd in commands if cmd in ['ping', 'netstat', 'ifconfig', 'ip', 'ssh', 'scp', 'curl', 'wget']]
    if net_cmds:
        logger.debug(f"Networking commands found: {len(net_cmds)}")
        result += "Networking:\n" + ", ".join(net_cmds) + "\n\n"

    # Show total count
    result += f"Total commands found: {len(commands)}\n"
    result += "Use get_command_documentation() to learn more about any command."

    return result

@mcp.tool()
def check_command_exists(command: str) -> str:
    """
    Check if a command exists on the system.

    Args:
        command: The command to check

    Returns:
        Information about whether the command exists
    """
    logger.info(f"Checking if command exists: '{command}'")
    command_name = command.strip().split()[0]
    logger.debug(f"Extracted command name: {command_name}")

    if not re.match(r'^[a-zA-Z0-9_\.-]+$', command_name):
        logger.warning(f"Invalid command name: '{command_name}'")
        return f"Invalid command name: '{command_name}'"

    command_path = get_command_path(command_name)
    if command_path:
        logger.info(f"Command '{command_name}' exists at {command_path}")

        # Try --version
        logger.debug(f"Trying --version for {command_name}")
        version_result = safe_execute([command_path, "--version"], timeout=5)
        if version_result and version_result.returncode < 2 and version_result.stdout.strip():
            logger.debug(f"Got version info using --version for {command_name}")
            return f"Command '{command_name}' exists at {command_path}.\nVersion information: {version_result.stdout.strip()}"

        # Try -V (some commands use this for version)
        logger.debug(f"Trying -V for {command_name}")
        version_result = safe_execute([command_path, "-V"], timeout=5)
        if version_result and version_result.returncode < 2 and version_result.stdout.strip():
            logger.debug(f"Got version info using -V for {command_name}")
            return f"Command '{command_name}' exists at {command_path}.\nVersion information: {version_result.stdout.strip()}"

        # Try version
        logger.debug(f"Trying version subcommand for {command_name}")
        version_result = safe_execute([command_path, "version"], timeout=5)
        if version_result and version_result.returncode < 2 and version_result.stdout.strip():
            logger.debug(f"Got version info using version subcommand for {command_name}")
            return f"Command '{command_name}' exists at {command_path}.\nVersion information: {version_result.stdout.strip()}"

        return f"Command '{command_name}' exists on this system at {command_path}."
    else:
        logger.warning(f"Command '{command_name}' does not exist or is not in the PATH")
        return f"Command '{command_name}' does not exist or is not in the PATH."

def main():
    logger.info("Starting unix-manual-server")
    try:
        mcp.run()
    except Exception as e:
        logger.critical(f"Fatal error in MCP server: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
