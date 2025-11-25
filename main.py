from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.google import GoogleModel

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.google import GoogleProvider

import asyncio
import logfire
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

logfire.configure(
    send_to_logfire=False,
    console=logfire.ConsoleOptions(
        verbose=True,
    ),
)

logfire.instrument_pydantic_ai()
logfire.instrument_mcp()

basicConfig(handlers=[logfire.LogfireLoggingHandler()])
logger = getLogger(__name__)

console = Console()

class ServerConfig(BaseModel):
    url: str
    type: str
    prefix: str = ""

class Settings(BaseSettings):
    servers: Dict[str, ServerConfig]
    provider_url: str
    model_name: str
    gemini_api_key: str

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

async def main():
    settings = Settings()

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

    agent = Agent(
        model=model,
        mcp_servers=mcp_servers,
        name="Terraform Documentation Example",
        system_prompt="""You are a Terraform Documentation Example.
Your task is to analyze the provided Terraform code and create a README.md file based on your analysis.

INSTRUCTIONS:
1. Do not use emojis.
2. Use the **terraform** tool to get the latest provider details for required providers.
3. Create an example terraform required_providers block using the version retrieved in step 2.
4. Create a ## Requirements section listing the provider resources and their latest versions.
5. Use the **mermaidchart** tool to generate a topdown Mermaid chart string of the Terraform resources.
6. There is a link included in the tool output from step 5. Use markdown to make it a link labelled [View at MermaidChart](<link>)

The README.md should look like:
# Module
## Required Providers
<required provider configuration>
## Variables
<variable configuration>
## Resources
<resource configuration>
## Output
<output configuration>
## Mermaid Chart
<mermaid chart>
"""
    )

    response = await agent.run("""
main.tf
```
terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "6.12.0"
    }
  }
}

provider "google" {
}

resource "google_cloud_run_service" "default" {
  name     = "cloudrun-srv"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "us-docker.pkg.dev/cloudrun/container/hello"
      }
    }

metadata {
annotations = {
"autoscaling.knative.dev/maxScale"      = "1000"
"run.googleapis.com/cloudsql-instances" = google_sql_database_instance.instance.connection_name
"run.googleapis.com/client-name"        = "terraform"
}
}
  }
  autogenerate_revision_name = true
}

resource "google_sql_database_instance" "instance" {
  name             = "cloudrun-sql"
  region           = "us-east1"
  database_version = "MYSQL_5_7"
  settings {
    tier = "db-f1-micro"
  }

  deletion_protection  = true
}
```
""")

    print(response)

    console.print(Markdown(response.output))

    with open('Generated_README.md', 'w') as f:
        f.write(response.output)

if __name__ == "__main__":
    asyncio.run(main())
