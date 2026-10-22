# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from munshi.api import app

@pytest.fixture
def client():
    return TestClient(app)

def test_api_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "munshi"
    assert len(data["features"]) > 0

def test_api_workflow_run_bookkeeping(client):
    payload = {
        "prompt": "Purchased Dell laptops for INR 118000 including 18% GST",
        "thread_id": "test-api-thread-1",
    }
    response = client.post("/v1/workflows/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == "test-api-thread-1"
    assert data["status"] == "AWAITING_HITL_APPROVAL"  # > 50k requires HITL
    assert data["requires_hitl"] is True
    assert data["entry"] is not None
    assert data["entry"]["total_debit"] == 139240.0
    assert data["entry"]["total_credit"] == 139240.0
    assert data["entry"]["is_balanced"] is True

def test_api_hitl_approval(client):
    # First post high value entry
    thread_id = "test-api-hitl-thread"
    client.post("/v1/workflows/run", json={
        "prompt": "Purchased machinery for INR 150000 including 18% GST",
        "thread_id": thread_id,
    })

    # Now approve it
    approval_resp = client.post(f"/v1/workflows/{thread_id}/hitl", json={
        "approved": True,
        "reviewer_notes": "Approved by Finance Director",
    })
    assert approval_resp.status_code == 200
    appr_data = approval_resp.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["reviewer_notes"] == "Approved by Finance Director"
    assert appr_data["trial_balance"]["is_balanced"] is True

def test_api_ledger_and_gst_endpoints(client):
    thread_id = "test-api-reports"
    client.post("/v1/workflows/run", json={
        "prompt": "Consulting revenue received for INR 50000 with 18% GST",
        "thread_id": thread_id,
    })

    tb_resp = client.get(f"/v1/ledger/trial-balance?thread_id={thread_id}")
    assert tb_resp.status_code == 200
    assert tb_resp.json()["is_balanced"] is True

    pnl_resp = client.get(f"/v1/ledger/pnl?thread_id={thread_id}")
    assert pnl_resp.status_code == 200
    assert "revenues" in pnl_resp.json()

    gst_resp = client.get(f"/v1/gst/gstr3b?thread_id={thread_id}")
    assert gst_resp.status_code == 200
    assert "net_gst_payable" in gst_resp.json()

    audit_resp = client.get(f"/v1/audit/findings?thread_id={thread_id}")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["audit_chain_valid"] is True
