#!/usr/bin/env python
import argparse
import os
import sys
from dataclasses import dataclass

from otrs_mcp.server import mcp

VALID_TRANSPORTS = {"stdio", "sse", "streamable-http"}
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000


@dataclass
class RuntimeOptions:
    transport: str
    host: str
    port: int


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OTRS MCP server runtime options")
    parser.add_argument(
        "--transport",
        choices=sorted(VALID_TRANSPORTS),
        help="Transport protocol to expose (default: stdio)",
    )
    parser.add_argument(
        "--host",
        help="Interface/IP for HTTP transports (default: 127.0.0.1 or MCP_* env)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port for HTTP transports (default: 8000 or MCP_* env)",
    )
    return parser.parse_args(argv)


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _parse_port(value: int | str | None, *, default: int = DEFAULT_HTTP_PORT) -> int:
    if value is None:
        return default
    try:
        port = int(value)
    except (TypeError, ValueError):
        print(f"[WARN] Invalid MCP port '{value}', falling back to {default}", file=sys.stderr)
        return default
    if not (0 < port < 65536):
        print(f"[WARN] MCP port '{port}' out of range, falling back to {default}", file=sys.stderr)
        return default
    return port


def resolve_runtime_options(args: argparse.Namespace) -> RuntimeOptions:
    env_transport = os.getenv("MCP_TRANSPORT")
    transport = args.transport or env_transport or "stdio"
    if transport not in VALID_TRANSPORTS:
        print(
            f"[WARN] Unsupported MCP transport '{transport}', falling back to 'stdio'",
            file=sys.stderr,
        )
        transport = "stdio"

    host = args.host or _first_env("MCP_HTTP_HOST", "MCP_SERVER_HOST", "MCP_HOST") or DEFAULT_HTTP_HOST
    port_source = args.port if args.port is not None else _first_env(
        "MCP_HTTP_PORT",
        "MCP_SERVER_PORT",
        "MCP_PORT",
    )
    port = _parse_port(port_source)

    return RuntimeOptions(transport=transport, host=host, port=port)


def apply_runtime_settings(options: RuntimeOptions) -> None:
    mcp.settings.host = options.host
    mcp.settings.port = options.port


def setup_environment(options: RuntimeOptions) -> bool:
    """Setup and validate environment configuration"""
    print("[CONFIG] OTRS MCP Server Configuration:")

    required_vars = ["OTRS_BASE_URL", "OTRS_USERNAME", "OTRS_PASSWORD"]
    missing_vars: list[str] = []

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            display_value = "*" * len(value) if "PASSWORD" in var else value
            print(f"  {var}: {display_value}")

    if missing_vars:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        print("\n[INFO] Set these environment variables:")
        print("  export OTRS_BASE_URL='https://your-otrs-server/otrs/nph-genericinterface.pl/Webservice/TestInterface'")
        print("  export OTRS_USERNAME='your-username'")
        print("  export OTRS_PASSWORD='your-password'")
        print("  export OTRS_VERIFY_SSL='false'  # Optional, for self-signed certificates")
        return False

    optional_vars = [
        "OTRS_VERIFY_SSL",
        "OTRS_DEFAULT_QUEUE",
        "OTRS_DEFAULT_STATE",
        "OTRS_DEFAULT_PRIORITY",
    ]
    for var in optional_vars:
        value = os.getenv(var, "default")
        print(f"  {var}: {value}")

    print("\n[CONFIG] MCP Runtime Settings:")
    print(f"  MCP_TRANSPORT: {options.transport}")
    print(f"  MCP_HOST: {options.host}")
    print(f"  MCP_PORT: {options.port}")
    if options.transport == "stdio":
        print("  (host/port affect HTTP transports only)")

    return True


def run_server(argv: list[str] | None = None):
    """Main entry point for the OTRS MCP Server"""
    args = parse_cli_args(argv)
    runtime_options = resolve_runtime_options(args)

    if not setup_environment(runtime_options):
        sys.exit(1)

    apply_runtime_settings(runtime_options)

    print("\n[START] Starting OTRS MCP Server...")
    print(f"[MODE] Running server with '{runtime_options.transport}' transport...")
    if runtime_options.transport != "stdio":
        print(f"[LISTEN] Interface {runtime_options.host}:{runtime_options.port}")
    print(
        "[OPS] Available operations: SessionCreate, TicketCreate, TicketGet, TicketSearch, "
        "TicketUpdate, TicketHistoryGet, ConfigItemGet, ConfigItemSearch"
    )

    mcp.run(transport=runtime_options.transport)

if __name__ == "__main__":
    run_server()