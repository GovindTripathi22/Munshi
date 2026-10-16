"""Rich interactive Command-Line Interface (CLI) for Munshi."""

import click
import json
from decimal import Decimal
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from munshi.config import MunshiConfig
from munshi.ledger.engine import DoubleEntryLedger
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.gst import GSTComputationAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.agents.reporter import ReportingAgent
from munshi.graph import create_munshi_graph
from munshi.agents.state import AgentState
from munshi.evaluation.benchmark import run_benchmark

console = Console()


@click.group()
def cli():
    """Munshi: Supervisor-Routed Multi-Agent Finance Assistant."""
    pass


@cli.command()
def chat():
    """Starts an interactive multi-agent chat session."""
    console.print(Panel.fit(
        "[bold green]Munshi: Multi-Agent Finance Assistant[/bold green]\n"
        "[dim]LangGraph Supervisor | Double-Entry Invariants | Indian GST | Audit Trail[/dim]",
        border_style="green"
    ))
    ledger = DoubleEntryLedger(MunshiConfig().db_path)
    graph = create_munshi_graph(ledger=ledger)

    while True:
        try:
            user_input = console.input("\n[bold cyan]You > [/bold cyan]").strip()
            if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Exiting Munshi session. Khata band (Account closed).[/yellow]")
                break

            initial_state = AgentState(query=user_input)
            result = graph.invoke(initial_state)

            if result.get("report_output"):
                md = result["report_output"].get("markdown", "")
                console.print(Markdown(md))
            elif result.get("categorization"):
                cat = result["categorization"]
                console.print(Panel(
                    f"[bold]Account:[/bold] {cat['account_code']} - {cat['account_name']}\n"
                    f"[bold]Confidence:[/bold] {cat['confidence'] * 100:.1f}%\n"
                    f"[bold]Posted to Ledger:[/bold] {result.get('ledger_posted', False)}",
                    title="Bookkeeper Output",
                    border_style="cyan"
                ))
            elif result.get("audit_findings"):
                findings = result["audit_findings"]
                console.print(Panel(
                    f"[bold]Anomalies Detected:[/bold] {findings.get('anomalies_detected', 0)}\n"
                    f"[bold]Risk Score:[/bold] {findings.get('risk_score', 0)}/100\n"
                    f"[bold]Status:[/bold] {findings.get('status', 'CLEAN')}",
                    title="Auditor Output",
                    border_style="red" if findings.get("anomalies_detected", 0) > 0 else "green"
                ))
            else:
                for msg in result.get("messages", []):
                    console.print(f"[dim]{msg}[/dim]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


@cli.command()
@click.option("--type", "report_type", type=click.Choice(["trial_balance", "pnl", "gst"]), default="trial_balance")
def report(report_type):
    """Generates financial statements (trial balance, P&L, GST)."""
    ledger = DoubleEntryLedger(MunshiConfig().db_path)
    # Add seed transactions for demonstration
    bookkeeper = BookkeeperAgent()
    tx1 = bookkeeper.create_journal_transaction(
        tx_id="TXN-001",
        date="2026-10-15",
        description="Enterprise Consulting Contract",
        amount=Decimal("100000.00"),
        is_sale=True,
    )
    ledger.post_transaction(tx1, force_approval=True)

    tx2 = bookkeeper.create_journal_transaction(
        tx_id="TXN-002",
        date="2026-10-15",
        description="AWS Cloud Server Hosting",
        amount=Decimal("20000.00"),
        is_sale=False,
    )
    ledger.post_transaction(tx2, force_approval=True)

    rep = ReportingAgent(ledger)
    if report_type == "trial_balance":
        console.print(Markdown(rep.generate_trial_balance_report()))
    elif report_type == "pnl":
        console.print(Markdown(rep.generate_profit_loss_report()))
    elif report_type == "gst":
        gst_data = rep.generate_gst_summary()
        console.print(Panel.fit(
            f"[bold]Company:[/bold] {gst_data['company']}\n"
            f"[bold]GSTIN:[/bold] {gst_data['gstin']}\n\n"
            f"[bold cyan]Output Tax (Liabilities):[/bold cyan] INR {gst_data['output_liability']['total']}\n"
            f"[bold green]Input Tax Credit (ITC):[/bold green] INR {gst_data['input_tax_credit']['total']}\n"
            f"[bold yellow]Net Cash Tax Payable:[/bold yellow] INR {gst_data['net_tax_payable_cash']}",
            title="GSTR-3B Tax Return Summary",
            border_style="yellow"
        ))


@cli.command()
def benchmark():
    """Runs the synthetic evaluation benchmark suite."""
    console.print("[bold blue]Running Munshi Evaluation Benchmark...[/bold blue]")
    res = run_benchmark()
    
    table = Table(title="Benchmark Evaluation Results", border_style="blue")
    table.add_column("Evaluation Track", style="cyan")
    table.add_column("Metric", style="white")
    table.add_column("Result", style="green bold")

    table.add_row("Bookkeeping Categorization", "Accuracy", f"{res['categorization']['accuracy_percent']}%")
    table.add_row("Bank Reconciliation", "Precision", f"{res['reconciliation']['precision_percent']}%")
    table.add_row("Bank Reconciliation", "Recall", f"{res['reconciliation']['recall_percent']}%")
    table.add_row("Bank Reconciliation", "Statement Clearing Rate", f"{res['reconciliation']['match_rate_percent']}%")
    table.add_row("Anomaly & Fraud Detection", "Precision", f"{res['anomaly_detection']['precision_percent']}%")
    table.add_row("Anomaly & Fraud Detection", "Recall", f"{res['anomaly_detection']['recall_percent']}%")
    table.add_row("Anomaly & Fraud Detection", "F1-Score", f"{res['anomaly_detection']['f1_score']}%")

    console.print(table)


@cli.command()
def mcp():
    """Launches the Model Context Protocol (MCP) server over standard I/O."""
    console.print("[bold green]Starting Munshi MCP Server...[/bold green]")
    from munshi.mcp_server import mcp as server_instance
    server_instance.run()


if __name__ == "__main__":
    cli()
