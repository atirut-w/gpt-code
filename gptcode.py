from dotenv import load_dotenv
from openai import OpenAI
import asyncio
import os
import sys
from typing import Optional
from agents import TResponseInputItem, Agent, RunResult, Runner, function_tool


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
async def edit_file(file_path: str, content: str) -> str:
    """Edit a file using the provided Git diff content."""
    import tempfile
    
    # Create a temporary file with the diff content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as temp:
        temp.write(content)
        temp_path = temp.name
    
    try:
        # Apply the patch
        process = await asyncio.create_subprocess_shell(
            f"git apply {temp_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        if process.returncode != 0:
            return f"Failed to apply diff: {stderr.decode()}"
        return f"Successfully applied diff to {file_path}"
    except Exception as e:
        # Clean up the temporary file in case of exception
        os.unlink(temp_path)
        return f"Error: {str(e)}"


main_agent = Agent(
    name="Main",
    instructions=f"""You are the Main agent. Your job is to process user requests and determine the best way to handle them. You will either respond directly or delegate to other specialized agents when needed.
    
Current working directory: {os.getcwd()}
Directory contents: {os.listdir('.')}""",
    tools=[run_command_tool, edit_file],
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
