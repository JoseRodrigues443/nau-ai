#!/usr/bin/env python3
"""
DevAssist - AI-powered terminal tool for developers
Integrates with GitHub, Jira, Slack, and other services to provide a unified interface.
"""

import os
import sys
import argparse
import json
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import subprocess
import importlib.util
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("devassist")

# Configuration paths
CONFIG_DIR = Path.home() / ".devassist"
CONFIG_FILE = CONFIG_DIR / "config.json"
EXTENSIONS_DIR = CONFIG_DIR / "extensions"

@dataclass
class AIConfig:
    """Configuration for AI providers"""
    provider: str  # "local", "claude", "openai"
    model: str
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    local_model_path: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIConfig':
        return cls(
            provider=data.get("provider", "local"),
            model=data.get("model", "llama3"),
            api_key=data.get("api_key"),
            api_url=data.get("api_url"),
            local_model_path=data.get("local_model_path")
        )

@dataclass
class Extension:
    """Extension metadata"""
    name: str
    enabled: bool
    config: Dict[str, Any]
    module: Any = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Extension':
        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            config=data.get("config", {})
        )

class DevAssist:
    """Main application class"""
    
    def __init__(self):
        self.config = {}
        self.ai_config = None
        self.extensions = {}
        self.initialized = False
        
    def initialize(self):
        """Initialize the application"""
        if self.initialized:
            return
        
        # Create config directory if it doesn't exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.load_config()
        
        # Load AI provider
        self.load_ai_provider()
        
        # Load extensions
        self.load_extensions()
        
        self.initialized = True
        logger.info("DevAssist initialized")
    
    def load_config(self):
        """Load configuration from file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {CONFIG_FILE}")
            except Exception as e:
                logger.error(f"Error loading configuration: {e}")
                self.config = self.create_default_config()
        else:
            logger.info("Configuration file not found, creating default")
            self.config = self.create_default_config()
            self.save_config()
        
        # Initialize AI configuration
        self.ai_config = AIConfig.from_dict(self.config.get("ai", {}))
        
    def create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        return {
            "ai": {
                "provider": "local",
                "model": "llama3",
                "local_model_path": str(Path.home() / ".cache" / "devassist" / "models" / "llama3")
            },
            "extensions": {
                "github": {
                    "enabled": True,
                    "config": {
                        "token": "",
                        "repositories": []
                    }
                },
                "jira": {
                    "enabled": True,
                    "config": {
                        "url": "",
                        "username": "",
                        "api_token": "",
                        "projects": []
                    }
                },
                "slack": {
                    "enabled": True,
                    "config": {
                        "token": "",
                        "channels": []
                    }
                }
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def load_ai_provider(self):
        """Load AI provider module"""
        provider = self.ai_config.provider
        
        if provider == "local":
            try:
                # Check if llama-cpp-python is installed
                import llama_cpp
                logger.info("Using local Llama model")
            except ImportError:
                logger.error("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
                sys.exit(1)
        elif provider == "claude":
            try:
                import anthropic
                logger.info("Using Claude API")
            except ImportError:
                logger.error("anthropic package not installed. Install with: pip install anthropic")
                sys.exit(1)
        elif provider == "openai":
            try:
                import openai
                logger.info("Using OpenAI API")
            except ImportError:
                logger.error("openai package not installed. Install with: pip install openai")
                sys.exit(1)
        else:
            logger.error(f"Unknown AI provider: {provider}")
            sys.exit(1)
    
    def load_extensions(self):
        """Load all enabled extensions"""
        extensions_config = self.config.get("extensions", {})
        
        for name, config in extensions_config.items():
            ext_config = Extension.from_dict({"name": name, **config})
            
            if not ext_config.enabled:
                logger.info(f"Extension {name} is disabled, skipping")
                continue
            
            # Check for built-in extensions first
            builtin_path = Path(__file__).parent / "extensions" / f"{name}.py"
            user_path = EXTENSIONS_DIR / f"{name}.py"
            
            if builtin_path.exists():
                self._load_extension_module(ext_config, builtin_path)
            elif user_path.exists():
                self._load_extension_module(ext_config, user_path)
            else:
                logger.warning(f"Extension {name} not found")
                continue
            
            self.extensions[name] = ext_config
    
    def _load_extension_module(self, extension: Extension, path: Path):
        """Load extension module from file"""
        try:
            spec = importlib.util.spec_from_file_location(f"devassist.extensions.{extension.name}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "initialize"):
                module.initialize(extension.config)
            
            extension.module = module
            logger.info(f"Loaded extension: {extension.name}")
        except Exception as e:
            logger.error(f"Error loading extension {extension.name}: {e}")
    
    def query_ai(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Query the AI model with given prompt and context"""
        provider = self.ai_config.provider
        
        # Format the prompt with context
        formatted_prompt = self._format_prompt(prompt, context)
        
        if provider == "local":
            return self._query_local_llama(formatted_prompt)
        elif provider == "claude":
            return self._query_claude(formatted_prompt)
        elif provider == "openai":
            return self._query_openai(formatted_prompt)
        else:
            logger.error(f"Unknown AI provider: {provider}")
            return "Error: Unable to query AI model"
    
    def _format_prompt(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Format the prompt with context"""
        if not context:
            return prompt
            
        # Create a formatted context string
        context_str = "Context:\n"
        for source, data in context.items():
            context_str += f"=== {source} ===\n"
            context_str += json.dumps(data, indent=2) + "\n\n"
        
        return f"{context_str}\nTask: {prompt}\n\nResponse:"
    
    def _query_local_llama(self, prompt: str) -> str:
        """Query local Llama model"""
        try:
            from llama_cpp import Llama
            
            model_path = self.ai_config.local_model_path
            if not model_path or not Path(model_path).exists():
                return "Error: Local model path not configured or model file not found"
            
            llm = Llama(model_path=model_path)
            response = llm(prompt, max_tokens=1024, temperature=0.7)
            
            return response["choices"][0]["text"]
        except Exception as e:
            logger.error(f"Error querying local model: {e}")
            return f"Error querying local model: {str(e)}"
    
    def _query_claude(self, prompt: str) -> str:
        """Query Claude API"""
        try:
            import anthropic
            
            api_key = self.ai_config.api_key
            if not api_key:
                return "Error: Claude API key not configured"
            
            client = anthropic.Anthropic(api_key=api_key)
            model = self.ai_config.model or "claude-3-7-sonnet-20250219"
            
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error querying Claude API: {e}")
            return f"Error querying Claude API: {str(e)}"
    
    def _query_openai(self, prompt: str) -> str:
        """Query OpenAI API"""
        try:
            import openai
            
            api_key = self.ai_config.api_key
            if not api_key:
                return "Error: OpenAI API key not configured"
            
            openai.api_key = api_key
            model = self.ai_config.model or "gpt-4"
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error querying OpenAI API: {e}")
            return f"Error querying OpenAI API: {str(e)}"
    
    def collect_data(self) -> Dict[str, Any]:
        """Collect data from all enabled extensions"""
        data = {}
        
        for name, extension in self.extensions.items():
            if not extension.enabled or not extension.module:
                continue
                
            try:
                if hasattr(extension.module, "collect_data"):
                    extension_data = extension.module.collect_data()
                    if extension_data:
                        data[name] = extension_data
            except Exception as e:
                logger.error(f"Error collecting data from {name}: {e}")
        
        return data
    
    def process_data(self, data: Dict[str, Any]) -> str:
        """Process collected data with AI to generate a summary"""
        if not data:
            return "No data collected from extensions."
        
        prompt = """You are an AI assistant for developers. Analyze the following data from different developer tools and provide a concise summary focusing on:
1. Important tasks and their priorities
2. Pending code reviews that need attention
3. Messages that require responses
4. Any blocking issues that should be addressed immediately

Please format the output in a clear, readable way with sections for each category."""
        
        response = self.query_ai(prompt, context=data)
        return response
    
    def run(self):
        """Run the main application"""
        self.initialize()
        
        # Collect data from all extensions
        data = self.collect_data()
        
        # Process data with AI
        summary = self.process_data(data)
        
        # Print summary
        print("\n" + "="*80)
        print(" DEVELOPER ASSISTANT SUMMARY ")
        print("="*80 + "\n")
        print(summary)
        print("\n" + "="*80)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AI-powered terminal tool for developers")
    parser.add_argument("--config", help="Show current configuration", action="store_true")
    parser.add_argument("--setup", help="Run setup wizard", action="store_true")
    parser.add_argument("--install-extension", help="Install an extension", metavar="NAME")
    
    args = parser.parse_args()
    
    app = DevAssist()
    
    if args.config:
        app.initialize()
        print(json.dumps(app.config, indent=2))
    elif args.setup:
        setup_wizard(app)
    elif args.install_extension:
        install_extension(app, args.install_extension)
    else:
        app.run()

def setup_wizard(app: DevAssist):
    """Run setup wizard"""
    app.initialize()
    
    print("DevAssist Setup Wizard")
    print("======================")
    
    # AI Provider
    print("\nAI Provider Configuration:")
    providers = {
        "1": ("local", "Local Llama model"),
        "2": ("claude", "Claude API"),
        "3": ("openai", "OpenAI API"),
    }
    
    for key, (provider, desc) in providers.items():
        print(f"{key}. {desc}")
    
    choice = input(f"Select AI provider (1-3) [{app.ai_config.provider}]: ").strip()
    if choice in providers:
        provider, _ = providers[choice]
        app.config["ai"]["provider"] = provider
    
    if app.config["ai"]["provider"] == "local":
        path = input(f"Local model path [{app.config['ai'].get('local_model_path', '')}]: ").strip()
        if path:
            app.config["ai"]["local_model_path"] = path
    else:
        api_key = input(f"API key (leave empty to keep current): ").strip()
        if api_key:
            app.config["ai"]["api_key"] = api_key
        
        model = input(f"Model name [{app.config['ai'].get('model', '')}]: ").strip()
        if model:
            app.config["ai"]["model"] = model
    
    # Extension Configuration
    for name, ext_config in app.config.get("extensions", {}).items():
        print(f"\nConfigure {name.capitalize()} Extension:")
        
        enabled = input(f"Enable {name}? (y/n) [{'y' if ext_config.get('enabled', True) else 'n'}]: ").strip().lower()
        if enabled:
            app.config["extensions"][name]["enabled"] = enabled == 'y'
        
        if not app.config["extensions"][name]["enabled"]:
            continue
        
        for key in ext_config.get("config", {}):
            current = ext_config["config"].get(key, "")
            if key.lower() in ("token", "password", "api_token"):
                prompt = f"{key} (leave empty to keep current): "
            else:
                prompt = f"{key} [{current}]: "
            
            value = input(prompt).strip()
            if value:
                app.config["extensions"][name]["config"][key] = value
    
    # Save configuration
    app.save_config()
    print("\nConfiguration saved successfully!")

def install_extension(app: DevAssist, extension_name: str):
    """Install an extension"""
    app.initialize()
    
    print(f"Installing extension: {extension_name}")
    
    # Here you could implement downloading from a repository
    # For now, just create a template file
    
    extension_file = EXTENSIONS_DIR / f"{extension_name}.py"
    
    if extension_file.exists():
        print(f"Extension {extension_name} already exists")
        return
    
    template = """#!/usr/bin/env python3
    \"\"\"
    DevAssist Extension: {name}
    \"\"\"

    import logging
    from typing import Dict, Any

    logger = logging.getLogger("devassist.extensions.{name}")

    def initialize(config: Dict[str, Any]):
        \"\"\"Initialize the extension with the given configuration\"\"\"
        logger.info("Initializing {name} extension")
        # TODO: Implement initialization
        
    def collect_data() -> Dict[str, Any]:
        \"\"\"Collect data from the service\"\"\"
        logger.info("Collecting data from {name}")
        # TODO: Implement data collection
        
        # Example:
        return {{
            "items": [
                # Your data here
            ]
        }}
    """
    
    with open(extension_file, 'w') as f:
        f.write(template.format(name=extension_name))
    
    print(f"Extension template created at {extension_file}")
    print("Edit this file to implement your extension functionality")
    
    # Add to config if not exists
    if extension_name not in app.config.get("extensions", {}):
        if "extensions" not in app.config:
            app.config["extensions"] = {}
            
        app.config["extensions"][extension_name] = {
            "enabled": True,
            "config": {}
        }
        app.save_config()
        print(f"Added {extension_name} to configuration")

if __name__ == "__main__":
    main()