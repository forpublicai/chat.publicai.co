# Public AI Inference Utility

**A public compute platform for everyone.**

The Public AI Inference Utility is a public compute platform that provides free and low-cost access to state-of-the-art AI models. Built on principles of openness and accessibility, the Utility serves as critical infrastructure for citizens, businesses, researchers, and the public sectors of several different countries.

Unlike commercial AI APIs that prioritize profit maximization, the Utility is designed to serve the public interest. We provide transparent pricing, open governance, and equitable access to ensure that AI capabilities are available to everyone, not just those who can afford premium services.

This repository contains the production deployment configuration and community contributions for the platform.

## How to Contribute

We welcome contributions from the community! There are several ways you can help make AI more accessible:

### 🤝 Community Contributions (`/community`)

The `community/` folder contains user-contributed enhancements that make the platform more accessible and useful:

- **`owui_functions/`**: Custom functions and tools for the Open WebUI platform
  - Language toggle functions (Schwizerdütsch, Singlish)
  - Sponsor attribution utilities
  - Custom AI model integrations
- **`system_prompts/`**: Region-specific and specialized system prompts
  - Localized prompts for different countries/regions
  - Domain-specific prompt templates

**How to contribute to community features:**
1. Fork this repository
2. Add your function to the appropriate folder in `community/`
3. Include documentation and examples
4. Submit a pull request with a clear description

### ⚙️ Infrastructure Contributions (`/charts`)

For technically-minded contributors, the `charts/` folder contains Helm charts for Kubernetes deployment:

- **`infrastructure/`**: Core infrastructure components (databases, networking)
- **`llm_services/`**: AI model serving infrastructure
- **`web_ingress/`**: Load balancing and SSL termination
- **`web_services/`**: Application services and monitoring

**How to contribute to infrastructure:**
1. Review existing chart configurations
2. Test your changes in a staging environment
3. Ensure compatibility with existing deployments
4. Submit pull requests with detailed technical documentation

### 🚀 Platform Development & Governance

We are currently in **beta** and working toward progressive decentralization of the platform. Our goal is to create more accessible ways for people to contribute beyond just code and infrastructure.

**We want to hear from you:**
- Have ideas for making AI more accessible to your community?
- Want to help with governance, documentation, or outreach?
- Interested in regional partnerships or localized deployments?
- Have feedback on how we can better serve researchers and developers?

**Get involved:**
- [Open an issue](../../issues) to discuss your ideas
- Reach out to us directly with proposals for collaboration
- Join our community discussions about platform direction and governance

We believe the best infrastructure is built by and for the communities it serves.

## Project Structure

```
├── README.md
├── community/               # Community contributions
│   ├── owui_functions/     # Custom Open WebUI functions
│   └── system_prompts/     # Region-specific prompts
├── charts/                 # Kubernetes Helm charts
│   ├── infrastructure/     # Core infrastructure
│   ├── llm_services/      # AI model services
│   ├── web_ingress/       # Load balancers & SSL
│   └── web_services/      # Application services
```

## Getting Started

To get involved with the Public AI Inference Utility:

1. **Explore the platform**: Visit [chat.publicai.co](https://publicai.co) to see the platform in action
2. **Join the community**: Check out existing contributions in the `/community` folder
3. **Contribute**: Choose your contribution path based on your skills and interests
4. **Stay updated**: Watch this repository for updates and new contribution opportunities

Together, we're building infrastructure that democratizes access to AI capabilities for everyone.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
