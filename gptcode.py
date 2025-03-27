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
    return await run_command(command)


@function_tool
async def edit_file(file_path: str, content: str) -> str:
    """Edit a file with the given diff using Git."""
    process = await asyncio.create_subprocess_shell(
        f"git apply --cached {file_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return f"Process exited with code {process.returncode}.\n{stderr.decode()}"
    return stdout.decode()


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
            result = await Runner.run(
                main_agent,
                context
                + [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            context += result.to_input_list()

        print(f"{result.final_output}")


if __name__ == "__main__":
    load_dotenv()
    sys.exit(asyncio.run(main()))
