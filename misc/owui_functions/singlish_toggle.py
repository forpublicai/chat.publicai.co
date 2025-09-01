from pydantic import BaseModel, Field
from typing import Optional
import base64


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Creates a switch UI in Open WebUI

        # Singapore flag SVG with fixed colors for dark mode
        singapore_flag_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" style="color-scheme: initial;">
            <rect width="900" height="300" fill="#ED2939" style="fill: #ED2939 !important;"/>
            <rect y="300" width="900" height="300" fill="#FFFFFF" style="fill: #FFFFFF !important;"/>
            <circle cx="225" cy="150" r="85" fill="#FFFFFF" style="fill: #FFFFFF !important;"/>
            <circle cx="240" cy="150" r="70" fill="#ED2939" style="fill: #ED2939 !important;"/>
            <g fill="#FFFFFF" style="fill: #FFFFFF !important;">
                <polygon points="340,90 347,110 367,110 351,122 358,142 340,130 322,142 329,122 313,110 333,110" />
                <polygon points="380,115 387,135 407,135 391,147 398,167 380,155 362,167 369,147 353,135 373,135" />
                <polygon points="340,165 347,185 367,185 351,197 358,217 340,205 322,217 329,197 313,185 333,185" />
                <polygon points="300,140 307,160 327,160 311,172 318,192 300,180 282,192 289,172 273,160 293,160" />
                <polygon points="380,165 387,185 407,185 391,197 398,217 380,205 362,217 369,197 353,185 373,185" />
            </g>
        </svg>"""

        svg_base64 = base64.b64encode(singapore_flag_svg.encode("utf-8")).decode(
            "utf-8"
        )
        self.icon = f"data:image/svg+xml;base64,{svg_base64}"

    async def inlet(
        self, body: dict, __event_emitter__, __user__: Optional[dict] = None
    ) -> dict:
        if not self.toggle:
            return body

        # Default Singlish instruction
        singlish_instruction = {
            "role": "system",
            "content": "Respond in casual Singlish naturally. Keep it authentic but not too heavy - like how Singaporeans actually speak.",
        }

        # Insert at the beginning of messages
        body.setdefault("messages", []).insert(0, singlish_instruction)

        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Singlish mode ON 🇸🇬",
                    "done": True,
                    "hidden": False,
                },
            }
        )

        return body
