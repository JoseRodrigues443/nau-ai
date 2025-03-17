# Nau AI

![Nau AI Logo](logo.jpeg)

*Navigate the sea of complexity at your workplace*

Nau AI is an intelligent terminal tool for developers inspired by the Portuguese "Nau" - the iconic ships used during the Age of Discoveries that allowed explorers to navigate uncharted waters. Similarly, Nau AI helps developers navigate through the complexity of modern development environments, integrating with GitHub, Jira, Slack, and other services.

## Features

- **AI-driven analysis** of your development workflow
- **Local AI support** using Llama models
- **API integration** with Claude and ChatGPT
- **Extensible architecture** for adding new services
- **Unified interface** for all your development communications

## About the Name

"Nau" comes from Portuguese maritime history - these were the robust ships that enabled Portuguese explorers to navigate vast oceans during the Discoveries Era (15th-16th centuries). Just as these vessels helped sailors manage the complexity and challenges of ocean exploration, Nau AI helps developers navigate the sea of information and tasks in modern development environments.

## Requirements

- Python 3.8+
- pip packages:
  - `requests`
  - `llama-cpp-python` (for local AI)
  - `anthropic` (for Claude)
  - `openai` (for ChatGPT)
  - And other dependencies listed in requirements.txt

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/nau-ai.git
   cd nau-ai
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make the script executable:
   ```
   chmod +x nau.py
   ```

4. Run the setup wizard:
   ```
   ./nau.py --setup
   ```

## Configuration

Nau AI uses a configuration file located at `~/.nau/config.json`. The setup wizard will help you create this file, but you can also edit it manually.

Example configuration:

```json
{
  "ai": {
    "provider": "local",
    "model": "llama3",
    "local_model_path": "/path/to/llama/model.gguf"
  },
  "extensions": {
    "github": {
      "enabled": true,
      "config": {
        "token": "your-github-token",
        "repositories": [
          "owner/repo1",
          "owner/repo2"
        ]
      }
    },
    "jira": {
      "enabled": true,
      "config": {
        "url": "https://your-instance.atlassian.net",
        "username": "your-email@example.com",
        "api_token": "your-jira-api-token",
        "projects": [
          "PROJECT1",
          "PROJECT2"
        ]
      }
    },
    "slack": {
      "enabled": true,
      "config": {
        "token": "xoxp-your-slack-token",
        "team_id": "T0123456789",
        "channels": [
          "general",
          "development"
        ],
        "managers": [
          "U0123456789"
        ]
      }
    }
  }
}
```

## Usage

Run Nau AI to get a summary of your current development status:

```
./nau.py
```

This will:
1. Collect data from enabled extensions
2. Process the data using AI
3. Present a summary of important information

## Extensions

Nau AI uses an extension system to integrate with different services. Extensions are located in `~/.nau/extensions/`.

### Installing Extensions

Use the `--install-extension` option to create a new extension template:

```
./nau.py --install-extension gitlab
```

### Built-in Extensions

Nau AI comes with the following built-in extensions:

- **GitHub**: Pull requests, issues, and notifications
- **Jira**: Issues, sprints, and projects
- **Slack**: Messages, mentions, and important communications

### Creating Custom Extensions

Create a new Python file in the extensions directory with the following structure:

```python
def initialize(config):
    """Initialize the extension with the given configuration"""
    # Setup your extension here
    
def collect_data():
    """Collect data from your service"""
    # Collect and return data
    return {
        "items": [
            # Your data here
        ]
    }
```

## AI Integration

Nau AI supports three AI providers:

1. **Local**: Uses [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) to run Llama models locally
2. **Claude**: Uses Anthropic's Claude API
3. **OpenAI**: Uses OpenAI's API for ChatGPT

## Contributing

We welcome contributions to Nau AI! Feel free to submit pull requests or open issues to improve the tool.

## License

MIT