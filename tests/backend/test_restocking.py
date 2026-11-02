"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingEndpoints:
    """Test suite for restocking order endpoints."""

    def _forecast(self, client, sku):
        """Look up a demand forecast record by SKU."""
        forecasts = client.get("/api/demand").json()
        return next(f for f in forecasts if f["item_sku"] == sku)

    def test_demand_forecasts_include_cost_and_lead_time(self, client):
        """Test that forecasts expose unit cost and lead time for restocking."""
        data = client.get("/api/demand").json()
        assert len(data) > 0

        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_create_restocking_order(self, client):
        """Test submitting a valid restocking order."""
        widget = self._forecast(client, "WDG-001")
        filter_ = self._forecast(client, "FLT-405")
        payload = {
            "items": [
                {"item_sku": "WDG-001", "quantity": 10},
                {"item_sku": "FLT-405", "quantity": 20},
            ],
            "budget": 5000,
        }

        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert len(order["items"]) == 2

        expected_total = 10 * widget["unit_cost"] + 20 * filter_["unit_cost"]
        assert abs(order["total_cost"] - expected_total) < 0.01

        # Order lead time is driven by the slowest item
        assert order["lead_time_days"] == max(widget["lead_time_days"], filter_["lead_time_days"])
        assert "T" in order["submitted_date"]
        assert "T" in order["expected_delivery"]

    def test_restocking_order_uses_server_prices(self, client):
        """Test that unit cost comes from server data, not the request."""
        widget = self._forecast(client, "WDG-001")
        payload = {
            "items": [{"item_sku": "WDG-001", "quantity": 1, "unit_cost": 0.01}],
            "budget": 1000,
        }

        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201
        assert abs(response.json()["total_cost"] - widget["unit_cost"]) < 0.01

    def test_get_restocking_orders_includes_submitted(self, client):
        """Test that a submitted order appears in the list, newest first."""
        before = len(client.get("/api/restocking/orders").json())

        created = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "GSK-203", "quantity": 5}], "budget": 1000},
        ).json()

        data = client.get("/api/restocking/orders").json()
        assert len(data) == before + 1
        assert data[0]["id"] == created["id"]

    def test_restocking_order_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "MTR-304", "quantity": 100}], "budget": 100},
        )
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

    def test_restocking_order_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"items": [], "budget": 1000})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_restocking_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "NOPE-999", "quantity": 1}], "budget": 1000},
        )
        assert response.status_code == 400
        assert "unknown sku" in response.json()["detail"].lower()

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_restocking_order_non_positive_quantity(self, client, quantity):
        """Test that non-positive quantities fail validation."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "WDG-001", "quantity": quantity}], "budget": 1000},
        )
        assert response.status_code == 422
