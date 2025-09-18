from typing import Optional
import random


class Filter:
    def __init__(self):
        # icon shows up in the plugin list in WebUI
        self.icon = "⚡"

        # Separated sponsor data
        self.sponsors = [
            {"name": "AI Singapore", "location": "Singapore", "country": "Singapore"},
            {
                "name": "Amazon Web Services",
                "location": "Zurich",
                "country": "Switzerland",
            },
            {"name": "Exoscale", "location": "Vienna", "country": "Austria"},
            {
                "name": "National Computational Infrastructure",
                "location": "Canberra",
                "country": "Australia",
            },
            {"name": "Cudo Compute", "location": "Oslo", "country": "Norway"},
            {"name": "Swiss National Supercomputing Centre", "location": "Lugano", "country": "Switzerland"},
        ]

        # Attribution message variants for each sponsor (full messages with emojis)
        self.attribution_variants = {
            "AI Singapore": [
                "⚡ Powered by compute infrastructure in Singapore, provided by AI Singapore",
            ],
            "Amazon Web Services": ["⚡ I run on AWS infrastructure in Switzerland"],
            "Exoscale": [
                "❄️ Powered by liquid-cooled compute infrastructure in Austria, provided by Exoscale",
            ],
            "National Computational Infrastructure": [
                "⚡ Powered by soverign compute infrastructure in Canberra, courtesy of NCI Australia ",
            ],
            "Cudo Compute": [
                "⚡ Powered by compute infrastructure in Europe, provided by Cudo Compute",
            ],
            "Swiss National Supercomputing Centre": [
                "⚡ Powered by soverign compute infrastructure in Lugano, courtesy of Swiss National Supercomputing Centre",
            ],
        }

    def get_sponsor_by_model(self, model_name: str):
        """Get sponsor based on model name"""
        model_lower = model_name.lower()

        if "singapore" in model_lower or "sea-lion" in model_lower:
            sponsor = next(s for s in self.sponsors if s["name"] == "AI Singapore")
        elif "apertus" in model_lower:
            # For apertus models: AWS, Cudo, and Swiss National Supercomputing Centre have equal weight
            # AI Singapore has much lower weight
            sponsors_apertus = [
                next(s for s in self.sponsors if s["name"] == "Amazon Web Services"),
                next(s for s in self.sponsors if s["name"] == "Cudo Compute"),
                next(s for s in self.sponsors if s["name"] == "Swiss National Supercomputing Centre"),
                next(s for s in self.sponsors if s["name"] == "AI Singapore")
            ]
            weights = [1, 1, 1, 0.05]  # AI Singapore gets 5% weight compared to others
            sponsor = random.choices(sponsors_apertus, weights=weights)[0]
        else:
            # Default: random selection from all sponsors
            sponsor = random.choice(self.sponsors)

        variants = self.attribution_variants[sponsor["name"]]
        attribution = random.choice(variants)

        return {
            "sponsor_name": sponsor["name"],
            "sponsor_location": sponsor["location"],
            "sponsor_country": sponsor["country"],
            "attribution_message": attribution,
        }

    async def inlet(
        self, body: dict, __event_emitter__, __user__: Optional[dict] = None
    ) -> dict:
        # Detect if this is the start of a new conversation
        # In OpenWebUI, first turn typically has no "messages" or just 1 user message
        messages = body.get("messages", [])
        if len(messages) <= 1:
            # Get current model from body (top-level "model" key)
            model_name = body.get("model", "")

            # Get sponsor attribution based on the current model
            sponsor_info = self.get_sponsor_by_model(model_name)

            # Send the complete attribution message (already includes emoji and "Powered by")
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": sponsor_info["attribution_message"],
                        "done": True,
                        "hidden": False,
                    },
                }
            )

            # Note: We don't store sponsor info in body as some providers (like Bedrock)
            # reject extra parameters. The attribution is already sent via event_emitter.

        return body
