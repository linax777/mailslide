"""Message collection helpers for job processing."""

from typing import Any


class MessageCollector:
    """Collect mail items from an Outlook folder in descending received time order."""

    def collect_messages(self, messages: Any, *, limit: int) -> list[Any]:
        """Collect up to ``limit`` mail items from ``messages`` collection."""
        messages.Sort("[ReceivedTime]", True)

        msg_list: list[Any] = []
        msg = messages.GetFirst()
        while msg and len(msg_list) < limit:
            if getattr(msg, "Class", None) == 43:  # Mail item
                msg_list.append(msg)
            msg = messages.GetNext()

        return msg_list
