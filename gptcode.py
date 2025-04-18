import asyncio
import fnmatch
import glob
import os
import re
import sys
from typing import Dict, List, Optional, Union

from agents import Agent, Runner, TResponseInputItem, function_tool, trace
from dotenv import load_dotenv

from commands import CommandSystem


async def run_command(command: str) -> str:
    """Run a command in the shell and return the output."""
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return f"Process exited with code {process.returncode}.\n{stderr.decode()}"
    return stdout.decode()


@function_tool
async def run_tool(command: str) -> str:
    """Run a command in the shell after user confirmation and return the output.

    Args:
        command: The command to run
    """
    confirmation = (
        input(f"Do you want to execute the command: {command}? (y/n): ").strip().lower()
    )
    if confirmation == "y":
        return await run_command(command)
    else:
        return "Command execution canceled by user."


@function_tool
async def list_tool(directory: str) -> str | List[str]:
    """List all files in a directory.

    Args:
        directory: Path to the directory to list
    """
    try:
        files = os.listdir(directory)
        return files
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
async def read_tool(file_path: str, offset: int) -> str:
    """Read the content of a file with an optional limit on the number of lines and an offset.

    Args:
        file_path: Path to the file to read
        offset: Line number to start reading from
    """
    try:
        with open(file_path, "r", errors="ignore") as f:
            lines = f.readlines()

        start_line = 0
        if offset is not None and offset > 0:
            start_line = offset
            lines = lines[start_line:]

        # Format with line numbers like Claude Code's View tool
        result = []
        for i, line in enumerate(lines, start_line + 1):
            result.append(f"{i:6d}\t{line}")

        return "".join(result)
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
async def replace_tool(file_path: str, content: str) -> str:
    """Replace a file with entirely new content.

    Args:
        file_path: Path to the file to replace or create
        content: The new content for the file
    """
    try:
        # Write the file
        with open(file_path, "w") as f:
            f.write(content)

        return f"Successfully replaced {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
