"""Offline HTTP journey: signed checkout -> full mock -> refund -> saved history.

Uses the real Stripe adapter with in-memory HTTP responses and original synthetic
exams. This verifies entitlement plumbing, not Stripe connectivity, deployed audio
or realistic IELTS content/difficulty.
"""
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import settings
from app.models.models import GeneratedPractice, StudyPassGrant, UserPractice
from app.routers import checkout
from app.services.stripe_test import StripeTestAdapter
from tests.test_checkout_http import auth, order, sandbox  # noqa: F401 (fixture)
from tests.test_full_mock_delivery import offline, original_exam  # noqa: F401 (fixture)
from tests.test_stripe_test_adapter import NOW, SECRET, StripeFixture, refund, signed


@pytest.mark.parametrize("skill,total", [("reading", 30), ("listening", 40)])
def test_signed_checkout_full_mock_and_refund_keep_saved_results(
        client, test_db, test_user, auth_token, sandbox, monkeypatch, skill, total):
    provider = StripeFixture()
    provider.session.update(status="open", payment_status="unpaid", payment_intent=None)

    def respond(request):
        if request.method == "POST":
            fields = parse_qs(request.content.decode())
            metadata = {name: fields[f"metadata[{name}]"][0]
                        for name in provider.session["metadata"]}
            provider.session.update(metadata=metadata, client_reference_id=metadata["order_id"])
            provider.payment["metadata"] = metadata
        return provider.respond(request)

    def seed():
        row = GeneratedPractice(skill=skill, topic="Original delivery fixture",
                                content=json.dumps(original_exam(skill)), is_validated=True)
        test_db.add(row)
        test_db.commit()
        return row.id

    def submit_body(practice_id):
        return {"practice_id": practice_id, "time_taken_seconds": 42,
                "sections": [{"section_number": section["section_number"],
                              "answers": {f"q_0_{i}": f"parcel{i + 1}" for i in range(10)}}
                             for section in original_exam(skill)["sections"]]}

    def webhook(event=None):
        raw, headers = signed(event)
        response = client.post("/api/checkout/webhook", content=raw, headers=headers)
        assert response.status_code == 200, response.text
        return response

    headers = auth(auth_token)
    daily = f"/api/generate/daily-{skill}"
    submit = f"/api/generate/submit-ai-{skill}-exam"
    history = f"/api/generate/recent-exams?skill={skill}"
    first = seed()
    assert test_user.role == "free"
    assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is False
    assert client.get(daily, headers=headers).json() == {"practices": []}
    assert client.post(submit, headers=headers, json=submit_body(first)).status_code == 402
    assert test_db.query(UserPractice).count() == 0

    monkeypatch.setattr(settings, "STRIPE_TEST_SECRET_KEY", "sk_test_not_a_real_key")
    monkeypatch.setattr(settings, "STRIPE_TEST_WEBHOOK_SECRET", SECRET)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        monkeypatch.setattr(checkout, "_adapter_factory", lambda **kwargs: StripeTestAdapter(
            **kwargs, http_client=transport, clock=lambda: NOW))
        created = order(client, auth_token)
        assert created.status_code == 200
        status_path = f'/api/checkout/orders/{created.json()["id"]}'
        assert client.get(status_path + "?success=true", headers=headers).json()["state"] == "pending"
        assert client.get(daily, headers=headers).json() == {"practices": []}
        assert test_db.query(StudyPassGrant).count() == 0

        provider.session.update(status="complete", payment_status="paid", payment_intent="pi_fixture")
        webhook()
        webhook()  # Duplicate delivery must not create another entitlement.
        assert test_db.query(StudyPassGrant).count() == 1
        assert client.get(status_path, headers=headers).json()["state"] == "fulfilled"
        assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is True
        assert [p["practice_db_id"] for p in client.get(daily, headers=headers).json()["practices"]] == [first]
        result = client.post(submit, headers=headers, json=submit_body(first))
        assert result.status_code == 200, result.text
        assert result.json()["overall"]["correct"] == total
        assert result.json()["overall"]["total"] == total
        saved_history = client.get(history, headers=headers).json()
        assert len(saved_history) == 1
        assert saved_history[0]["exercise"] == original_exam(skill)
        assert saved_history[0]["result"] == result.json()

        # An already opened but unfinished mock must also lose submission access.
        second = seed()
        assert [p["practice_db_id"] for p in client.get(daily, headers=headers).json()["practices"]] == [second]
        third = seed()  # Unassigned inventory must not be dealt after revocation.
        assert test_db.query(UserPractice).count() == 2

        provider.refunds = [refund(status="pending")]
        refund_event = {"object": "event", "id": "evt_pending_refund", "livemode": False,
                        "type": "refund.updated", "data": {"object": provider.refunds[0]}}
        webhook(refund_event)
        assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is True

        provider.refunds = [refund()]
        provider.charge["amount_refunded"] = 1900
        refund_event.update(id="evt_succeeded_refund", data={"object": provider.refunds[0]})
        webhook(refund_event)
        webhook(refund_event)
        assert client.get(status_path, headers=headers).json()["state"] == "refunded"
        assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is False
        assert client.get(daily, headers=headers).json() == {"practices": []}
        assert client.post(submit, headers=headers, json=submit_body(second)).status_code == 402
        assert client.post(submit, headers=headers, json=submit_body(third)).status_code == 402
        assert client.get(history, headers=headers).json() == saved_history
        test_db.expire_all()
        assert test_db.query(UserPractice).count() == 2
        assert test_db.query(UserPractice).filter_by(practice_id=second).one().submitted_at is None
        assert test_db.query(UserPractice).filter_by(practice_id=third).count() == 0
        assert test_db.query(StudyPassGrant).one().revoked_at is not None

        # Even a later authentic completion notification cannot resurrect it.
        completion, _ = signed()
        event = json.loads(completion)
        event["id"] = "evt_late_completion"
        webhook(event)
        assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is False
        assert client.get(history, headers=headers).json() == saved_history
