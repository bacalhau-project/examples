# Event Puller Dashboard

A modern web interface for the Event Puller service, built with Next.js and Tailwind CSS.

## Features

- Real-time event monitoring via WebSockets
- Visual representation of VM and container status
- Queue management and statistics
- Connection status and metrics
- CosmosDB integration status

## Development

First, set up and run the Event Puller service:

```bash
# In the parent directory
go build -o bin/event-puller
./bin/event-puller
```

Then, run the dashboard development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

By default, the dashboard will attempt to connect to a WebSocket server running at the same host. To connect to a different Event Puller instance, use query parameters:

```
http://localhost:3000/?host=your-event-puller-host&port=8080
```

## Building for Production

The dashboard can be built as a static site:

```bash
# Build the static site
npm run build
```

This creates a `out` directory with the static files, which are automatically included in the Event Puller Docker container when using the build script.

## Integration with Event Puller

The dashboard communicates with the Event Puller service through:

1. **WebSocket connection** - Receives real-time event updates
2. **API endpoints** - Sends commands like queue clearing

When the Event Puller service starts, it checks for the dashboard static files in the `dashboard/out` directory and serves them if available.
