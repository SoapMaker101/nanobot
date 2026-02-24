"""Message tool for sending messages to users."""

from pathlib import Path
from typing import Any, Awaitable, Callable

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.filesystem import _resolve_path
from nanobot.bus.events import OutboundMessage


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        default_message_id: str | None = None,
        workspace: Path | None = None,
    ):
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id
        self._default_message_id = default_message_id
        self._workspace = workspace
        self._sent_in_turn: bool = False

    def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id
        self._default_message_id = message_id

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        self._sent_in_turn = False

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return (
            "Send a message to the user. To send a FILE (e.g. after creating it with write_file), pass the file path in the media array: message(content='...', media=['hello.txt']). "
            "Without media, only text is sent; with media, the file is attached."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message text to send"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: target chat/user ID"
                },
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths to attach (e.g. ['hello.txt']). Required when sending a file to the user — use the same path you used in write_file."
                }
            },
            "required": ["content"]
        }

    async def execute(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        message_id: str | None = None,
        media: list[str] | None = None,
        **kwargs: Any
    ) -> str:
        channel = channel or self._default_channel
        chat_id = chat_id or self._default_chat_id
        message_id = message_id or self._default_message_id

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        # Resolve media paths to absolute (relative to workspace) so channels can open files
        media_raw = media or []
        media_resolved = [str(_resolve_path(m, self._workspace, None)) for m in media_raw]

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=media_resolved,
            metadata={
                "message_id": message_id,
            }
        )

        try:
            await self._send_callback(msg)
            self._sent_in_turn = True
            media_info = f" with {len(media_resolved)} attachments" if media_resolved else ""
            return f"Message sent to {channel}:{chat_id}{media_info}"
        except Exception as e:
            return f"Error sending message: {str(e)}"
