from backend.app.domains.ai.nlquote import regex_extract


def test_extracts_customer_quantities_discount_and_validity():
    r = regex_extract("Create a quote for Acme Corp: 10 Dell Latitude 7440, 50 cloud subscriptions with 8% discount, valid 45 days")
    assert r["customer"] == "Acme Corp"
    assert r["valid_days"] == 45
    assert [(i["query"], i["quantity"], i["discount_percentage"]) for i in r["items"]] == [
        ("Dell Latitude 7440", 10, 8.0),
        ("cloud subscriptions", 50, 8.0),
    ]


def test_customer_names_may_contain_digits():
    r = regex_extract("quote for E2E Verify Co 5e82b: 4 laptops")
    assert r["customer"] == "E2E Verify Co 5e82b"
    assert r["items"][0]["quantity"] == 4


def test_x_multiplier_and_default_quantity():
    r = regex_extract("quote for Globex with 5 x Enterprise Cloud Cluster and implementation service")
    assert [(i["query"], i["quantity"]) for i in r["items"]] == [("Enterprise Cloud Cluster", 5), ("implementation service", 1)]


def test_sku_only_request():
    r = regex_extract("10 DEV-LAP-001 for Horizon Financial")
    assert r["customer"] == "Horizon Financial"
    assert r["items"][0] == {"query": "DEV-LAP-001", "quantity": 10, "discount_percentage": 0.0}


def test_discount_is_capped_at_100():
    assert regex_extract("quote for X: 1 thing with 250% off")["items"][0]["discount_percentage"] == 100.0
