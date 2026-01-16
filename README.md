# F1 MCP Server

A Model Context Protocol (MCP) server that provides comprehensive Formula 1 data and analytics for Claude Desktop integration.

## Features

This server exposes 36+ tools for accessing F1 data:

### Race Data
- Race results and classifications
- Sprint race results
- Qualifying progression (Q1, Q2, Q3)
- Grid vs finish comparisons
- DNF lists and retirement reasons

### Telemetry & Analysis
- Speed trace comparisons between drivers
- Gear shift visualizations
- Brake and throttle analysis
- RPM and engine data
- DRS usage patterns

### Timing & Laps
- Fastest lap data with sector times
- Lap-by-lap timing
- Deleted laps (track limits)
- Lap consistency statistics
- Personal best laps

### Strategy
- Tire compound analysis
- Stint breakdowns
- Pit stop data and fastest stops
- Starting tire choices
- Strategy comparisons

### Standings & History
- Driver championship standings
- Constructor standings
- Historical race winners
- Track records

### Live Data
- Live session status
- Real-time positions
- Live lap times
- Live telemetry
- Current weather conditions

### Other
- Team radio links
- Race control messages
- Track status (flags, safety car)
- Weather data
- Circuit information

## Installation

### Prerequisites

- Python 3.10 or higher
- Claude Desktop

### Setup

1. Clone this repository:
```bash
git clone https://github.com/drivenrajat/f1.git
cd f1
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

### Configure Claude Desktop

Add this server to your Claude Desktop MCP configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "f1": {
      "command": "python",
      "args": ["/path/to/f1/f1_server.py"]
    }
  }
}
```

Or if using uv:

```json
{
  "mcpServers": {
    "f1": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/f1", "python", "f1_server.py"]
    }
  }
}
```

## Usage

Once configured, you can ask Claude questions like:

- "Show me the 2024 F1 calendar"
- "Get the race results from Monaco 2024"
- "Compare telemetry between Verstappen and Norris at Silverstone qualifying"
- "What was Hamilton's tire strategy at Spa?"
- "Show me the current driver standings"
- "Get the fastest pit stops from the Italian GP"

## Data Sources

- **FastF1**: Historical telemetry, lap times, and session data
- **Ergast API**: Championship standings and historical results
- **OpenF1 API**: Team radio recordings

## Caching

The server automatically caches FastF1 data in a `cache` directory to improve performance on repeated queries.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
