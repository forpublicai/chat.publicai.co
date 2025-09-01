from pydantic import BaseModel, Field
from typing import Optional
import base64


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Creates a switch UI in Open WebUI

        # Swiss flag SVG with fixed colors for dark mode
        swiss_flag_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320" style="color-scheme: initial;">
            <rect width="320" height="320" fill="#FF0000" style="fill: #FF0000 !important;"/>
            <rect x="80" y="40" width="160" height="240" fill="#FFFFFF" style="fill: #FFFFFF !important;"/>
            <rect x="40" y="80" width="240" height="160" fill="#FFFFFF" style="fill: #FFFFFF !important;"/>
        </svg>"""

        svg_base64 = base64.b64encode(swiss_flag_svg.encode("utf-8")).decode("utf-8")
        self.icon = f"data:image/svg+xml;base64,{svg_base64}"

    async def inlet(
        self, body: dict, __event_emitter__, __user__: Optional[dict] = None
    ) -> dict:
        if not self.toggle:
            return body

        # Default Swiss German instruction
        swiss_instruction = {
            "role": "system",
            "content": "Respond in casual Swiss German (Schwizerdütsch). Use typical Swiss expressions like 'öppe' (etwa), 'luege' (schauen), 'chönd' (können), and particles like 'halt', 'scho', 'ou'. Mix in authentic Swiss German grammar patterns and vocabulary naturally.",
        }

        # Insert at the beginning of messages
        body.setdefault("messages", []).insert(0, swiss_instruction)

        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Schwizerdütsch mode ON 🇨🇭",
                    "done": True,
                    "hidden": False,
                },
            }
        )

        return body
