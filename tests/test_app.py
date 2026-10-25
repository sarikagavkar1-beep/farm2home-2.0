from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash

from app import create_app
from models import (DeliverySlot, LoyaltyPoint, Order, OrderItem, Payment,
                    Product, Review, SlotCapacity, Subscription, User)
from services import process_due_subscriptions


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'farm2home-test.sqlite3'}",
        "SECRET_KEY": "test-only-session-secret",
        "SEED_DEMO_DATA": True,
        "SCHEDULER_ENABLED": False,
    })
    yield application
    application.extensions["farm2home_engine"].dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email="consumer@farm2home.test", password="Farm2Home123!"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["user"]


def make_test_image(image_format):
    stream = BytesIO()
    Image.new("RGB", (20, 16), (42, 132, 73)).save(stream, format=image_format)
    return stream.getvalue()


def test_health_manifest_and_sample_counts(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["success"] is True
    assert client.get("/healthz").get_json()["status"] == "ok"
    manifest = client.get("/manus-routes.json")
    assert manifest.status_code == 200
    assert "/track/:order_id" in [r["path"] for r in manifest.get_json()["routes"]]
    assert len(client.get("/api/categories").get_json()["data"]) == 8
    product_response = client.get("/api/products").get_json()
    assert len(product_response["data"]) == 25
    # These are read from the real API response by productCard/loadProducts.
    browser_product_fields = {"product_id", "product_name", "price", "unit",
        "available_quantity", "organic", "category_name", "farmer_name",
        "farmer_location", "rating", "review_count", "image_url"}
    assert browser_product_fields <= product_response["data"][0].keys()
    assert isinstance(product_response["data"][0]["rating"], (int, float))
    assert len(client.get("/api/farmers").get_json()["data"]) == 5
    assert len(client.get("/api/subscriptions/plans").get_json()["data"]) == 5


def test_authentication_validation_and_role_protection(client):
    bad_login = client.post("/api/auth/login", json={"email": "wrong@farm2home.test", "password": "incorrect"})
    assert bad_login.status_code == 401
    assert bad_login.get_json()["success"] is False
    assert client.get("/api/admin/dashboard").status_code == 401
    login(client)
    assert client.get("/api/admin/dashboard").status_code == 403
    weak = client.post("/api/auth/register", json={
        "full_name": "Test Person", "email": "invalid-email", "password": "short", "phone": "123", "role": "consumer"
    })
    assert weak.status_code == 400
    created = client.post("/api/auth/register", json={
        "full_name": "Fresh Customer", "email": "fresh.customer@farm2home.test",
        "password": "StrongPass123", "phone": "9000099991", "role": "consumer"
    })
    assert created.status_code == 201
    assert created.get_json()["data"]["user"]["role"] == "consumer"
    with Session(client.application.extensions["farm2home_engine"]) as db:
        saved = db.scalar(select(User).where(User.email == "fresh.customer@farm2home.test"))
        assert saved is not None
        assert saved.password_hash != "StrongPass123"
        assert check_password_hash(saved.password_hash, "StrongPass123")


def test_cart_checkout_transaction_and_delivery_tracking(client, app):
    user = login(client)
    products = client.get("/api/products?sort=price_asc").get_json()["data"]
    product = products[0]
    added = client.post("/api/cart/add", json={"product_id": product["product_id"], "quantity": 2})
    assert added.status_code == 200
    assert added.get_json()["data"]["item_count"] == 2
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slots = client.get(f"/api/delivery-slots?date={tomorrow}").get_json()["data"]
    order_response = client.post("/api/orders", json={
        "name": user["full_name"], "phone": user["phone"], "address": "12 Demo Lane",
        "city": "Mira Road", "pincode": "401107", "delivery_date": tomorrow,
        "slot_id": slots[0]["slot_id"], "payment_method": "demo_online", "use_points": False,
    })
    assert order_response.status_code == 201, order_response.get_json()
    order = order_response.get_json()["data"]
    assert order["order_status"] == "Placed"
    assert order["payment_status"] == "paid"
    assert len(order["items"]) == 1 and order["items"][0]["quantity"] == 2
    assert order["delivery"]["delivery_id"] is not None
    with Session(app.extensions["farm2home_engine"]) as db:
        saved_order = db.get(Order, order["order_id"])
        saved_product = db.get(Product, product["product_id"])
        assert saved_order is not None and saved_product is not None
        payment = db.scalar(select(Payment).where(Payment.order_id == saved_order.order_id))
        capacity = db.scalar(select(SlotCapacity).where(SlotCapacity.slot_id == saved_order.delivery_slot_id, SlotCapacity.service_date == saved_order.delivery_date))
        assert payment is not None and capacity is not None
        assert saved_product.available_quantity == product["available_quantity"] - 2
        assert payment.payment_status == "simulated_success"
        assert capacity.current_orders >= 1
    tracking = client.get(f"/api/delivery/{order['order_id']}")
    assert tracking.status_code == 200
    assert tracking.get_json()["data"]["route"]["customer"]["lat"]


def test_checkout_rejects_a_full_delivery_slot(client, app):
    with Session(app.extensions["farm2home_engine"]) as db:
        slot = db.scalar(select(DeliverySlot).where(DeliverySlot.slot_name == "Morning"))
        assert slot is not None
        slot.max_orders = 1
        db.commit()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for account, phone in (("consumer@farm2home.test", "9000000011"), ("consumer2@farm2home.test", "9000000012")):
        login(client, email=account)
        product = client.get("/api/products").get_json()["data"][0]
        client.post("/api/cart/add", json={"product_id": product["product_id"], "quantity": 1})
        slot = next(s for s in client.get(f"/api/delivery-slots?date={tomorrow}").get_json()["data"] if s["slot_name"] == "Morning")
        response = client.post("/api/orders", json={"name":"Demo Customer","phone":phone,
            "address":"12 Farm Road","city":"Mira Road","pincode":"401107",
            "delivery_date":tomorrow,"slot_id":slot["slot_id"],"payment_method":"cod"})
        if account.startswith("consumer@"):
            assert response.status_code == 201
            client.post("/api/auth/logout", json={})
        else:
            assert response.status_code == 400
            assert "full" in response.get_json()["message"].lower()
            assert client.get("/api/cart").get_json()["data"]["item_count"] == 1
            break


def test_subscription_controls_and_idempotent_due_renewal(app, client):
    login(client)
    with Session(app.extensions["farm2home_engine"]) as db:
        sub = db.get(Subscription, 1)
        assert sub is not None
        sub.next_delivery_date = date.today()
        sub.status = "active"
        db.commit()
        before = db.scalar(select(func.count(Order.order_id)))
        assert before is not None
        result = process_due_subscriptions(db, date.today())
        db.commit()
        assert len(result["created_order_ids"]) == 1
        again = process_due_subscriptions(db, date.today())
        db.commit()
        assert again["created_order_ids"] == []
        assert db.scalar(select(func.count(Order.order_id))) == before + 1
        renewed_sub = db.get(Subscription, 1)
        assert renewed_sub is not None and renewed_sub.next_delivery_date > date.today()
    assert client.put("/api/subscriptions/1/pause").status_code == 200
    assert client.put("/api/subscriptions/1/resume").status_code == 200
    assert client.delete("/api/subscriptions/1").status_code == 200


def test_verified_purchaser_review_and_notification_read(client, app):
    login(client)
    response = client.post("/api/reviews", json={"order_id": 1, "product_id": 2, "rating": 5, "comment": "Fresh and lovely"})
    assert response.status_code == 201, response.get_json()
    review_id = response.get_json()["data"]["review_id"]
    mine = client.get("/api/reviews/mine").get_json()["data"]
    assert any(review["review_id"] == review_id and review["product_id"] == 2 for review in mine)
    assert client.put(f"/api/reviews/{review_id}", json={"rating":4,"comment":"Still great"}).status_code == 200
    assert client.delete(f"/api/reviews/{review_id}").status_code == 200
    notifications = client.get("/api/notifications").get_json()["data"]
    assert notifications["unread_count"] >= 1
    notification_id = notifications["items"][0]["notification_id"]
    assert client.put(f"/api/notifications/{notification_id}/read").status_code == 200


def test_farmer_application_requires_admin_approval_then_product_create(client):
    registration = client.post("/api/auth/register", json={
        "full_name":"Sam Orchard","email":"sam.orchard@farm2home.test","password":"StrongPass123",
        "phone":"9000099992","role":"farmer","farm_name":"Sam's Demo Farm","farm_location":"Mira Road",
        "city":"Mira Road","pincode":"401107"
    })
    assert registration.status_code == 201
    farmer_user_id = registration.get_json()["data"]["user"]["user_id"]
    assert client.post("/api/products",json={"category_id":1,"product_name":"Blocked","price":12}).status_code == 403
    public_farms = client.get("/api/farmers").get_json()["data"]
    assert public_farms and "phone" not in public_farms[0]
    client.post("/api/auth/logout",json={})
    assert client.get("/api/admin/farmers").status_code == 401
    login(client,"admin@farm2home.test")
    farmers = client.get("/api/admin/farmers").get_json()["data"]
    new_farm = next(f for f in farmers if f["user"]["user_id"] == farmer_user_id)
    assert new_farm["verification_status"] == "pending"
    assert new_farm["user"]["phone"] == "9000099992"
    pending_card = next(f for f in client.get("/api/admin/dashboard").get_json()["data"]["pending_farmers"] if f["user"]["user_id"] == farmer_user_id)
    assert pending_card["user"]["phone"] == "9000099992"
    decision = client.put(f"/api/admin/farmers/{new_farm['farmer_id']}",json={"verification_status":"approved"})
    assert decision.status_code == 200
    client.post("/api/auth/logout",json={})
    login(client,"sam.orchard@farm2home.test","StrongPass123")
    categories = client.get("/api/categories").get_json()["data"]
    image_url = "https://images.example.test/sams-greens.jpg"
    created = client.post("/api/products",json={"category_id":categories[0]["category_id"],"product_name":"Sam's Greens","price":44,"unit":"bunch","available_quantity":8,"image_url":image_url})
    assert created.status_code == 201, created.get_json()
    product = created.get_json()["data"]
    assert product["image_url"] == image_url
    product_id = product["product_id"]
    invalid = client.put(f"/api/products/{product_id}",json={"image_url":"javascript:alert(1)"})
    assert invalid.status_code == 400
    assert client.get(f"/api/products/{product_id}").get_json()["data"]["image_url"] == image_url
    replacement_url = "https://images.example.test/sams-greens-fresh.webp"
    updated = client.put(f"/api/products/{product_id}",json={"image_url":replacement_url})
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["data"]["image_url"] == replacement_url


def test_farmer_product_form_uses_form_event_and_renders_images():
    source = (Path(__file__).resolve().parents[1] / "static/js/main.js").read_text()
    assert 'name="image_url" type="url"' in source
    assert 'name="product_image" type="file"' in source
    assert "const f=event.target" in source
    assert "String(fd.get('image_url')||'').trim()" in source
    assert "image_url:photo?'':" in source
    assert "safeImageUrl(product?.image_url)" in source
    assert "class=\"product-photo\"" in source
    assert "options.body instanceof FormData" in source
    assert "/products/${created.product_id}/image" in source
    assert 'data-action="product-image"' in source
    assert "<th>Mobile</th>" in source
    assert "phoneLink(f.user.phone)" in source
    assert 'href="tel:${phone}"' in source


def test_farmer_can_upload_replace_and_serve_product_photo(client, app):
    login(client, "farmer1@farm2home.test")
    product = client.get("/api/farmer/dashboard").get_json()["data"]["products"][0]
    product_id = product["product_id"]
    uploaded_urls = []
    try:
        first = client.post(f"/api/products/{product_id}/image", data={
            "product_image": (BytesIO(make_test_image("PNG")), "okra.png")
        }, content_type="multipart/form-data")
        assert first.status_code == 200, first.get_json()
        first_url = first.get_json()["data"]["image_url"]
        uploaded_urls.append(first_url)
        assert first_url.startswith("/static/uploads/")
        served = client.get(first_url)
        assert served.status_code == 200 and served.mimetype == "image/png"

        invalid = client.post(f"/api/products/{product_id}/image", data={
            "product_image": (BytesIO(b"not an image"), "not-image.png")
        }, content_type="multipart/form-data")
        assert invalid.status_code == 400

        too_large = client.post(f"/api/products/{product_id}/image", data={
            "product_image": (BytesIO(b"x" * (6 * 1024 * 1024)), "large.png")
        }, content_type="multipart/form-data")
        assert too_large.status_code == 413

        client.post("/api/auth/logout", json={})
        login(client)
        denied = client.post(f"/api/products/{product_id}/image", data={
            "product_image": (BytesIO(make_test_image("PNG")), "wrong-owner.png")
        }, content_type="multipart/form-data")
        assert denied.status_code == 403
        client.post("/api/auth/logout", json={})
        login(client, "farmer1@farm2home.test")

        replacement = client.post(f"/api/products/{product_id}/image", data={
            "product_image": (BytesIO(make_test_image("WEBP")), "okra.webp")
        }, content_type="multipart/form-data")
        assert replacement.status_code == 200, replacement.get_json()
        replacement_url = replacement.get_json()["data"]["image_url"]
        uploaded_urls.append(replacement_url)
        assert replacement_url.endswith(".webp") and replacement_url != first_url
        assert client.get(replacement_url).mimetype == "image/webp"
        old_path = Path(app.static_folder) / "uploads" / Path(first_url).name
        assert not old_path.exists()
    finally:
        for image_url in uploaded_urls:
            if image_url.startswith("/static/uploads/"):
                (Path(app.static_folder) / "uploads" / Path(image_url).name).unlink(missing_ok=True)


def test_product_search_and_sort(client):
    products = client.get("/api/products?q=tomato").get_json()["data"]
    assert products and all("tomato" in p["product_name"].lower() for p in products)
    sorted_products = client.get("/api/products?sort=price_asc").get_json()["data"]
    prices = [p["price"] for p in sorted_products]
    assert prices == sorted(prices)


def test_admin_management_categories_products_and_dashboard(client):
    login(client, "admin@farm2home.test")
    dashboard = client.get("/api/admin/dashboard").get_json()["data"]
    assert {"orders_chart", "revenue_chart", "subscription_chart", "category_chart", "delivery_chart"} <= dashboard.keys()
    assert dashboard["total_consumers"] >= 1
    assert len(dashboard["recent_farmers"]) == 5
    assert client.get("/api/admin/subscriptions").status_code == 200
    assert client.get("/api/admin/deliveries").status_code == 200

    categories = client.get("/api/admin/categories").get_json()["data"]
    assert len(categories) == 8
    created = client.post("/api/admin/categories", json={"category_name": "Seasonal Herbs", "description": "Local greens"})
    assert created.status_code == 201, created.get_json()
    category_id = created.get_json()["data"]["category_id"]
    assert client.post("/api/admin/categories", json={"category_name": "Seasonal Herbs"}).status_code == 409
    assert client.put(f"/api/admin/categories/{category_id}", json={"category_name": "Fresh Herbs"}).status_code == 200
    assert client.delete(f"/api/admin/categories/{category_id}").status_code == 200

    product = client.get("/api/admin/products").get_json()["data"][0]
    assert client.delete(f"/api/admin/categories/{product['category_id']}").status_code == 409
    paused = client.put(f"/api/products/{product['product_id']}", json={"status": "inactive"})
    assert paused.status_code == 200, paused.get_json()
    resumed = client.put(f"/api/products/{product['product_id']}", json={"status": "active"})
    assert resumed.status_code == 200, resumed.get_json()

    users = client.get("/api/admin/users").get_json()["data"]
    consumer = next(user for user in users if user["email"] == "consumer2@farm2home.test")
    assert client.put(f"/api/admin/users/{consumer['user_id']}/status", json={"is_active": False}).status_code == 200
    assert client.put(f"/api/admin/users/{consumer['user_id']}/status", json={"is_active": True}).status_code == 200


def test_review_listing_and_farmer_dashboard_subscription_metric(client):
    login(client)
    mine = client.get("/api/reviews/mine")
    assert mine.status_code == 200 and isinstance(mine.get_json()["data"], list)
    client.post("/api/auth/logout", json={})
    login(client, "farmer1@farm2home.test")
    dashboard = client.get("/api/farmer/dashboard")
    assert dashboard.status_code == 200, dashboard.get_json()
    data = dashboard.get_json()["data"]
    assert isinstance(data["active_subscriptions"], int)
    assert {"sales_chart", "product_chart", "products", "recent_orders"} <= data.keys()
    assert isinstance(data["subscriptions"], list)
    for subscription in data["subscriptions"]:
        assert {"subscription_id", "plan_name", "frequency", "next_delivery_date", "status", "city", "pincode", "delivery_slot", "items"} <= subscription.keys()


def test_consumer_dashboard_baskets_and_rewards_contract(client):
    login(client)
    dashboard = client.get("/api/consumer/dashboard").get_json()["data"]
    assert isinstance(dashboard["active_subscriptions"], int)
    assert isinstance(dashboard["next_delivery"], (str, type(None)))
    assert {"labels", "values"} <= dashboard["spending_chart"].keys()
    assert {"labels", "values"} <= dashboard["orders_chart"].keys()
    subscriptions = client.get("/api/subscriptions").get_json()["data"]
    assert isinstance(subscriptions, list)
    loyalty = client.get("/api/loyalty").get_json()["data"]
    assert isinstance(loyalty["points"], int) and isinstance(loyalty["history"], list)



def test_delivery_status_transitions_enforce_order_lifecycle(client):
    shopper = login(client)
    product = client.get("/api/products").get_json()["data"][0]
    assert client.post("/api/cart/add", json={"product_id": product["product_id"], "quantity": 1}).status_code == 200
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slot = client.get(f"/api/delivery-slots?date={tomorrow}").get_json()["data"][0]
    placed = client.post("/api/orders", json={
        "name": shopper["full_name"], "phone": shopper["phone"], "address": "12 Demo Lane",
        "city": "Mira Road", "pincode": "401107", "delivery_date": tomorrow,
        "slot_id": slot["slot_id"], "payment_method": "cod",
    })
    assert placed.status_code == 201, placed.get_json()
    order = placed.get_json()["data"]
    delivery_id = order["delivery"]["delivery_id"]

    client.post("/api/auth/logout", json={})
    login(client, email="admin@farm2home.test")
    direct_delivery = client.put(f"/api/delivery/{delivery_id}/status", json={"status": "Delivered"})
    assert direct_delivery.status_code == 409
    assert direct_delivery.get_json()["success"] is False
    assert client.get(f"/api/delivery/{order['order_id']}").get_json()["data"]["order"]["order_status"] == "Placed"

    for status in ("Confirmed", "Preparing"):
        response = client.put(f"/api/delivery/{delivery_id}/status", json={"status": status})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["data"]["order_status"] == status

    skipped = client.put(f"/api/delivery/{delivery_id}/status", json={"status": "Delivered"})
    assert skipped.status_code == 409
    assert client.get(f"/api/delivery/{order['order_id']}").get_json()["data"]["order"]["order_status"] == "Preparing"

    for status in ("Out for Delivery", "Delivered"):
        response = client.put(f"/api/delivery/{delivery_id}/status", json={"status": status})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["data"]["order_status"] == status

    closed = client.put(f"/api/delivery/{delivery_id}/status", json={"status": "Cancelled"})
    assert closed.status_code == 409
