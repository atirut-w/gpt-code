import asyncio
import os
import sys
import subprocess
from typing import Optional, Dict, List

from agents import Agent, Runner, RunResult, TResponseInputItem, function_tool
from dotenv import load_dotenv
from openai import OpenAI

def get_project_info() -> Dict[str, str]:
    """Gather information about the current project."""
    info = {
        "cwd": os.getcwd(),
        "files": os.listdir('.'),
        "is_git_repo": False,
        "git_branch": "",
        "git_status": ""
    }
    
    # Check if this is a git repository
    try:
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], stderr=subprocess.DEVNULL)
        info["is_git_repo"] = True
        
        # Get git branch
        branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
        info["git_branch"] = branch
        
        # Get git status
        status = subprocess.check_output(["git", "status", "--short"]).decode().strip()
        info["git_status"] = status
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return info


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
    """Run a command in the shell after user confirmation and return the output."""
    confirmation = input(f"Do you want to execute the command: {command}? (y/n): ").strip().lower()
    if confirmation == 'y':
        return await run_command(command)
    else:
        return "Command execution canceled by user."


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


project_info = get_project_info()

# This one helps the main agent plan tasks
planner = Agent(
    name="Planner",
    instructions="You are a planning assistant. Your job is to help the main agent plan tasks. You will receive a task and you need to break it down into smaller steps.",
    tools=[],
    handoffs=[],
)

main_agent = Agent(
    name="Main",
    instructions=f"""You are GPT Code, an AI assistant specialized in helping with coding tasks. Your job is to process user requests and provide helpful responses for software development tasks.

PROJECT CONTEXT:
- Working directory: {project_info['cwd']}
- Files in directory: {', '.join(project_info['files'])}
- Git repository: {'Yes' if project_info['is_git_repo'] else 'No'}
- Current branch: {project_info['git_branch'] if project_info['is_git_repo'] else 'N/A'}
- File status: {project_info['git_status'] if project_info['git_status'] else 'No changes'}

Aim to provide concise, practical responses. For complex tasks, break them down into clear steps.""",
    tools=[run_command_tool, read_file, edit_file, replace_file],
    handoffs=[planner],
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
