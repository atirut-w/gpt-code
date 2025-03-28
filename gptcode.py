import asyncio
import os
import sys
from typing import List, Optional

from agents import Agent, Runner, TResponseInputItem, function_tool, trace
from dotenv import load_dotenv


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
async def read_tool(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Read the content of a file with an optional limit on the number of lines and an offset.

    Args:
        file_path: Path to the file to read
        offset: Optional line number to start reading from
        limit: Optional limit on the number of lines to read
    """
    try:
        with open(file_path, "r", errors='ignore') as f:
            lines = f.readlines()
        
        start_line = 0
        if offset is not None and offset > 0:
            start_line = offset
            lines = lines[start_line:]
            
        if limit is not None:
            lines = lines[:limit]
            
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


main_agent = Agent(
    name="Main Agent",
    instructions=f"""Assist with coding tasks. If you don't know something, use the available tools or hand off to other agents to let them handle the task.

Current directory: {os.getcwd()}""",
    tools=[
        list_tool,
        read_tool,
        replace_tool,
        edit_tool,
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
                
                # Handle special commands
                if prompt.strip() == "/help":
                    print("\nGPT Code Commands:")
                    print("  /help      - Show this help message")
                    print("  /clear     - Clear conversation history")
                    print("  /exit      - Exit GPT Code")
                    print()
                    continue
                
                if prompt.strip() == "/clear":
                    context = []
                    print("Conversation history cleared.")
                    continue
                
                if prompt.strip() in ["/exit", "/quit"]:
                    return 0
                
                # Process normal prompts
                result = await Runner.run(main_agent, context + [
                    {
                        "role": "user",
                        "content": prompt
                    },
                ])
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
