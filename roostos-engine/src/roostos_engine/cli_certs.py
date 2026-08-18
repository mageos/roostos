"""CLI command definitions for RoostOS Certificate Management."""

import sys
import json
import click
from typing import List, Optional

from roostos_engine.cert_manager import CertificateManager

def register_certs_commands(main_group: click.Group, call_dbus_method_fn, run_async_fn):
    @main_group.group(name="certs")
    def certs_group():
        """Manage system, service, and plugin X.509 certificates."""
        pass

    @certs_group.command(name="status")
    @click.option("--session", is_flag=True, help="Query session bus instead of system bus")
    def certs_status(session):
        """Displays the status of Root CA, server cert, services, and plugins."""
        async def run():
            status_json = await call_dbus_method_fn("GetCertificateStatus", session=session)
            status = json.loads(status_json)
            
            click.echo("=== RoostOS Certificate Status ===")
            root = status.get("root_ca", {})
            click.echo(f"Root CA: {'VALID' if root.get('valid') else 'INVALID'}")
            click.echo(f"  Issuer: {root.get('issuer')}")
            click.echo(f"  Expires: {root.get('expires_at')}")

            server = status.get("server_cert")
            if server:
                click.echo(f"\nServer TLS Cert:")
                click.echo(f"  Common Name: {server.get('cn')}")
                click.echo(f"  Expires: {server.get('expires_at')}")
            else:
                click.echo("\nServer TLS Cert: Not generated yet.")

            services = status.get("services", [])
            click.echo(f"\nService Certificates ({len(services)}):")
            if services:
                for s in services:
                    click.echo(f"  • {s.get('service_id')} (CN: {s.get('subject_cn')} | Scopes: {', '.join(s.get('scopes', []))})")
            else:
                click.echo("  None issued.")

            plugins = status.get("plugins", [])
            click.echo(f"\nPlugin Certificates ({len(plugins)}):")
            if plugins:
                for p in plugins:
                    click.echo(f"  • {p.get('plugin_id')} (CN: {p.get('subject_cn')} | Scopes: {', '.join(p.get('scopes', []))})")
            else:
                click.echo("  None issued.")

        run_async_fn(run())

    @certs_group.command(name="init")
    @click.option("--cert-dir", default="/etc/roostos/certs", help="Path to certs directory")
    def certs_init(cert_dir):
        """Initializes the Root CA and default server certificate locally."""
        try:
            mgr = CertificateManager(cert_dir=cert_dir)
            mgr.ensure_root_ca()
            mgr.issue_server_cert()
            click.echo(f"✓ Certificate Authority and Server TLS certificate initialized at {cert_dir}.")
        except Exception as e:
            click.echo(f"✗ Failed to initialize certificates: {e}", err=True)
            sys.exit(1)

    @certs_group.command(name="issue-service")
    @click.argument("service_name")
    @click.option("--scopes", default="", help="Comma-separated scopes (e.g. 'timeguard:sync,devices:read')")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def issue_service(service_name, scopes, session):
        """Issues an X.509 client certificate for a system service."""
        async def run():
            scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
            res_json = await call_dbus_method_fn(
                "IssueServiceCertificate", service_name, json.dumps(scope_list), session=session
            )
            res = json.loads(res_json)
            if "error" in res:
                click.echo(f"✗ Failed to issue service cert: {res['error']}", err=True)
                sys.exit(1)
            click.echo(f"✓ Successfully issued certificate for service '{service_name}' with scopes: {scope_list}")

        run_async_fn(run())

    @certs_group.command(name="issue-plugin")
    @click.argument("plugin_id")
    @click.option("--scopes", default="", help="Comma-separated scopes (e.g. 'dns:manage,network:read')")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def issue_plugin(plugin_id, scopes, session):
        """Issues an X.509 client certificate for a plugin."""
        async def run():
            scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
            res_json = await call_dbus_method_fn(
                "IssuePluginCertificate", plugin_id, json.dumps(scope_list), session=session
            )
            res = json.loads(res_json)
            if "error" in res:
                click.echo(f"✗ Failed to issue plugin cert: {res['error']}", err=True)
                sys.exit(1)
            click.echo(f"✓ Successfully issued certificate for plugin '{plugin_id}' with scopes: {scope_list}")

        run_async_fn(run())

    @certs_group.command(name="renew-server")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def renew_server(session):
        """Renews the HTTPS server TLS certificate."""
        async def run():
            res_json = await call_dbus_method_fn("RenewServerCertificate", session=session)
            res = json.loads(res_json)
            if res.get("status") == "success":
                click.echo("✓ Server TLS certificate renewed successfully.")
            else:
                click.echo(f"✗ Server certificate renewal failed: {res.get('error')}", err=True)
                sys.exit(1)

        run_async_fn(run())
