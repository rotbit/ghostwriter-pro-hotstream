# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GhostWriter Pro HotStream is a plugin-based multi-platform data scraping framework built with Python and Playwright. It supports both immediate searches and scheduled data collection from platforms like Twitter, Medium, 知乎, and 掘金.

## Development Commands

### Setup & Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers  
playwright install

# Install in development mode
pip install -e .
```

### Code Quality & Testing
```bash
# Format code
black hotstream/
isort hotstream/

# Lint code
flake8 hotstream/

# Type checking
mypy hotstream/

# Run tests
pytest tests/
pytest --asyncio-mode=auto tests/
```

### CLI Usage
```bash
# Start framework daemon
python -m hotstream.cli start

# Immediate search
python -m hotstream.cli search twitter "AI,机器学习" --limit 50

# List supported platforms
python -m hotstream.cli list-platforms

# Add scheduled task
python -m hotstream.cli add-task task_id platform "keywords" --schedule "0 9 * * *"

# Show framework info
python -m hotstream.cli info
```

## Architecture Overview

### Core Components
- **HotStreamFramework**: Main orchestrator in `hotstream/core/framework.py`
- **PluginManager**: Plugin discovery and lifecycle management in `hotstream/core/plugin_manager.py`
- **TaskScheduler**: Cron-based scheduling in `hotstream/core/scheduler.py`  
- **DataProcessor**: Data pipeline management in `hotstream/core/data_processor.py`
- **ConfigManager**: YAML/JSON configuration in `hotstream/config/config_manager.py`

### Plugin Architecture
The framework uses a three-tier plugin system:

1. **Platform Adapters** (`hotstream/plugins/platforms/`): Implement `PlatformAdapter` interface for specific platforms
2. **Data Extractors** (`hotstream/plugins/extractors/`): Implement `DataExtractor` interface for custom data processing  
3. **Storage Adapters** (`hotstream/plugins/storages/`): Implement `StorageAdapter` interface for storage backends

All plugins inherit from abstract base classes defined in `hotstream/core/interfaces.py`.

### Plugin Discovery Process
- Plugins are automatically discovered by scanning directories in `hotstream/plugins/`
- Uses Python introspection to find classes implementing the required interfaces
- Plugin instances are cached and managed by the PluginManager

## Configuration Management

### Configuration Files
- Primary config: `configs/hotstream.yaml`
- Supports both YAML and JSON formats
- Config discovery order:
  1. Current directory: `hotstream.{yaml,yml,json}`
  2. Config directory: `configs/hotstream.*`
  3. User directory: `~/.hotstream/config.*`

### Configuration Structure
```yaml
framework:
  debug: false
  log_level: "INFO"

platforms:
  twitter:
    enabled: true
    rate_limit:
      requests_per_minute: 100

storage:
  default_type: "json"
  output_dir: "output"

crawler:
  timeout: 30
  retry_count: 3
```

## Key Development Patterns

### Async Programming
- All core operations use async/await
- Plugin interfaces are async-based
- Proper resource cleanup with context managers

### Data Models
- Use Pydantic models for data validation (see `DataItem`, `TaskConfig`, `SearchOptions`)
- Type hints throughout the codebase
- Structured error handling with custom exceptions

### Plugin Development
When creating new plugins:

1. **Platform Adapter**:
   ```python
   class MyPlatformAdapter(PlatformAdapter):
       platform_name = "myplatform"
       
       async def authenticate(self, credentials): ...
       async def search(self, keywords, options): ...
       async def get_rate_limit(self): ...
       async def cleanup(self): ...
   ```

2. **Storage Adapter**:
   ```python
   class MyStorageAdapter(StorageAdapter):
       async def save(self, items): ...
       async def query(self, filters): ...
       async def close(self): ...
   ```

### Rate Limiting & Security
- All platform adapters must implement rate limiting
- Use the `RateLimitInfo` model to track API limits
- Respect robots.txt and platform terms of service
- Implement proper delay mechanisms between requests

## Testing Guidelines

### Test Structure
- Tests should be placed in `tests/` directory
- Use pytest with asyncio mode for async tests
- Mock external dependencies (browsers, APIs)

### Example Test Pattern
```python
import pytest
from hotstream.core.framework import HotStreamFramework

@pytest.mark.asyncio
async def test_framework_initialization():
    framework = HotStreamFramework()
    assert await framework.initialize()
    await framework.stop()
```

## Troubleshooting

### Common Issues
- **Plugin not loading**: Check that plugin class inherits from correct interface and implements all required methods
- **Playwright errors**: Ensure browsers are installed with `playwright install`
- **Config not found**: Verify config file exists in expected locations
- **Async errors**: Ensure all async functions are properly awaited

### Debugging
- Set `framework.debug: true` in config for verbose logging
- Use `--log-level DEBUG` for detailed output
- Check `logs/hotstream.log` for error details

## Security Considerations

- Never commit credentials or API keys
- Use environment variables for sensitive configuration
- Implement proper proxy rotation for large-scale scraping
- Respect platform rate limits and terms of service
- Enable `security.encrypt_credentials` in production