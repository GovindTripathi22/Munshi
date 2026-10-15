"""
Munshi: Multi-Agent Finance Assistant
Built with LangGraph, Double-Entry Ledger, Indian GST Rules, Audit Trail, and MCP Server.
"""

__version__ = "1.0.0"
__author__ = "Govind Tripathi"

from munshi.config import MunshiConfig
from munshi.ledger.engine import DoubleEntryLedger
from munshi.graph import create_munshi_graph

__all__ = ["MunshiConfig", "DoubleEntryLedger", "create_munshi_graph"]
