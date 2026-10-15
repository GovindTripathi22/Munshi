"""
Munshi: Autonomous AI Bookkeeper & GST Forensic Audit OS
Built with LangGraph, Double-Entry Ledger, Indian GST Rules, Audit Trail, and MCP Server.
"""

__version__ = "1.1.0"
__author__ = "Govind Tripathi"

from munshi.config import MunshiConfig, DEFAULT_CONFIG
from munshi.ledger.engine import LedgerEngine, DoubleEntryLedger
from munshi.graph import MunshiOrchestrator
from munshi.mcp_server import MunshiMCPServer

__all__ = [
    "MunshiConfig",
    "DEFAULT_CONFIG",
    "LedgerEngine",
    "DoubleEntryLedger",
    "MunshiOrchestrator",
    "MunshiMCPServer",
]
