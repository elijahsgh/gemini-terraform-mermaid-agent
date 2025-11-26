from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.google import GoogleModel

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.google import GoogleProvider

import asyncio
import logfire
import logging
from logging import basicConfig, getLogger

from rich.markdown import Markdown
from rich.console import Console

from typing import Dict
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    JsonConfigSettingsSource,
)

class MCPValidationFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.enabled = True

    def filter(self, record):
        if not self.enabled:
            return True
        return "Failed to validate notification" not in record.getMessage()

class ServerConfig(BaseModel):
    url: str
    type: str
    prefix: str = ""

class Settings(BaseSettings):
    servers: Dict[str, ServerConfig]
    provider_url: str
    model_name: str
    gemini_api_key: str | None = None
    verbose_logging: bool = False
    instructions: str
    example_content: str
    readme_example: str
    model_config = SettingsConfigDict(json_file="settings.json")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
        )

async def configure_mcp_server(server_config: ServerConfig) -> MCPServerStreamableHTTP | MCPServerSSE:
    if server_config.type == 'sse':
        return MCPServerSSE(server_config.url)
    elif server_config.type == 'http':
        return MCPServerStreamableHTTP(server_config.url)
    else:
        raise ValueError(f"Unknown server type: {server_config.type}")

settings = Settings()

logfire.configure(
    send_to_logfire=False,
    console=logfire.ConsoleOptions(
        verbose=settings.verbose_logging,
    ),
)

logfire.instrument_pydantic_ai()
logfire.instrument_mcp()

validation_filter = MCPValidationFilter()
logfire_handler = logfire.LogfireLoggingHandler()
logfire_handler.addFilter(validation_filter)

basicConfig(handlers=[logfire_handler])
logger = getLogger(__name__)

console = Console()

async def main():
    mcp_servers = []
    for k in settings.servers:
        server_config = settings.servers[k]
        server = await configure_mcp_server(server_config)
        tools = await server.list_tools()
        tool_names = ", ".join([tool.name for tool in tools])
        logfire.info(f"Calling tool listing for {server_config.url}: {tool_names}")

        mcp_servers.append(server)

    model = GoogleModel(
        provider=GoogleProvider(
            api_key=settings.gemini_api_key,
        ),
        model_name=settings.model_name,
    )

    # Used for local testing with ollama
    # model = OpenAIChatModel(
    #     provider=OpenAIProvider(
    #         base_url=settings.provider_url,
    #     ),
    #     model_name=settings.model_name,
    # )

    with open(settings.instructions, 'r') as f:
        instructions_content = f.read()

    with open(settings.readme_example, 'r') as f:
        example_readme_content = f.read()

    system_prompt=f"""
You are a Terraform Documentation Expert.
Your task is to analyze the provided Terraform code and create a README.md file based on your analysis.

{instructions_content}

The README.md should look like:
{example_readme_content}
"""
    agent = Agent(
        model=model,
        mcp_servers=mcp_servers,
        name="Terraform Documentation Example",
        system_prompt=system_prompt,
    )

    logfire.info(system_prompt)

    with open(settings.example_content, 'r') as f:
        example_content = f.read()

    response = await agent.run(example_content)

    # Disable the validation filter after MCP usage
    validation_filter.enabled = False

    console.print(Markdown(response.output))

    with open('Generated_README.md', 'w') as f:
        f.write(response.output)

if __name__ == "__main__":
    asyncio.run(main())
