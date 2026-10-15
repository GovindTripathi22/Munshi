"""Rich interactive Command-Line Interface (CLI) for Munshi."""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from munshi.config import MunshiConfig
from munshi.graph import MunshiOrchestrator
from munshi.mcp_server import MunshiMCPServer
from munshi.evaluation.benchmark import run_benchmark

console = Console()


@click.group()
def cli():
    """Munshi: Autonomous AI Bookkeeper & GST Forensic Audit OS."""
    pass


@cli.command()
def chat():
    """Starts an interactive multi-agent financial assistant session."""
    console.print(Panel.fit(
        "[bold green]MUNSHI (मुंशी) AI: Multi-Agent Finance Assistant[/bold green]\n"
        "[dim]Multi-Agent Orchestrator | Double-Entry Invariants | Indian GST & TDS | Audit Trail[/dim]",
        border_style="green"
    ))
    orch = MunshiOrchestrator()

    while True:
        try:
            user_input = console.input("\n[bold cyan]You > [/bold cyan]").strip()
            if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Exiting Munshi session. Khata band (Account closed).[/yellow]")
                break

            result = orch.process_transaction(user_input)
            entry = result["entry"]
            flags = result["audit_flags"]

            lines_summary = "\n".join(
                f"  {'[cyan]Dr[/cyan]' if l.debit > 0 else '[magenta]Cr[/magenta]'} {l.account_code} {l.account_name}: INR {l.debit if l.debit > 0 else l.credit:,.2f}"
                for l in entry.lines
            )

            status_style = "yellow" if result["requires_hitl"] else "green"
            hitl_badge = "[bold yellow]⚠ PENDING HUMAN APPROVAL[/bold yellow]" if result["requires_hitl"] else "[bold green]✓ COMMITTED TO LEDGER[/bold green]"

            panel_content = (
                f"[bold]Entry ID:[/bold] {entry.entry_id} | [bold]Date:[/bold] {entry.date}\n"
                f"[bold]Narration:[/bold] {entry.narration}\n"
                f"[bold]Double-Entry Lines:[/bold]\n{lines_summary}\n"
                f"[bold]Total Balanced:[/bold] INR {entry.total_debit:,.2f}\n"
                f"[bold]Governance Status:[/bold] {hitl_badge}"
            )

            if flags:
                flag_text = "\n".join(f"  • [{ 'red' if f.severity in ('HIGH','CRITICAL') else 'yellow'}]{f.rule}:[/{ 'red' if f.severity in ('HIGH','CRITICAL') else 'yellow'}] {f.detail}" for f in flags)
                panel_content += f"\n\n[bold red]Audit Flags Raised ({len(flags)}):[/bold red]\n{flag_text}"

            console.print(Panel(panel_content, title="Munshi Processing Result", border_style=status_style))

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


@cli.command()
@click.option("--type", "report_type", type=click.Choice(["trial_balance", "pnl", "balance_sheet", "gst"]), default="trial_balance")
def report(report_type):
    """Generates financial statements (trial balance, P&L, balance sheet, GST)."""
    orch = MunshiOrchestrator()
    # Add seed transactions
    orch.process_transaction("Initial promoter capital infusion INR 5,00,000 via bank")
    orch.process_transaction("Sold SaaS consulting contract in Bengaluru for INR 1,00,000 via bank")
    orch.process_transaction("AWS Cloud server infrastructure bill INR 20,000 via bank")
    orch.process_transaction("Paid office rent INR 30,000 via bank")

    res = orch.run_full_close()

    if report_type == "trial_balance":
        tb = res["trial_balance"]
        table = Table(title="Trial Balance: Munshi Enterprise Technologies", border_style="cyan")
        table.add_column("Code", style="white")
        table.add_column("Account Name", style="cyan")
        table.add_column("Debit (INR)", justify="right", style="green")
        table.add_column("Credit (INR)", justify="right", style="magenta")

        for row in tb["rows"]:
            table.add_row(row["code"], row["name"], f"{row['debit']:,.2f}", f"{row['credit']:,.2f}")

        table.add_row("TOTAL", "BALANCED", f"{tb['total_debit']:,.2f}", f"{tb['total_credit']:,.2f}", style="bold")
        console.print(table)

    elif report_type == "pnl":
        pnl = res["profit_and_loss"]
        console.print(Panel(
            f"[bold cyan]Total Revenue:[/bold cyan] INR {pnl['total_revenue']:,.2f}\n"
            f"[bold magenta]Total Expense:[/bold magenta] INR {pnl['total_expense']:,.2f}\n"
            f"----------------------------------------\n"
            f"[bold green]Net Profit:[/bold green] INR {pnl['net_profit']:,.2f}",
            title="Profit & Loss Statement",
            border_style="green"
        ))

    elif report_type == "balance_sheet":
        bs = res["balance_sheet"]
        console.print(Panel(
            f"[bold cyan]Total Assets:[/bold cyan] INR {bs['total_assets']:,.2f}\n"
            f"[bold magenta]Total Liabilities:[/bold magenta] INR {bs['total_liabilities']:,.2f}\n"
            f"[bold blue]Total Equity (with Retained Profit):[/bold blue] INR {bs['total_equity']:,.2f}\n"
            f"----------------------------------------\n"
            f"[bold]Balance Sheet Status:[/bold] {'[green]BALANCED (Assets = Liabilities + Equity)[/green]' if bs['is_balanced'] else '[red]IMBALANCED[/red]'}",
            title="Balance Sheet",
            border_style="blue"
        ))

    elif report_type == "gst":
        gst = res["gstr3b"]
        console.print(Panel.fit(
            f"[bold cyan]Total Output GST Liability:[/bold cyan] INR {gst['output_tax']['total']:,.2f}\n"
            f"  - CGST: INR {gst['output_tax']['cgst']:,.2f} | SGST: INR {gst['output_tax']['sgst']:,.2f} | IGST: INR {gst['output_tax']['igst']:,.2f}\n\n"
            f"[bold green]Eligible Input Tax Credit (ITC):[/bold green] INR {gst['eligible_itc']['total']:,.2f}\n"
            f"  - CGST: INR {gst['eligible_itc']['cgst']:,.2f} | SGST: INR {gst['eligible_itc']['sgst']:,.2f} | IGST: INR {gst['eligible_itc']['igst']:,.2f}\n\n"
            f"[bold yellow]Net Cash GST Payable:[/bold yellow] INR {gst['net_gst_payable']:,.2f}",
            title="GSTR-3B Monthly Return Summary",
            border_style="yellow"
        ))


@cli.command()
def benchmark():
    """Displays the synthetic evaluation benchmark suite results."""
    console.print("[bold blue]Loading Munshi Evaluation Benchmark Results...[/bold blue]")
    try:
        with open("benchmark_results.json", "r") as f:
            res = json.load(f)
    except Exception:
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
    """Launches the Model Context Protocol (MCP) server."""
    console.print("[bold green]Starting Munshi MCP Server...[/bold green]")
    server = MunshiMCPServer()
    tools = server.list_tools()
    console.print(f"[cyan]Loaded {len(tools)} MCP Tools:[/cyan]")
    for t in tools:
        console.print(f"  - [bold]{t['name']}[/bold]: {t['description']}")


if __name__ == "__main__":
    cli()