async def edit_tool(file_path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing specific text with new text.

    Args:
        file_path: Path to the file to edit
        old_string: The text to be replaced (must match exactly)
        new_string: The text to replace it with
    """
    try:
        # Read the file
        with open(file_path, "r") as f:
            content = f.read()

        # Verify old_string exists in content
        if old_string not in content:
            return f"Error: The specified text was not found in {file_path}"

        # Replace the text
        new_content = content.replace(old_string, new_string, 1)

        # Write the file
        with open(file_path, "w") as f:
            f.write(new_content)

        return f"Successfully edited {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
async def grep_tool(pattern: str, path: str, include: str) -> str:
    """Search file contents using regular expressions.

    Args:
        pattern: The regular expression pattern to search for
        path: The directory to search in
        include: File pattern to include in search (e.g. "*.py")
    """
    try:
        results = []
        regex = re.compile(pattern)

        # Default to current directory if path is None
        search_path = "." if path is None else path

        # Get files to search
        files_to_search = []
        if include:
            for root, _, files in os.walk(search_path):
                for file in files:
                    if fnmatch.fnmatch(file, include):
                        files_to_search.append(os.path.join(root, file))
        else:
            for root, _, files in os.walk(search_path):
                files_to_search.extend(os.path.join(root, file) for file in files)

        # Sort by modification time (newest first)
        files_to_search.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        # Search files
        for file_path in files_to_search:
            try:
                with open(file_path, "r", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{i}: {line.rstrip()}")
            except (PermissionError, IsADirectoryError):
                continue

        if not results:
            return f"No matches found for pattern '{pattern}'"

        return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
async def glob_tool(pattern: str, path: Optional[str] = None) -> Union[str, List[str]]:
    """Find files matching a glob pattern.

    Args:
        pattern: The glob pattern to match against (e.g. "**/*.py")
        path: The directory to search in
    """
    try:
        # Default to current directory if path is None
        search_dir = "." if path is None else path
        search_path = os.path.join(search_dir, pattern)
        matches = glob.glob(search_path, recursive=True)

        # Sort by modification time (newest first)
        matches.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        if not matches:
            return f"No files matching pattern '{pattern}' found in {path}"

        return matches
    except Exception as e:
        return f"Error: {str(e)}"


# Initialize command system
cmd_system = CommandSystem()


@cmd_system.register("/help", "Show this help message")
async def cmd_help(_: List[TResponseInputItem]) -> None:
    """Display help message with available commands"""
    print("\nGPT Code Commands:")
    for cmd in cmd_system.list_commands():
        print(f"  {cmd.name:<10} - {cmd.description}")
    print()


@cmd_system.register("/clear", "Clear conversation history")
async def cmd_clear(_: List[TResponseInputItem]) -> List[TResponseInputItem]:
    """Clear the conversation history"""
    print("Conversation history cleared.")
    return []


@cmd_system.register("/exit", "Exit GPT Code")
async def cmd_exit(_: List[TResponseInputItem]) -> int:
    """Exit the application"""
    return 0


main_agent = Agent(
    name="Main Agent",
    instructions=f"""You are GPT Code, a CLI assistant for software engineering tasks. You help users with coding, debugging, and other programming tasks.

# Tone and style
You should be concise, direct, and to the point. When you run a non-trivial command, you should explain what the command does and why you are running it, to make sure the user understands what you are doing.
Remember that your output will be displayed on a command line interface. Your responses can use markdown for formatting, and will be rendered in a monospace font.
Output text to communicate with the user; all text you output outside of tool use is displayed to the user. Only use tools to complete tasks.
If you cannot or will not help the user with something, please do not say why or what it could lead to. Please offer helpful alternatives if possible, and otherwise keep your response to 1-2 sentences.
IMPORTANT: You should minimize output tokens as much as possible while maintaining helpfulness, quality, and accuracy. Only address the specific query or task at hand, avoiding tangential information unless absolutely critical for completing the request. If you can answer in 1-3 sentences or a short paragraph, please do.
You should NOT answer with unnecessary preamble or postamble (such as explaining your code or summarizing your action), unless the user asks you to.
Keep your responses short, since they will be displayed on a command line interface. Answer concisely with fewer than 4 lines (not including tool use or code generation), unless user asks for detail. Answer the user's question directly, without elaboration, explanation, or details. Avoid introductions, conclusions, and explanations.

# Proactiveness
You are allowed to be proactive, but only when the user asks you to do something. You should strive to strike a balance between:
1. Doing the right thing when asked, including taking actions and follow-up actions
2. Not surprising the user with actions you take without asking
For example, if the user asks you how to approach something, you should do your best to answer their question first, and not immediately jump into taking actions.

# Following conventions
When making changes to files, first understand the file's code conventions. Mimic code style, use existing libraries and utilities, and follow existing patterns.
- NEVER assume that a given library is available, even if it is well known. Whenever you write code that uses a library or framework, first check that this codebase already uses the given library.
- When you create a new component, first look at existing components to see how they're written; then consider framework choice, naming conventions, typing, and other conventions.
- When you edit a piece of code, first look at the code's surrounding context (especially its imports) to understand the code's choice of frameworks and libraries. Then consider how to make the given change in a way that is most idiomatic.
- Always follow security best practices. Never introduce code that exposes or logs secrets and keys.

# Code style
- DO NOT ADD ANY COMMENTS unless asked

# Doing tasks
The user will primarily request you perform software engineering tasks. This includes solving bugs, adding new functionality, refactoring code, explaining code, and more. For these tasks the following steps are recommended:
1. Use the available search tools to understand the codebase and the user's query
2. Implement the solution using all tools available to you
3. Verify the solution if possible with tests

# Environment information
Current directory: {os.getcwd()}
Top-level files: {os.listdir(os.getcwd())}
Current operating system: {sys.platform}
""",
    tools=[
        run_tool,
        list_tool,
        read_tool,
        replace_tool,
        edit_tool,
        grep_tool,
        glob_tool,
    ],
    handoffs=[],
)


async def main() -> int:
    context: list[TResponseInputItem] = []

    # Print welcome message
    print("Welcome to GPT Code - a CLI assistant for software engineering tasks")
    print("Type '/help' for available commands or '/exit' to quit")
    print()

    with trace("GPT Code"):
        while True:
            try:
                prompt = input("\033[1;36m>\033[0m ")  # Cyan prompt for visibility

                # Handle command system
                if prompt.startswith("/"):
                    cmd_name = prompt.split()[0]  # Get the command name (first word)
                    command = cmd_system.get_command(cmd_name)

                    if command:
                        result = await command.handler(context)
                        if isinstance(result, int):  # Exit code
                            return result
                        elif result is not None:  # New context
                            context = result
                        continue
                    else:
                        print(
                            f"Unknown command: {cmd_name}. Type /help for available commands."
                        )
                        continue

                # Process normal prompts
                result = await Runner.run(
                    main_agent,
                    context
                    + [
                        {"role": "user", "content": prompt},
                    ],
                    max_turns=32
                )
                context = result.to_input_list()

                # Print the result
                print(f"\n{result.final_output}")

            except KeyboardInterrupt:
                print("\nUse '/exit' to quit GPT Code")
                continue
            except Exception as e:
                print(f"Error: {str(e)}")


def setup_environment():
    """Set up the environment for GPT Code."""
    load_dotenv()

    # Create banner
    print("\033[1;32m")  # Bright green
    print("  ____  ____  _____    ____          _      ")
    print(" / ___||  _ \\|_   _|  / ___|___   __| | ___ ")
    print("| |  _ | |_) | | |   | |   / _ \\ / _` |/ _ \\")
    print("| |_| ||  __/  | |   | |__| (_) | (_| |  __/")
    print(" \\____||_|     |_|    \\____\\___/ \\__,_|\\___|")
    print("\033[0m")  # Reset color


if __name__ == "__main__":
    setup_environment()
    sys.exit(asyncio.run(main()))
