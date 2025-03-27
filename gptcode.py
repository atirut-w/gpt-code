import asyncio
import os
import sys
from typing import Optional

from agents import Agent, Runner, RunResult, TResponseInputItem, function_tool
from dotenv import load_dotenv
from openai import OpenAI


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
async def run_command_tool(command: str) -> str:
    """Run a command in the shell and return the output."""
    return await run_command(command)


@function_tool
async def replace_file(file_path: str, content: str) -> str:
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
async def edit_file(file_path: str, old_string: str, new_string: str) -> str:
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
    name="Main",
    instructions=f"""You are the Main agent. Your job is to process user requests and determine the best way to handle them. You will either respond directly or delegate to other specialized agents when needed.
    
Current working directory: {os.getcwd()}
Directory contents: {os.listdir('.')}""",
    tools=[run_command_tool, edit_file, replace_file],
    handoffs=[],
)


async def main() -> int:
    context: list[TResponseInputItem] = []

    while True:
        prompt = input("> ")

        result: Optional[RunResult] = None
        if len(context) == 0:
            result = await Runner.run(main_agent, prompt)
            context = result.to_input_list()
        else:
            # Create a new context to avoid duplicate message IDs
            new_message = {
                "role": "user",
                "content": prompt,
            }
            result = await Runner.run(main_agent, context + [new_message])

            # Only append the new user message and the latest response
            # to avoid duplicate message IDs
            context.append(new_message)
            context.append(result.to_input_list()[-1])

        print(f"{result.final_output}")


if __name__ == "__main__":
    load_dotenv()
    sys.exit(asyncio.run(main()))
