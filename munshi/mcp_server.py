"""Model Context Protocol (MCP) Server for Munshi."""

import json
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional

# Supports both MCP 2.x (MCPServer) and MCP 1.x (FastMCP)
try:
    from mcp.server.mcpserver import MCPServer
    server_class = MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP
    server_class = FastMCP

from munshi.config import MunshiConfig
from munshi.ledger.engine import DoubleEntryLedger
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.gst import GSTComputationAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.agents.reporter import ReportingAgent

# Instantiate shared global components
config = MunshiConfig()
ledger = DoubleEntryLedger(config.db_path)
bookkeeper = BookkeeperAgent(config)
gst_agent = GSTComputationAgent(config)
reconciler = ReconciliationAgent(config)
auditor = AuditorAgent(config)
reporter = ReportingAgent(ledger, config)

mcp = server_class("munshi-finance-assistant")


@mcp.tool()
def record_transaction(
    description: str,
    amount: float,
    is_sale: bool = False,
    counterparty_gstin: Optional[str] = None,
    payment_method: str = "BANK",
    counterparty: str = "",
) -> str:
    """
    Categorizes and records a transaction into the double-entry ledger.
    Enforces Debits == Credits and applies appropriate Indian GST slabs.
    """
    tx_id = f"TXN-{len(ledger.transactions) + 1:04d}"
    tx = bookkeeper.create_journal_transaction(
        tx_id=tx_id,
        date=date.today().isoformat(),
        description=description,
        amount=Decimal(str(amount)),
        is_sale=is_sale,
        counterparty_gstin=counterparty_gstin,
        payment_method=payment_method,
        counterparty=counterparty,
    )
    posted = ledger.post_transaction(tx, actor="mcp:client")
    
    return json.dumps({
        "transaction_id": posted.id,
        "status": posted.status.value,
        "total_debit": str(posted.total_debits()),
        "total_credit": str(posted.total_credits()),
        "is_balanced": posted.is_balanced(),
        "requires_human_approval": posted.requires_approval,
        "items": [item.model_dump() for item in posted.items],
    }, indent=2, default=str)


@mcp.tool()
def compute_gst(
    taxable_value: float,
    rate_percent: float,
    counterparty_gstin: Optional[str] = None,
) -> str:
    """
    Computes exact CGST, SGST, IGST breakdown, determining inter-state vs intra-state
    supply based on buyer and seller GSTIN state prefixes.
    """
    rate = Decimal(str(rate_percent))
    val = Decimal(str(taxable_value))
    calc = gst_agent.compute_gst(
        taxable_value=val,
        rate=rate,
        counterparty_gstin=counterparty_gstin,
    )
    return json.dumps(calc, indent=2)


@mcp.tool()
def reconcile_statement(
    bank_lines_json: str,
    invoices_json: str,
) -> str:
    """
    Reconciles a list of bank statement transactions against internal ledger invoices.
    Returns matched transactions, match rate %, and flagged discrepancies.
    """
    bank_lines = json.loads(bank_lines_json)
    invoices = json.loads(invoices_json)
    result = reconciler.reconcile(bank_lines, invoices)
    return json.dumps(result, indent=2)


@mcp.tool()
def run_financial_audit(transactions_json: str) -> str:
    """
    Audits a batch of financial transactions for duplicate invoices,
    invalid tax rates, arithmetic discrepancies, and un-balanced debit/credit entries.
    """
    transactions = json.loads(transactions_json)
    result = auditor.audit_batch(transactions)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_trial_balance() -> str:
    """Returns the current Trial Balance verifying Debits == Credits across all ledger accounts."""
    tb = ledger.get_trial_balance()
    return json.dumps(tb, indent=2)


@mcp.tool()
def get_profit_and_loss() -> str:
    """Returns the current Profit and Loss Statement with Total Revenues, Expenses, and Net Profit."""
    pnl = ledger.get_profit_and_loss()
    return json.dumps(pnl, indent=2)


@mcp.tool()
def get_gst_summary() -> str:
    """Returns the GSTR-3B monthly return tax summary including Output Tax, ITC, and Net Cash Payable."""
    summary = reporter.generate_gst_summary()
    return json.dumps(summary, indent=2)


if __name__ == "__main__":
    mcp.run()
