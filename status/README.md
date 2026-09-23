# Public AI Status App

A lightweight Next.js status dashboard with Docker and Docker Compose support.

## Getting Started

### Local Development (with Node.js)

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) in your browser.

### Run with Docker Compose

1. Build and start the container:
   ```bash
   docker compose up -d --build
   ```

2. Access the status app at [http://localhost:3000](http://localhost:3000).

3. Stop the container:
   ```bash
   docker compose down
   ```

### Production Build

```bash
npm run build
npm start
```
