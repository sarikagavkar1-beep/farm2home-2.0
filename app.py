"""Farm2Home Flask application entry point."""
from __future__ import annotations
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from pathlib import Path
import os
from flask import Flask, jsonify, render_template, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from werkzeug.security import generate_password_hash
from sqlalchemy import select
from config import Config
from db import Base, close_session, create_schema, get_session, init_database, session_factory
from models import (Cart, CartItem, Category, Delivery, DeliverySlot, Farmer,
                    LoyaltyPoint, Notification, Order, OrderItem, Payment,
                    Product, Review, SlotCapacity, Subscription,
                    SubscriptionItem, SubscriptionPlan, User)
from api import api

ROOT = Path(__file__).resolve().parent
_scheduler = None


def _seed_demo_data(app):
    """Insert demo rows once; never overwrite data on an ordinary app restart."""
    maker = session_factory(app)
    with maker() as db:
        if db.scalar(select(User.user_id).limit(1)):
            return
        categories_data = [
            ("Vegetables", "Seasonal staples picked close to home."),
            ("Fruits", "Bright, seasonal fruit from local growers."),
            ("Leafy Vegetables", "Tender greens harvested in small batches."),
            ("Grains", "Everyday grains from trusted farms."),
            ("Pulses", "Wholesome pantry staples."),
            ("Organic Produce", "Produce grown with organic practices."),
            ("Dairy", "Fresh dairy from local producers."),
            ("Farm Products", "Small-batch produce and farm goods."),
        ]
        categories = {}
        for name, desc in categories_data:
            category = Category(category_name=name, description=desc)
            db.add(category); db.flush(); categories[name] = category
        localities = ["Mira Road", "Bhayandar East", "Bhayandar West", "Kashimira", "Uttan"]
        demo_pw = "Farm2Home123!"
        admin = User(full_name="Farm2Home Admin", email="admin@farm2home.test",
            password_hash=generate_password_hash(demo_pw), phone="9000000001", role="admin",
            address="Demo Admin Office", city="Mira Road", pincode="401107")
        db.add(admin); db.flush(); db.add(LoyaltyPoint(user_id=admin.user_id, points=320))
        farmer_specs = [
            ("Green Valley Farm", "Mira Road", "Seasonal vegetables grown with care near the coast.", "Natural seasonal farming", (19.2851, 72.8710)),
            ("Sunrise Fields", "Bhayandar East", "Fruit and greens from a small family-run plot.", "Integrated sustainable farming", (19.3010, 72.8560)),
            ("Coastal Harvest Co-op", "Bhayandar West", "A grower cooperative serving neighboring families.", "Community-supported farming", (19.2920, 72.8360)),
            ("Uttan Orchard", "Uttan", "Fruit, herbs and vegetables from the Uttan belt.", "Low-input mixed farming", (19.2700, 72.7850)),
            ("Kashimira Organics", "Kashimira", "Organic-practice greens and pantry produce.", "Organic practices", (19.2660, 72.8680)),
        ]
        farmers = []
        for index, (farm, area, description, method, coords) in enumerate(farmer_specs, 1):
            user = User(full_name=["Aarav Patil", "Meera Naik", "Rohan Sawant", "Anaya More", "Kabir Shah"][index-1],
                email=f"farmer{index}@farm2home.test", password_hash=generate_password_hash(demo_pw),
                phone=f"910000000{index}", role="farmer", address=f"{area}, Mira-Bhayandar",
                city=area, pincode=["401107", "401105", "401101", "401106", "401107"][index-1])
            db.add(user); db.flush()
            farmer = Farmer(user_id=user.user_id, farm_name=farm, farm_location=area,
                description=description, farming_method=method, verification_status="approved",
                latitude=coords[0], longitude=coords[1])
            db.add(farmer); db.flush(); farmers.append((user, farmer))
            db.add(LoyaltyPoint(user_id=user.user_id, points=120))
        consumer_specs = [
            ("Aditi Kulkarni", "consumer@farm2home.test", "9000000011", "Mira Road", "401107"),
            ("Neel Joshi", "consumer2@farm2home.test", "9000000012", "Bhayandar East", "401105"),
            ("Sara Fernandes", "consumer3@farm2home.test", "9000000013", "Kashimira", "401107"),
            ("Ishaan Desai", "consumer4@farm2home.test", "9000000014", "Bhayandar West", "401101"),
            ("Diya Mhatre", "consumer5@farm2home.test", "9000000015", "Uttan", "401106"),
            ("Arjun Rao", "consumer6@farm2home.test", "9000000016", "Mira Road East", "401107"),
        ]
        consumers = []
        for name, email, phone, city, pin in consumer_specs:
            user = User(full_name=name, email=email, password_hash=generate_password_hash(demo_pw),
                phone=phone, role="consumer", address=f"{city} Main Road", city=city, pincode=pin)
            db.add(user); db.flush(); consumers.append(user)
            db.add(Cart(user_id=user.user_id)); db.add(LoyaltyPoint(user_id=user.user_id, points=180))
        slot_specs = [("Morning", time(8,0), time(11,0)), ("Afternoon", time(12,0), time(15,0)), ("Evening", time(16,0), time(19,0))]
        slots = []
        for name, start, end in slot_specs:
            slot = DeliverySlot(slot_name=name, start_time=start, end_time=end, max_orders=18, status="active")
            db.add(slot); db.flush(); slots.append(slot)
        plan_specs = [
            ("Weekly Fresh Basket", "weekly", 549, 5, "A colorful weekly selection of seasonal farm staples."),
            ("Bi-Weekly Family Basket", "biweekly", 999, 7, "A family-sized box arriving every two weeks."),
            ("Monthly Organic Basket", "monthly", 1799, 10, "A curated organic-practice selection once a month."),
            ("Weekly Greens Box", "weekly", 399, 5, "Leafy greens and fresh herbs for the week."),
            ("Seasonal Farm Box", "monthly", 1299, 8, "A changing monthly box based on the harvest."),
        ]
        plans = []
        for name, freq, price, discount, desc in plan_specs:
            plan = SubscriptionPlan(plan_name=name, frequency=freq, price=Decimal(str(price)),
                discount_percent=discount, description=desc, delivery_slot="Morning", bonus_points=10)
            db.add(plan); db.flush(); plans.append(plan)
        products_data = [
            ("Organic Tomatoes", "Vegetables", 60, "kg", True, "Juicy vine-ripened tomatoes."),
            ("Baby Spinach", "Leafy Vegetables", 45, "bunch", True, "Tender spinach leaves for everyday meals."),
            ("Alphonso Mangoes", "Fruits", 180, "kg", False, "Seasonal sweet mangoes from the grower."),
            ("Farm Carrots", "Vegetables", 55, "kg", True, "Crunchy, bright carrots harvested this week."),
            ("Fresh Okra", "Vegetables", 52, "kg", False, "Small-batch okra with a crisp bite."),
            ("Coriander Bunch", "Leafy Vegetables", 18, "bunch", True, "Fragrant coriander picked to order."),
            ("Green Cucumbers", "Vegetables", 38, "kg", False, "Cool and crisp cucumbers."),
            ("Purple Eggplant", "Vegetables", 48, "kg", True, "Glossy brinjal from a nearby farm."),
            ("Red Onions", "Vegetables", 42, "kg", False, "Kitchen-ready red onions."),
            ("Sweet Bananas", "Fruits", 60, "dozen", False, "Naturally sweet local bananas."),
            ("Leafy Amaranth", "Leafy Vegetables", 25, "bunch", True, "Vibrant amaranth greens."),
            ("Red Bell Peppers", "Vegetables", 110, "kg", True, "Colorful sweet peppers."),
            ("Fresh Sweet Corn", "Vegetables", 40, "each", False, "Tender cobs picked at the right time."),
            ("Seasonal Papaya", "Fruits", 50, "kg", False, "Ripe papaya with a mellow sweetness."),
            ("Organic Green Peas", "Organic Produce", 95, "kg", True, "Sweet peas grown with organic practices."),
            ("Brown Rice", "Grains", 95, "kg", False, "Locally milled everyday brown rice."),
            ("Toor Dal", "Pulses", 145, "kg", False, "Cleaned and sorted toor dal."),
            ("Tender Drumsticks", "Vegetables", 65, "bunch", True, "Fresh drumsticks for sambar and curries."),
            ("Fresh Mint", "Leafy Vegetables", 20, "bunch", True, "Cooling mint leaves."),
            ("Local Groundnuts", "Farm Products", 120, "kg", False, "Small-batch roasted-ready groundnuts."),
            ("Bottle Gourd", "Vegetables", 36, "each", False, "Tender lauki harvested nearby."),
            ("Red Amaranth", "Leafy Vegetables", 28, "bunch", True, "Colorful nutrient-rich leafy greens."),
            ("Farm Fresh Curd", "Dairy", 75, "500g", False, "Creamy cultured curd from a local dairy."),
            ("Seasonal Guava", "Fruits", 85, "kg", True, "Aromatic guavas from the seasonal harvest."),
            ("Organic Lemon", "Organic Produce", 70, "kg", True, "Bright lemons grown with organic practices."),
        ]
        products = []
        for idx, (name, category, price, unit, organic, description) in enumerate(products_data):
            farmer = farmers[idx % len(farmers)][1]
            product = Product(farmer_id=farmer.farmer_id, category_id=categories[category].category_id,
                product_name=name, description=description, price=Decimal(str(price)), unit=unit,
                available_quantity=15 + (idx % 12), organic=organic, image_url="", status="active")
            db.add(product); db.flush(); products.append(product)
        # Two active subscriptions exercise renewals; one is paused for dashboard demos.
        for index, plan_idx in ((0, 0), (1, 1), (2, 2)):
            consumer = consumers[index]
            plan = plans[plan_idx]
            sub = Subscription(user_id=consumer.user_id, plan_id=plan.plan_id, plan_name=plan.plan_name,
                frequency=plan.frequency, start_date=date.today()-timedelta(days=14),
                next_delivery_date=date.today()+timedelta(days=1+index), amount=plan.price,
                discount_percent=plan.discount_percent, status="paused" if index == 2 else "active",
                delivery_slot=slots[index].slot_name, delivery_address=consumer.address,
                city=consumer.city, pincode=consumer.pincode)
            db.add(sub); db.flush()
            for product in products[index*3:index*3+4]:
                db.add(SubscriptionItem(subscription_id=sub.subscription_id, product_id=product.product_id, quantity=1))
        # Ten fictional demo orders: eight delivered and two active; all rows are linked.
        for index in range(10):
            consumer = consumers[index % len(consumers)]
            chosen = products[(index * 2) % len(products):(index * 2) % len(products)+2]
            slot = slots[index % len(slots)]
            delivered = index < 8
            service_day = date.today() - timedelta(days=10-index) if delivered else date.today()+timedelta(days=index-7)
            subtotal = sum((p.price for p in chosen), Decimal("0"))
            number = f"F2H-DEMO-{1001+index}"
            order = Order(order_number=number, user_id=consumer.user_id, subtotal=subtotal,
                delivery_fee=Decimal("0.00") if subtotal >= 499 else Decimal("30.00"),
                discount_amount=Decimal("0.00"), loyalty_used=0,
                total_amount=subtotal + (Decimal("0.00") if subtotal >= 499 else Decimal("30.00")),
                delivery_address=consumer.address, city=consumer.city, pincode=consumer.pincode,
                delivery_date=service_day, delivery_slot=slot.slot_name, delivery_slot_id=slot.slot_id,
                order_status="Delivered" if delivered else ("Preparing" if index == 8 else "Confirmed"),
                payment_status="paid" if delivered else "pending")
            db.add(order); db.flush()
            for product in chosen:
                db.add(OrderItem(order_id=order.order_id, product_id=product.product_id,
                    quantity=1, price_at_purchase=product.price))
                product.available_quantity = max(0, product.available_quantity-1)
            db.add(Payment(order_id=order.order_id, amount=order.total_amount,
                payment_method="demo_online" if index % 2 else "cod",
                transaction_reference=f"DEMO-REF-{1001+index}",
                payment_status="simulated_success" if delivered and index % 2 else ("paid" if delivered else "pending")))
            farmer_coord = farmers[index % len(farmers)][1]
            delivery = Delivery(order_id=order.order_id, delivery_date=service_day,
                delivery_slot=slot.slot_name, delivery_status=order.order_status,
                route_status="completed" if delivered else "optimized",
                current_latitude=farmer_coord.latitude, current_longitude=farmer_coord.longitude,
                estimated_time="Delivered" if delivered else "~28 min from farm", route_sequence=index % 4 + 1,
                route_group=f"{service_day.isoformat()}|{consumer.pincode}|{slot.slot_name}")
            db.add(delivery)
            if delivered:
                db.add(Review(user_id=consumer.user_id, product_id=chosen[0].product_id,
                    order_id=order.order_id, rating=4 + (index % 2),
                    comment=["Picked this morning and tasted wonderful.", "Great local quality and careful packing.", "Fresh produce and an easy delivery."][index % 3]))
            if not delivered:
                cap = db.scalar(select(SlotCapacity).where(SlotCapacity.slot_id == slot.slot_id, SlotCapacity.service_date == service_day))
                if not cap:
                    cap = SlotCapacity(slot_id=slot.slot_id, service_date=service_day, current_orders=0); db.add(cap); db.flush()
                cap.current_orders += 1
        for consumer in consumers:
            db.add(Notification(user_id=consumer.user_id, title="A fresh start", message="Browse this week's harvest from local Mira-Bhayandar farms."))
        for user, _farmer in farmers:
            db.add(Notification(user_id=user.user_id, title="Welcome to the marketplace", message="Your approved farm profile is ready for product listings."))
        db.commit()


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static", instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 + 128 * 1024
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_database(app)
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api)
    app.teardown_appcontext(close_session)

    @app.get("/manus-routes.json")
    def route_manifest():
        return send_from_directory(app.static_folder, "manus-routes.json", mimetype="application/json")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def web_pages(path):
        allowed = {"", "shop", "farmers", "subscriptions", "cart", "checkout", "dashboard", "orders", "notifications", "admin", "how-it-works"}
        if path in allowed or path.startswith("product/") or path.startswith("track/"):
            return render_template("index.html")
        if path.startswith("api/"):
            return jsonify({"success": False, "message": "API endpoint not found."}), 404
        return render_template("index.html"), 404

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "service": "farm2home"}), 200

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        return jsonify({"success": False, "message": "Product images must be 5 MB or smaller."}), 413

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        app.logger.exception("Unhandled Farm2Home error")
        return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500

    with app.app_context():
        create_schema(app)
        if app.config.get("SEED_DEMO_DATA", True):
            _seed_demo_data(app)
    return app


def run_due_subscriptions(app):
    """APScheduler callback; safely owns a short-lived DB session."""
    maker = session_factory(app)
    with maker() as db:
        try:
            from services import process_due_subscriptions
            result = process_due_subscriptions(db, date.today())
            db.commit()
            if result["created_order_ids"]:
                app.logger.info("Subscription scheduler created orders: %s", result["created_order_ids"])
        except Exception:
            db.rollback()
            app.logger.exception("Recurring subscription job failed")


def start_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata", daemon=True)
    scheduler.add_job(lambda: run_due_subscriptions(app), IntervalTrigger(hours=1),
        id="farm2home_subscription_renewals", replace_existing=True,
        max_instances=1, coalesce=True, misfire_grace_time=3600)
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def main():
    application = create_app()
    if application.config.get("SCHEDULER_ENABLED", True):
        start_scheduler(application)
    application.run(host="0.0.0.0", port=application.config.get("PORT", 3000), debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
