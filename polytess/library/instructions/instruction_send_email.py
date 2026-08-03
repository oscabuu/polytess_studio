# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Send a notification email via the system sendmail."""

from __future__ import annotations

import asyncio
import getpass
import shutil
import socket

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetString

SENDMAIL = "/usr/sbin/sendmail"


@meta(title="Send Email", category="Notify/Send Email", icon="message", color="teal",
      description="Sends an email via the system sendmail (success/failure "
                  "notifications); logs a warning instead of failing if "
                  "sendmail is unavailable (unless strict)",
      keywords=("mail", "notify", "sendmail", "report"))
class SendEmail(Instruction):

    FIELD_HELP = {
        "to": "Recipient address; empty = the node is skipped with a "
              "warning.",
        "subject": "Subject line of the email.",
        "body": "Plain-text message body.",
        "strict": "When enabled, a missing sendmail binary or a send "
                  "failure raises an error; otherwise only a warning "
                  "is logged (default).",
    }

    def __init__(self, to: str = "", subject: str = "", body: str = ""):
        super().__init__()
        self.to = PropertyGetString(to)
        self.subject = PropertyGetString(subject)
        self.body = PropertyGetString(body)
        self.strict = PropertyGetBool(False)

    @property
    def title(self) -> str:
        return f"Email to {self.to}: {self.subject}"

    async def run(self, ctx):
        recipient = self.to.get(ctx).strip()
        if not recipient:
            ctx.warning("Send Email: no recipient set — skipped")
            return
        sender = f"{getpass.getuser()}@{socket.gethostname()}"
        message = (f"From: {sender}\nTo: {recipient}\n"
                   f"Subject: {self.subject.get(ctx)}\n\n{self.body.get(ctx)}\n")
        binary = SENDMAIL if shutil.which(SENDMAIL) or shutil.which("sendmail") else None
        if binary is None and shutil.which("sendmail"):
            binary = "sendmail"
        if binary is None:
            note = f"Send Email: sendmail not available (to={recipient})"
            if self.strict.get(ctx):
                raise RuntimeError(note)
            ctx.warning(note + " — skipped")
            return
        process = await asyncio.create_subprocess_exec(
            binary, "-t", "-oi",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
        _, err = await process.communicate(message.encode())
        if process.returncode != 0:
            note = f"Send Email failed ({process.returncode}): {err.decode().strip()}"
            if self.strict.get(ctx):
                raise RuntimeError(note)
            ctx.warning(note)
        else:
            ctx.info(f"Email sent to {recipient}")
