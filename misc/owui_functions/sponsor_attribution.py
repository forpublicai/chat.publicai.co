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
            {"name": "Exoscale", "location": "Austria", "country": "Austria"},
            {
                "name": "National Computational Infrastructure",
                "location": "Australia",
                "country": "Australia",
            },
        ]

        # Attribution message variants for each sponsor (full messages with emojis)
        self.attribution_variants = {
            "AI Singapore": [
                "🇸🇬 Powered by sovereign compute infrastructure in Singapore, provided by AI Singapore",
                "🚀 Running on cutting-edge AI compute resources from the heart of Singapore, courtesy of AI Singapore",
                "⚡ Energized by next-generation computational power from Singapore's AI innovation hub, AI Singapore",
                "🏙️ Streaming from state-of-the-art processing infrastructure in the Lion City, powered by AI Singapore",
                "🧠 Thinking with advanced computational resources from Singapore's premier AI institute, AI Singapore",
            ],
            "Amazon Web Services": [
                "☁️ Powered by cloud-native compute infrastructure in Zurich, provided by Amazon Web Services",
                "🏔️ Running on scalable computational resources from the Swiss Alps region, courtesy of AWS Zurich",
                "💼 Energized by enterprise-grade compute power from Switzerland's financial capital, powered by Amazon Web Services",
                "🎯 Streaming with globally-distributed infrastructure with Swiss precision, provided by AWS Zurich",
                "🌍 Thinking on hyperscale computational resources from the heart of Europe, courtesy of Amazon Web Services",
            ],
            "Exoscale": [
                "❄️ Powered by liquid-cooled compute infrastructure in Austria, provided by Exoscale",
                "🌿 Running on carbon-neutral computational power from the Austrian Alps, courtesy of Exoscale",
                "🛡️ Energized by European sovereign cloud infrastructure in Austria, powered by Exoscale",
                "🔋 Streaming with green energy-powered compute resources from Austria's data centers, provided by Exoscale",
                "🔒 Thinking on privacy-focused computational infrastructure in the heart of Europe, courtesy of Exoscale",
            ],
            "National Computational Infrastructure": [
                "🦘 Powered by high-performance computing infrastructure across Australia, provided by National Computational Infrastructure",
                "🔬 Running on research-grade computational resources from Down Under, courtesy of NCI Australia",
                "⚡ Energized by supercomputing power from Australia's national research infrastructure, powered by NCI",
                "🌏 Streaming across continent-spanning computational resources in Australia, provided by National Computational Infrastructure",
                "🏆 Thinking with world-class HPC infrastructure from Australia's research computing backbone, courtesy of NCI",
            ],
        }

    def get_sponsor_by_model(self, model_name: str):
        """Get sponsor based on model name"""
        model_lower = model_name.lower()

        if "singapore" in model_lower or "sea-lion" in model_lower:
            sponsor = next(s for s in self.sponsors if s["name"] == "AI Singapore")
        elif "apertus" in model_lower:
            # For apertus models, randomly select from the other sponsors
            other_sponsors = [s for s in self.sponsors if s["name"] != "AI Singapore"]
            sponsor = random.choice(other_sponsors)
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

            # Optional: Store sponsor info in body for downstream use
            body["_sponsor_info"] = {
                "name": sponsor_info["sponsor_name"],
                "location": sponsor_info["sponsor_location"],
                "country": sponsor_info["sponsor_country"],
                "attribution": sponsor_info["attribution_message"],
            }

        return body
