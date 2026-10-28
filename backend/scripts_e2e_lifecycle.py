"""
End-to-end lifecycle check against a running backend (default http://localhost:8000).

    python backend/scripts_e2e_lifecycle.py --base http://localhost:8000 --email you@corp.com --password '...'

Flow: customer+contact -> quote -> submit -> (approve if routed) -> PDF -> download -> AI -> email -> accept
      -> dashboard -> webhook delivery -> CSV import.  Creates clearly-labelled "E2E" records.
"""
import argparse
import json
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

received = []


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        received.append((self.headers.get("X-CPQ-Event"), self.headers.get("X-CPQ-Signature"), body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {extra}" if extra else ""))
    if not cond:
        check.failed += 1


check.failed = 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    a = ap.parse_args()
    api = a.base + "/api/v1"

    srv = HTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    hook_url = f"http://127.0.0.1:{srv.server_port}/hook"

    c = httpx.Client(timeout=60)
    r = c.post(f"{api}/auth/login", json={"email": a.email, "password": a.password})
    check("login", r.status_code == 200, r.text[:120])
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    tag = uuid.uuid4().hex[:6]
    r = c.post(f"{api}/customers/", headers=h, json={"customer_number": f"E2E-{tag}", "legal_name": f"E2E Verify Co {tag}", "status": "ACTIVE"})
    check("create customer", r.status_code == 201, r.text[:150])
    cust = r.json()
    r = c.post(f"{api}/customers/{cust['id']}/contacts", headers=h, json={"first_name": "Erin", "last_name": "Buyer", "email": "erin.buyer@example.com", "is_primary": True})
    check("create contact", r.status_code == 201, r.text[:150])

    prods = c.get(f"{api}/products", headers=h, params={"limit": 50}).json()
    prod = next((p for p in prods if p["is_active"] and float(p["base_price"]) > 0), None)
    check("have an active product", prod is not None)

    # webhook
    r = c.put(f"{api}/integrations/webhooks", headers=h, json={"endpoint_url": hook_url, "events": ["quote.submitted", "quote.approved", "quote.accepted"], "enabled": True})
    check("save webhook", r.status_code == 200, r.text[:150])
    secret = r.json()["secret_key"]
    r = c.post(f"{api}/integrations/webhooks/test", headers=h)
    check("webhook test delivered", r.status_code == 200 and r.json()["success"], r.text[:150])

    r = c.post(f"{api}/quotes/", headers=h, json={"customer_id": cust["id"], "title": f"E2E proposal {tag}", "items": [{"product_id": prod["id"], "quantity": 3, "discount_percentage": "2"}]})
    check("create quote", r.status_code == 201, r.text[:200])
    q = r.json()
    r = c.post(f"{api}/quotes/{q['id']}/submit", headers=h)
    check("submit quote", r.status_code == 200, r.text[:200])
    q = r.json()
    print("   status after submit:", q["status"])
    if q["status"] == "SUBMITTED":
        pend = [p for p in c.get(f"{api}/approvals/pending", headers=h).json() if p["quote_id"] == q["id"]]
        for p in pend:
            rr = c.post(f"{api}/approvals/requests/{p['id']}/decide", headers=h, json={"status": "APPROVED", "comments": "e2e"})
            check(f"approve request {p['id']}", rr.status_code == 200, rr.text[:150])
        q = c.get(f"{api}/quotes/{q['id']}", headers=h).json()
    check("quote approved", q["status"] == "APPROVED", q["status"])

    r = c.post(f"{api}/documents/generate", headers=h, json={"quote_id": q["id"]})
    check("generate PDF", r.status_code == 201, r.text[:200])
    doc = r.json()
    r = c.get(f"{api}/documents/{doc['id']}/download", headers=h)
    check("download PDF", r.status_code == 200 and r.content[:4] == b"%PDF", f"{len(r.content)} bytes")

    for path, body in [("customer-summary", {"customer_id": cust["id"]}), ("quote-summary", {"quote_id": q["id"]}),
                       ("draft-email", {"quote_id": q["id"]}), ("recommendations", {"customer_id": cust["id"]})]:
        r = c.post(f"{api}/ai/{path}", headers=h, json=body)
        check(f"AI {path}", r.status_code == 200, (r.json().get("source", "") if r.status_code == 200 else r.text[:150]))
        if path == "draft-email" and r.status_code == 200:
            draft = r.json()
            check("draft addressed to contact", draft["recipient"] == "erin.buyer@example.com", str(draft["recipient"]))

    r = c.post(f"{api}/emails/send", headers=h, json={"quote_id": q["id"], "recipient": "erin.buyer@example.com", "subject": draft["subject"], "body": draft["body"]})
    check("email attempt logged", r.status_code == 201, r.text[:200])
    print("   email status:", r.json().get("status"), r.json().get("error_message"))

    r = c.post(f"{api}/quotes/{q['id']}/accept", headers=h)
    check("accept quote", r.status_code == 200 and r.json()["status"] == "ACCEPTED", r.text[:150])

    d = c.get(f"{api}/analytics/dashboard", headers=h).json()
    check("dashboard shows won revenue", d["won_revenue"] > 0, str(d["won_revenue"]))

    time.sleep(0.5)
    events = [e[0] for e in received]
    print("   webhook events received:", events)
    check("webhook quote.accepted received", "quote.accepted" in events)
    import hashlib, hmac
    ev = next((e for e in received if e[0] == "quote.accepted"), None)
    if ev:
        good = "sha256=" + hmac.new(secret.encode(), ev[2], hashlib.sha256).hexdigest()
        check("webhook signature valid", ev[1] == good)
    c.delete(f"{api}/integrations/webhooks", headers=h)

    csv_bytes = f"Part Number,Product Name,List Price,Billing\nE2E-{tag}-A,E2E Imported A,10.50,NRC\nE2E-{tag}-A,Dup,5,NRC\n,No sku,5,NRC\n".encode()
    files = {"file": ("e2e.csv", csv_bytes, "text/csv")}
    r = c.post(f"{api}/integrations/import/preview", headers=h, files=files, data={"import_type": "catalog"})
    check("import preview", r.status_code == 200 and len(r.json()["suggested_mappings"]) >= 3, r.text[:200])
    maps = r.json()["suggested_mappings"]
    r = c.post(f"{api}/integrations/import/execute", headers=h, files={"file": ("e2e.csv", csv_bytes, "text/csv")}, data={"import_type": "catalog", "mappings": json.dumps(maps)})
    check("import execute (1 ok, 2 rejected)", r.status_code == 200 and r.json()["records_imported"] == 1 and r.json()["records_failed"] == 2, r.text[:300])

    r = c.get(f"{api}/integrations/salesforce/status", headers=h)
    check("salesforce status (not connected)", r.status_code == 200 and r.json()["connected"] is False, r.text[:150])
    r = c.post(f"{api}/integrations/salesforce/sync-quote/{q['id']}", headers=h)
    check("sync without connection is refused", r.status_code == 422, r.text[:150])

    # ── Tax (scoped to a throw-away country so other quotes are unaffected) ─────────────────────
    country = f"E2Eland-{tag}"
    r = c.post(f"{api}/customers/{cust['id']}/addresses", headers=h, json={"line1": "1 Test St", "city": "Testville", "state": "TS", "postal_code": "00001", "country": country, "is_primary": True})
    check("create address", r.status_code == 201, r.text[:150])
    r = c.post(f"{api}/tax-rates/", headers=h, json={"name": f"E2E VAT {tag}", "country": country, "rate_percent": "7.5"})
    check("create tax rate", r.status_code == 201, r.text[:150])
    tax_id = r.json()["id"]
    r = c.post(f"{api}/quotes/", headers=h, json={"customer_id": cust["id"], "title": f"E2E taxed {tag}", "items": [{"product_id": prod["id"], "quantity": 2, "discount_percentage": "0"}]})
    tq = r.json()
    expected_tax = round(float(tq["subtotal"]) * 0.075, 2)
    check("tax applied to quote", abs(float(tq["tax_amount"]) - expected_tax) < 0.011 and tq["tax_label"] == f"E2E VAT {tag}", f"tax={tq['tax_amount']} expected={expected_tax}")
    check("total includes tax", abs(float(tq["total_amount"]) - (float(tq["subtotal"]) + expected_tax)) < 0.011)

    # ── Margin approval policy ──────────────────────────────────────────────────────────────────
    r = c.post(f"{api}/approvals/policies", headers=h, json={"name": f"E2E margin floor {tag}", "policy_type": "MARGIN", "margin_threshold": 99, "role_required": "Executive"})
    check("create MARGIN policy", r.status_code == 201, r.text[:150])
    pol_id = r.json()["id"]
    r = c.post(f"{api}/quotes/{tq['id']}/submit", headers=h)
    check("margin policy routes quote to approval", r.status_code == 200 and r.json()["status"] == "SUBMITTED", r.text[:150] if r.status_code != 200 else r.json()["status"])
    pend = [p for p in c.get(f"{api}/approvals/pending", headers=h).json() if p["quote_id"] == tq["id"]]
    check("pending request created", len(pend) >= 1)
    brief = c.get(f"{api}/ai/deal-insights/{tq['id']}", headers=h)
    check("AI deal insights", brief.status_code == 200 and "narrative" in brief.json(), brief.text[:150])
    for p in pend:
        c.post(f"{api}/approvals/requests/{p['id']}/decide", headers=h, json={"status": "APPROVED", "comments": "e2e"})
    check("deactivate policy", c.delete(f"{api}/approvals/policies/{pol_id}", headers=h).status_code == 204)
    tq = c.get(f"{api}/quotes/{tq['id']}", headers=h).json()
    check("taxed quote approved", tq["status"] == "APPROVED", tq["status"])

    # ── Customer share link, public accept, order ───────────────────────────────────────────────
    c.post(f"{api}/documents/generate", headers=h, json={"quote_id": tq["id"]})
    r = c.post(f"{api}/quotes/{tq['id']}/share", headers=h)
    check("create share link", r.status_code == 200 and r.json()["token"], r.text[:150])
    token = r.json()["token"]
    pub = httpx.Client(timeout=30)  # no auth header
    r = pub.get(f"{api}/public/proposals/{token}")
    check("public proposal view (no auth)", r.status_code == 200 and r.json()["can_respond"] is True and "margin" not in r.text.lower(), r.text[:150])
    check("public PDF", pub.get(f"{api}/public/proposals/{token}/pdf").content[:4] == b"%PDF")
    check("accept needs a name", pub.post(f"{api}/public/proposals/{token}/accept", json={"name": ""}).status_code == 422)
    r = pub.post(f"{api}/public/proposals/{token}/accept", json={"name": "Erin Buyer", "note": "Looks good"})
    check("customer accepts online", r.status_code == 200 and r.json()["status"] == "ACCEPTED" and r.json()["responded_by"] == "Erin Buyer", r.text[:150])
    check("second response refused", pub.post(f"{api}/public/proposals/{token}/decline", json={"name": "Erin Buyer"}).status_code == 422)
    check("bad token 404", pub.get(f"{api}/public/proposals/not-a-token").status_code == 404)

    r = c.post(f"{api}/orders/from-quote/{tq['id']}", headers=h)
    check("create order from accepted quote", r.status_code == 201 and r.json()["order_number"].startswith("SO-"), r.text[:200])
    order = r.json()
    check("order total matches quote incl. tax", abs(float(order["total_amount"]) - float(tq["total_amount"])) < 0.001)
    check("duplicate order refused", c.post(f"{api}/orders/from-quote/{tq['id']}", headers=h).status_code == 422)
    check("order PENDING->FULFILLED refused", c.post(f"{api}/orders/{order['id']}/status", headers=h, json={"status": "FULFILLED"}).status_code == 422)
    check("order confirmed", c.post(f"{api}/orders/{order['id']}/status", headers=h, json={"status": "CONFIRMED"}).json()["status"] == "CONFIRMED")
    c.delete(f"{api}/tax-rates/{tax_id}", headers=h)

    # ── AI-native layer ─────────────────────────────────────────────────────────────────────────
    words = " ".join(prod["name"].split()[:3])
    r = c.post(f"{api}/ai/quote-from-text", headers=h, json={"prompt": f"Create a quote for E2E Verify Co {tag}: 4 {words} with 5% discount, valid 20 days"})
    check("NL quote parses", r.status_code == 200, r.text[:200])
    nl = r.json()
    print("   NL source:", nl["source"], "| customer:", nl["customer_name"], "| lines:", [(l["query"], l["quantity"], l["matched"] and l["matched"]["sku"]) for l in nl["lines"]], nl["warnings"])
    check("NL resolves customer from the database", nl["customer_id"] == cust["id"])
    check("NL resolves product from the database", bool(nl["lines"]) and nl["lines"][0]["matched"] is not None and nl["lines"][0]["quantity"] == 4)
    r = c.post(f"{api}/ai/quote-from-text", headers=h, json={"prompt": f"Create a quote for E2E Verify Co {tag}: 4 {words} with 5% discount", "create": True})
    check("NL creates draft quote", r.status_code == 200 and r.json()["created_quote_id"], r.text[:200])
    nq = c.get(f"{api}/quotes/{r.json()['created_quote_id']}", headers=h).json()
    check("NL quote has priced line with discount", nq["status"] == "DRAFT" and len(nq["items"]) == 1 and float(nq["items"][0]["discount_percentage"]) == 5.0, str(nq["items"][:1])[:150])
    r = c.post(f"{api}/ai/quote-from-text", headers=h, json={"prompt": "quote for Nonexistent Nobody Ltd: 3 flux capacitors"})
    check("NL never invents products or customers", r.status_code == 200 and r.json()["customer_id"] is None and r.json()["lines"][0]["matched"] is None, r.text[:200])
    r = c.post(f"{api}/ai/ask", headers=h, json={"question": "What is my open pipeline and how many approvals are pending?"})
    check("copilot ask", r.status_code == 200 and r.json()["answer"], r.text[:200])
    print("   ask source:", r.json()["source"], "|", r.json()["answer"][:140])
    print("   AI status:", c.get(f"{api}/ai/status", headers=h).json())

    print("\nFAILED:" if check.failed else "\nALL CHECKS PASSED", check.failed or "")
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
