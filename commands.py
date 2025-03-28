from typing import Dict, List, Optional, Callable, Any, TypeVar

from agents import TResponseInputItem

T = TypeVar("T")


class Command:
    """Represents a command with a name, description, and handler function."""

    def __init__(self, name: str, description: str, handler: Callable):
        self.name = name
        self.description = description
        self.handler = handler


class CommandSystem:
    """A system for managing and executing commands."""

    def __init__(self):
        self.commands: Dict[str, Command] = {}

    def register(self, name: str, description: str):
        """Decorator to register a command handler."""

        def decorator(handler: Callable):
            self.commands[name] = Command(name, description, handler)
            return handler

        return decorator

    def get_command(self, name: str) -> Optional[Command]:
        """Get a command by name."""
        return self.commands.get(name)

    def list_commands(self) -> List[Command]:
        """Get all registered commands."""
        return list(self.commands.values())

    def execute(self, cmd_name: str, context: Any) -> Any:
        """Execute a command by name."""
        command = self.get_command(cmd_name)
        if command:
            return command.handler(context)
        return None
