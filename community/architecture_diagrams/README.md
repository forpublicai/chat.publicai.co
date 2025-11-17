# Architecture Diagrams

This folder contains architecture diagrams for the Public AI infrastructure using [D2](https://d2lang.com/), a declarative diagram language.

## What's in this folder

- `architecture.d2` - The source file defining the system architecture in D2 format
- `architecture.svg` - Generated SVG diagram (auto-updated when watching)

## Architecture Overview

The diagram illustrates the complete Public AI platform architecture, including:

- **User Portal** (OpenWebUI at chat.publicai.co) - Web interface for end users
- **Developer Portal** (Zudoku at platform.publicai.co) - Documentation and API key management
- **AI Gateway** (LiteLLM at api.publicai.co) - Central routing hub for AI inference requests
- **Landing Page** (Vercel at publicai.company) - Marketing site
- **Inference Partners** - Both managed and bare-metal compute providers
- **Identity Providers** - AWS Cognito (users) and Auth0 (developers)
- **Data Layer** - AWS managed PostgreSQL, Redis, and S3

## How to use

### Prerequisites

Install D2:
```bash
brew install d2  # macOS
# or visit https://d2lang.com/tour/install for other platforms
```

### Generate the diagram

To generate a one-time SVG from the D2 file:
```bash
d2 -w architecture_components.d2 architecture_components.svg --layout=elk
```

### Watch mode (recommended for editing)

To automatically regenerate the SVG whenever the D2 file changes:
```bash
d2 -w architecture.d2 architecture.svg --layout=elk
```

### Layout options

The `--layout=elk` flag uses the ELK (Eclipse Layout Kernel) layouter for hierarchical diagrams. Other options include:
- `dagre` - Default directed graph layout
- `tala` - Specialized for larger diagrams

## Editing the diagram

1. Open `architecture.d2` in your text editor
2. Run the watch command: `d2 -w architecture.d2 architecture.svg --layout=elk`
3. Open `architecture.svg` in your browser or preview tool
4. Make changes to the `.d2` file and the SVG will auto-update

## D2 Resources

- [D2 Documentation](https://d2lang.com/)
- [D2 Playground](https://play.d2lang.com/) - Test syntax in browser
- [D2 Tour](https://d2lang.com/tour/intro) - Interactive tutorial
