# tests/test_mcp_server.py
from munshi.mcp_server import MunshiMCPServer

def test_mcp_server_tools():
    mcp = MunshiMCPServer()
    tools = mcp.list_tools()
    assert len(tools) == 6
    res = mcp.call_tool("post_transaction", {"text": "Sold SaaS subscription in Bengaluru for ₹50,000"})
    assert res["total_debit"] == 59000.0
