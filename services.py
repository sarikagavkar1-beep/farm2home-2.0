"""Business helpers for delivery grouping, checkout and recurring subscriptions."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt
import json
import secrets
from sqlalchemy import select
from models import (Cart, CartItem, Delivery, DeliverySlot, Farmer, LoyaltyPoint,
                    LoyaltyTransaction, Notification, Order, OrderItem, Payment,
                    Product, SlotCapacity, Subscription, SubscriptionItem, User)

AREAS = {
    "Mira Road": (19.2800, 72.8700), "Mira Road East": (19.2840, 72.8760),
    "Mira Road West": (19.2780, 72.8600), "Bhayandar": (19.2950, 72.8500),
    "Bhayandar East": (19.3000, 72.8550), "Bhayandar West": (19.2910, 72.8370),
    "Kashimira": (19.2650, 72.8680), "Uttan": (19.2700, 72.7850),
    "Gorai": (19.2400, 72.7950),
}
SLOT_WINDOWS = {"Morning": ("08:00", "11:00"), "Afternoon": ("12:00", "15:00"), "Evening": ("16:00", "19:00")}
DELIVERY_FEE = Decimal("30.00")


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def notify(db, user_id: int, title: str, message: str):
    db.add(Notification(user_id=user_id, title=title, message=message))


def area_coordinates(city: str, pincode: str):
    for key, coordinates in AREAS.items():
        if key.lower() in (city or "").lower():
            return coordinates
    # Stable, small demonstration variation from a known Mira-Bhayandar center.
    tail = int((pincode or "401107")[-2:]) if (pincode or "").isdigit() else 7
    return (19.286 + (tail % 7) * 0.0015, 72.850 + (tail % 9) * 0.0014)


def haversine_km(a, b):
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def optimize_deliveries(db, delivery: Delivery):
    """Greedy nearest-neighbor route within the same date, pincode and time slot."""
    order = db.get(Order, delivery.order_id)
    if not order:
        return
    group_key = f"{order.delivery_date.isoformat()}|{order.pincode}|{order.delivery_slot}"
    rows = db.scalars(select(Delivery).join(Order).where(
        Order.delivery_date == order.delivery_date,
        Order.pincode == order.pincode,
        Order.delivery_slot == order.delivery_slot,
        Order.order_status != "Cancelled",
    )).all()
    stops = []
    farm_origin = (19.2900, 72.8500)
    for row in rows:
        o = db.get(Order, row.order_id)
        user = db.get(User, o.user_id)
        coords = area_coordinates(o.city, o.pincode)
        stops.append({"delivery_id": row.delivery_id, "order_id": o.order_id,
                      "order_number": o.order_number, "label": user.full_name,
                      "city": o.city, "pincode": o.pincode, "lat": coords[0], "lng": coords[1]})
    remaining = list(stops)
    route, current = [], farm_origin
    while remaining:
        nxt = min(remaining, key=lambda p: haversine_km(current, (p["lat"], p["lng"])))
        route.append(nxt)
        remaining.remove(nxt)
        current = (nxt["lat"], nxt["lng"])
    total_km, current = 0.0, farm_origin
    for idx, stop in enumerate(route, 1):
        point = (stop["lat"], stop["lng"])
        total_km += haversine_km(current, point)
        current = point
        item = next(r for r in rows if r.delivery_id == stop["delivery_id"])
        item.route_sequence = idx
        item.route_group = group_key
        # Demonstration ETA includes 12 minutes per stop and 22 km/h urban average.
        minutes = int(total_km / 22 * 60 + idx * 12)
        item.estimated_time = f"~{minutes} min from farm"
        item.route_json = json.dumps({"origin": {"lat": farm_origin[0], "lng": farm_origin[1]}, "stops": route}, ensure_ascii=False)
        if item.current_latitude is None:
            item.current_latitude, item.current_longitude = point
        if item.route_status == "planned":
            item.route_status = "optimized"
    db.flush()


def reserve_slot(db, slot_id: int, service_date: date):
    slot = db.get(DeliverySlot, slot_id)
    if not slot or slot.status != "active":
        raise ValueError("Choose an available delivery slot.")
    capacity = db.scalar(select(SlotCapacity).where(SlotCapacity.slot_id == slot_id, SlotCapacity.service_date == service_date).with_for_update())
    if capacity is None:
        capacity = SlotCapacity(slot_id=slot_id, service_date=service_date, current_orders=0)
        db.add(capacity)
        db.flush()
    if capacity.current_orders >= slot.max_orders:
        raise ValueError("That delivery slot is full. Please choose another time.")
    capacity.current_orders += 1
    return slot, capacity


def create_order_from_lines(db, *, user: User, lines, address: str, city: str, pincode: str,
                            delivery_date: date, slot_id: int, payment_method: str,
                            subscription: Subscription | None = None, use_points: bool = False,
                            subscriber_discount: int = 0):
    if delivery_date < date.today():
        raise ValueError("Choose today or a future delivery date.")
    if not address.strip() or not city.strip() or len(pincode) != 6 or not pincode.isdigit():
        raise ValueError("Enter a delivery address, city and six-digit pincode.")
    if payment_method not in ("cod", "demo_online"):
        raise ValueError("Choose Cash on Delivery or Demo Online Payment.")
    slot, _ = reserve_slot(db, slot_id, delivery_date)
    subtotal = money(sum((money(product.price) * quantity for product, quantity in lines), Decimal("0")))
    if subtotal <= 0:
        raise ValueError("Your basket is empty.")
    discount = money(subtotal * Decimal(subscriber_discount) / Decimal(100))
    loyalty = db.scalar(select(LoyaltyPoint).where(LoyaltyPoint.user_id == user.user_id))
    points_used, loyalty_discount = 0, Decimal("0.00")
    if use_points and loyalty:
        points_used = min((loyalty.points // 100) * 100, int(max(0, subtotal - discount) * 10))
        loyalty_discount = money(Decimal(points_used) / 10)
        loyalty.points -= points_used
        db.add(LoyaltyTransaction(user_id=user.user_id, points_delta=-points_used,
                                  event_key=f"redeem:{secrets.token_hex(8)}", note="Checkout points redeemed"))
    fee = Decimal("0.00") if subtotal >= Decimal("499.00") else DELIVERY_FEE
    total = max(Decimal("0.00"), money(subtotal + fee - discount - loyalty_discount))
    for product, quantity in lines:
        if product.status != "active" or product.available_quantity < quantity:
            raise ValueError(f"Not enough stock for {product.product_name}.")
    order = Order(order_number=f"F2H-{datetime.now():%y%m%d}-{secrets.token_hex(3).upper()}",
                  user_id=user.user_id, subscription_id=subscription.subscription_id if subscription else None,
                  subtotal=subtotal, delivery_fee=fee, discount_amount=money(discount + loyalty_discount),
                  loyalty_used=points_used, total_amount=total, delivery_address=address.strip(), city=city.strip(),
                  pincode=pincode, delivery_date=delivery_date, delivery_slot=slot.slot_name,
                  delivery_slot_id=slot.slot_id, order_status="Placed",
                  payment_status="paid" if payment_method == "demo_online" else "pending")
    db.add(order)
    db.flush()
    for product, quantity in lines:
        product.available_quantity -= quantity
        db.add(OrderItem(order_id=order.order_id, product_id=product.product_id,
                         quantity=quantity, price_at_purchase=money(product.price)))
    db.add(Payment(order_id=order.order_id, amount=total, payment_method=payment_method,
                   transaction_reference=f"DEMO-{secrets.token_hex(6).upper()}",
                   payment_status="simulated_success" if payment_method == "demo_online" else "pending"))
    delivery = Delivery(order_id=order.order_id, delivery_date=delivery_date,
                         delivery_slot=slot.slot_name, delivery_status="Placed",
                         route_status="planned", route_group="")
    db.add(delivery)
    db.flush()
    optimize_deliveries(db, delivery)
    notify(db, user.user_id, "Order placed", f"Your order {order.order_number} is confirmed for {slot.slot_name} delivery.")
    return order


def next_delivery_after(freq: str, when: date):
    if freq == "weekly":
        return when + timedelta(days=7)
    if freq == "biweekly":
        return when + timedelta(days=14)
    # Preserve a sensible monthly cadence without relying on an optional date library.
    year, month = when.year, when.month + 1
    if month == 13:
        year, month = year + 1, 1
    import calendar
    return date(year, month, min(when.day, calendar.monthrange(year, month)[1]))


def process_due_subscriptions(db, today: date | None = None):
    """Generate one recurring order per due period. The unique date guard makes retries safe."""
    today = today or date.today()
    due = db.scalars(select(Subscription).where(Subscription.status == "active", Subscription.next_delivery_date <= today)).all()
    created, skipped = [], []
    for sub in due:
        due_date = sub.next_delivery_date
        event_key = f"subscription:{sub.subscription_id}:{due_date.isoformat()}"
        # last_generated_for is a durable idempotency key for this subscription billing date.
        if sub.last_generated_for == due_date:
            skipped.append(sub.subscription_id)
            continue
        user = db.get(User, sub.user_id)
        items = db.scalars(select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub.subscription_id)).all()
        lines = []
        for item in items:
            product = db.get(Product, item.product_id)
            if product and product.status == "active" and product.available_quantity >= item.quantity:
                lines.append((product, item.quantity))
        if not user or not lines:
            notify(db, sub.user_id, "Subscription delivery delayed", f"{sub.plan_name} could not renew today because produce is unavailable.")
            skipped.append(sub.subscription_id)
            continue
        slot = db.scalar(select(DeliverySlot).where(DeliverySlot.slot_name == sub.delivery_slot, DeliverySlot.status == "active"))
        if not slot:
            slot = db.scalar(select(DeliverySlot).where(DeliverySlot.status == "active").order_by(DeliverySlot.slot_id))
        if not slot:
            skipped.append(sub.subscription_id)
            continue
        try:
            order = create_order_from_lines(db, user=user, lines=lines, address=sub.delivery_address,
                city=sub.city, pincode=sub.pincode, delivery_date=max(today, due_date), slot_id=slot.slot_id,
                payment_method="cod", subscription=sub, use_points=False,
                subscriber_discount=sub.discount_percent)
        except ValueError as exc:
            notify(db, sub.user_id, "Subscription delivery delayed", str(exc))
            skipped.append(sub.subscription_id)
            continue
        sub.last_generated_for = due_date
        sub.next_delivery_date = next_delivery_after(sub.frequency, due_date)
        notify(db, sub.user_id, "Subscription renewed", f"Order {order.order_number} is on its way to your next delivery slot.")
        created.append(order.order_id)
    return {"created_order_ids": created, "skipped_subscription_ids": skipped}
