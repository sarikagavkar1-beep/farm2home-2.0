"""Farm2Home JSON REST API."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from io import BytesIO
from pathlib import Path
import re
import warnings
from urllib.parse import urlparse
from uuid import uuid4
from flask import Blueprint, current_app, g, jsonify, request, session
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select, desc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_session
from models import (Cart, CartItem, Category, Delivery, DeliverySlot, Farmer,
                    LoyaltyPoint, LoyaltyTransaction, Notification, Order, OrderItem,
                    Payment, Product, Review, SlotCapacity, Subscription,
                    SubscriptionItem, SubscriptionPlan, User)
from services import (create_order_from_lines, money, next_delivery_after, notify,
                      process_due_subscriptions)

api = Blueprint("api", __name__, url_prefix="/api")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\d{10}$")
MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024
PRODUCT_IMAGE_FORMATS = {"JPEG": ("jpg", {".jpg", ".jpeg"}), "PNG": ("png", {".png"}), "WEBP": ("webp", {".webp"})}

def clean_product_image_url(value):
    image_url = str(value or "").strip()
    if not image_url:
        return ""
    if len(image_url) > 500:
        raise ValueError("Image URL must be 500 characters or fewer.")
    if re.fullmatch(r"/static/uploads/[a-f0-9]{32}\.(?:jpg|png|webp)", image_url):
        return image_url
    parsed = urlparse(image_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Use a direct HTTP or HTTPS image URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Image URLs must not contain login credentials.")
    return image_url


def save_product_image(uploaded_file):
    """Validate, normalize and store a small raster image under a random name."""
    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("Choose a JPG, PNG or WEBP image to upload.")
    suffix = Path(str(uploaded_file.filename).replace("\\", "/")).suffix.lower()
    raw = uploaded_file.stream.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if len(raw) > MAX_PRODUCT_IMAGE_BYTES:
        raise ValueError("Product images must be 5 MB or smaller.")
    if not raw:
        raise ValueError("The selected image is empty.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                image_format = source.format
                if image_format not in PRODUCT_IMAGE_FORMATS:
                    raise ValueError("Only JPG, PNG and WEBP image files are supported.")
                extension, allowed_suffixes = PRODUCT_IMAGE_FORMATS[image_format]
                if suffix not in allowed_suffixes:
                    raise ValueError("The image file extension must match its actual image format.")
                width, height = source.size
                if width < 1 or height < 1 or width > 10000 or height > 10000 or width * height > 25_000_000:
                    raise ValueError("Images must be no larger than 10,000 pixels per side or 25 megapixels.")
                image = ImageOps.exif_transpose(source)
                if image_format == "JPEG":
                    image = image.convert("RGB")
                    save_options = {"quality": 88, "optimize": True}
                elif image_format == "WEBP":
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    save_options = {"quality": 88, "method": 4}
                else:
                    save_options = {"optimize": True}
                output = BytesIO()
                image.save(output, format=image_format, **save_options)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("The selected file is not a valid supported image.") from error

    normalized = output.getvalue()
    if len(normalized) > MAX_PRODUCT_IMAGE_BYTES:
        raise ValueError("The optimized image is still larger than 5 MB.")
    filename = f"{uuid4().hex}.{extension}"
    upload_dir = Path(current_app.config.get("PRODUCT_UPLOAD_FOLDER") or Path(current_app.static_folder) / "uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / filename).write_bytes(normalized)
    return f"/static/uploads/{filename}"


def delete_product_image(image_url):
    """Delete only files created by save_product_image, never arbitrary paths."""
    match = re.fullmatch(r"/static/uploads/([a-f0-9]{32}\.(?:jpg|png|webp))", str(image_url or ""))
    if not match:
        return
    upload_dir = Path(current_app.config.get("PRODUCT_UPLOAD_FOLDER") or Path(current_app.static_folder) / "uploads")
    try:
        (upload_dir / match.group(1)).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not remove replaced product image %s", match.group(1))


def ok(data=None, message="OK", status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def fail(message, status=400):
    return jsonify({"success": False, "message": message}), status


def body_json():
    return request.get_json(silent=True) or {}


def current_user(db=None):
    db = db or get_session()
    uid = session.get("user_id")
    return db.get(User, uid) if uid else None


def auth_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            return fail("Please sign in to continue.", 401)
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapped


def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        @auth_required
        def wrapped(*args, **kwargs):
            if g.current_user.role not in allowed:
                return fail("You do not have permission to do that.", 403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def user_json(user):
    return {"user_id": user.user_id, "full_name": user.full_name, "email": user.email,
            "phone": user.phone, "role": user.role, "address": user.address,
            "city": user.city, "pincode": user.pincode}


def product_json(db, product):
    farmer = db.get(Farmer, product.farmer_id)
    user = db.get(User, farmer.user_id) if farmer else None
    category = db.get(Category, product.category_id)
    average = db.scalar(select(func.avg(Review.rating)).where(Review.product_id == product.product_id))
    count = db.scalar(select(func.count(Review.review_id)).where(Review.product_id == product.product_id)) or 0
    return {"product_id": product.product_id, "product_name": product.product_name,
            "description": product.description, "price": float(product.price), "unit": product.unit,
            "available_quantity": product.available_quantity, "organic": bool(product.organic),
            "image_url": product.image_url, "status": product.status,
            "category_id": product.category_id, "category_name": category.category_name if category else "Produce",
            "farmer_id": farmer.farmer_id if farmer else None,
            "farmer_name": farmer.farm_name if farmer else "Local Farm",
            "farmer_location": farmer.farm_location if farmer else "Mira-Bhayandar",
            "farmer_user_id": user.user_id if user else None,
            "rating": round(float(average or 0), 1), "review_count": count,
            "low_stock": product.available_quantity <= 5}


def product_summary_json(product, farmer, user, category, average, reviews):
    return {"product_id": product.product_id, "product_name": product.product_name,
            "description": product.description, "price": float(product.price), "unit": product.unit,
            "available_quantity": product.available_quantity, "organic": bool(product.organic),
            "image_url": product.image_url, "status": product.status,
            "category_id": product.category_id, "category_name": category.category_name,
            "farmer_id": farmer.farmer_id, "farmer_name": farmer.farm_name,
            "farmer_location": farmer.farm_location, "farmer_user_id": user.user_id,
            "rating": round(float(average or 0), 1), "review_count": int(reviews or 0),
            "low_stock": product.available_quantity <= 5}


def order_json(db, order, with_items=True):
    data = {"order_id": order.order_id, "order_number": order.order_number,
            "user_id": order.user_id, "subscription_id": order.subscription_id,
            "subtotal": float(order.subtotal), "delivery_fee": float(order.delivery_fee),
            "discount_amount": float(order.discount_amount), "loyalty_used": order.loyalty_used,
            "total_amount": float(order.total_amount), "delivery_address": order.delivery_address,
            "city": order.city, "pincode": order.pincode,
            "delivery_date": order.delivery_date.isoformat(), "delivery_slot": order.delivery_slot,
            "order_status": order.order_status, "payment_status": order.payment_status,
            "created_at": order.created_at.isoformat() if order.created_at else None}
    if with_items:
        data["items"] = [{"product_id": item.product_id,
                           "product_name": item.product.product_name if item.product else "Produce",
                           "quantity": item.quantity, "price_at_purchase": float(item.price_at_purchase)}
                          for item in order.items]
    delivery = order.delivery
    if delivery:
        data["delivery"] = {"delivery_id": delivery.delivery_id,
                            "delivery_status": delivery.delivery_status,
                            "route_status": delivery.route_status,
                            "estimated_time": delivery.estimated_time,
                            "route_sequence": delivery.route_sequence,
                            "route_group": delivery.route_group}
    return data


def subscription_json(sub):
    return {"subscription_id": sub.subscription_id, "plan_id": sub.plan_id,
            "plan_name": sub.plan_name, "frequency": sub.frequency,
            "start_date": sub.start_date.isoformat(),
            "next_delivery_date": sub.next_delivery_date.isoformat(),
            "amount": float(sub.amount), "discount_percent": sub.discount_percent,
            "status": sub.status, "delivery_slot": sub.delivery_slot,
            "delivery_address": sub.delivery_address, "city": sub.city, "pincode": sub.pincode,
            "items": [{"product_id": i.product_id, "product_name": i.product.product_name,
                       "quantity": i.quantity} for i in sub.items]}


def notify_order_status(db, order, status):
    order.order_status = status
    if order.delivery:
        order.delivery.delivery_status = status
        if status == "Out for Delivery":
            order.delivery.route_status = "in_progress"
        elif status == "Delivered":
            order.delivery.route_status = "completed"
            order.delivery.delivered_at = datetime.utcnow()
    notify(db, order.user_id, f"Order {status.lower()}", f"Your order {order.order_number} is now {status.lower()}.")
    if status == "Delivered":
        loyalty = db.scalar(select(LoyaltyPoint).where(LoyaltyPoint.user_id == order.user_id))
        if not loyalty:
            loyalty = LoyaltyPoint(user_id=order.user_id, points=0)
            db.add(loyalty)
            db.flush()
        bonus = 10 if db.scalar(select(func.count(Subscription.subscription_id)).where(
            Subscription.user_id == order.user_id, Subscription.status == "active")) else 0
        points = int(Decimal(order.total_amount) // Decimal(100)) * 10 + bonus
        if points > 0:
            event_key = f"order-delivered:{order.order_id}"
            exists = db.scalar(select(LoyaltyTransaction.transaction_id).where(
                LoyaltyTransaction.user_id == order.user_id, LoyaltyTransaction.event_key == event_key))
            if not exists:
                loyalty.points += points
                db.add(LoyaltyTransaction(user_id=order.user_id, points_delta=points,
                    event_key=event_key, note=f"Earned from delivered order {order.order_number}"))


@api.get("/health")
def health():
    return ok({"service": "Farm2Home API", "status": "ready"}, "API is ready")


@api.post("/auth/register")
def register():
    db, data = get_session(), body_json()
    name, email = str(data.get("full_name", "")).strip(), str(data.get("email", "")).strip().lower()
    password, phone = str(data.get("password", "")), str(data.get("phone", "")).strip()
    role = str(data.get("role", "consumer"))
    if not name or not email or not password or not phone:
        return fail("Name, email, password and phone are required.")
    if not EMAIL_RE.match(email):
        return fail("Enter a valid email address.")
    if not PHONE_RE.match(phone):
        return fail("Phone number must be exactly 10 digits.")
    if len(password) < 8:
        return fail("Password must contain at least 8 characters.")
    if role not in ("consumer", "farmer"):
        return fail("Choose consumer or farmer registration.")
    if db.scalar(select(User.user_id).where(User.email == email)):
        return fail("An account with this email already exists.", 409)
    if db.scalar(select(User.user_id).where(User.phone == phone)):
        return fail("An account with this phone number already exists.", 409)
    try:
        user = User(full_name=name, email=email, password_hash=generate_password_hash(password),
                    phone=phone, role=role, address=str(data.get("address", "")).strip() or None,
                    city=str(data.get("city", "Mira Road")).strip() or "Mira Road",
                    pincode=str(data.get("pincode", "401107")).strip() or "401107")
        db.add(user)
        db.flush()
        db.add(Cart(user_id=user.user_id))
        db.add(LoyaltyPoint(user_id=user.user_id, points=0))
        if role == "farmer":
            farm_name = str(data.get("farm_name", "")).strip()
            if not farm_name:
                db.rollback()
                return fail("Farm name is required for farmer registration.")
            db.add(Farmer(user_id=user.user_id, farm_name=farm_name,
                          farm_location=str(data.get("farm_location", user.city)).strip(),
                          description=str(data.get("description", "")),
                          farming_method=str(data.get("farming_method", "Seasonal local farming")),
                          verification_status="pending"))
            notify(db, user.user_id, "Application received", "Your farm profile is waiting for admin approval.")
        db.commit()
        session.clear()
        session["user_id"] = user.user_id
        session.permanent = True
        return ok({"user": user_json(user)}, "Account created successfully.", 201)
    except (IntegrityError, SQLAlchemyError):
        db.rollback()
        return fail("We could not create this account. Check that email and phone are unique.", 409)


@api.post("/auth/login")
def login():
    db, data = get_session(), body_json()
    email = str(data.get("email", "")).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not check_password_hash(user.password_hash, str(data.get("password", ""))) or not user.is_active:
        return fail("Email or password is incorrect.", 401)
    session.clear()
    session["user_id"] = user.user_id
    session.permanent = True
    return ok({"user": user_json(user)}, "Welcome back.")


@api.post("/auth/logout")
def logout():
    session.clear()
    return ok({}, "You have signed out.")


@api.get("/auth/me")
def me():
    user = current_user()
    return ok({"user": user_json(user)} if user else {"user": None})


@api.get("/categories")
def categories():
    db = get_session()
    return ok([{"category_id": c.category_id, "category_name": c.category_name,
                "description": c.description} for c in db.scalars(select(Category).order_by(Category.category_name)).all()])


@api.get("/products")
def products():
    db = get_session()
    review_stats = select(Review.product_id.label("product_id"),
                          func.avg(Review.rating).label("average_rating"),
                          func.count(Review.review_id).label("review_count"))\
        .group_by(Review.product_id).subquery()
    stmt = select(Product, Farmer, User, Category,
                  review_stats.c.average_rating, review_stats.c.review_count)\
        .join(Farmer, Product.farmer_id == Farmer.farmer_id)\
        .join(User, Farmer.user_id == User.user_id)\
        .join(Category, Product.category_id == Category.category_id)\
        .outerjoin(review_stats, review_stats.c.product_id == Product.product_id)\
        .where(Product.status == "active", Farmer.verification_status == "approved")
    search = request.args.get("q", "").strip()
    if search:
        term = f"%{search}%"
        stmt = stmt.where((Product.product_name.ilike(term)) | (Product.description.ilike(term)))
    if request.args.get("category"):
        stmt = stmt.where(Category.category_name == request.args["category"])
    if request.args.get("organic") == "true":
        stmt = stmt.where(Product.organic.is_(True))
    if request.args.get("farmer_id", "").isdigit():
        stmt = stmt.where(Product.farmer_id == int(request.args["farmer_id"]))
    sort = request.args.get("sort", "featured")
    if sort == "price_asc": stmt = stmt.order_by(Product.price.asc())
    elif sort == "price_desc": stmt = stmt.order_by(Product.price.desc())
    elif sort == "name": stmt = stmt.order_by(Product.product_name.asc())
    else: stmt = stmt.order_by(Product.organic.desc(), Product.product_name.asc())
    rows = db.execute(stmt.limit(100)).all()
    return ok([product_summary_json(*row) for row in rows])


@api.get("/products/<int:product_id>")
def product_detail(product_id):
    db = get_session()
    product = db.get(Product, product_id)
    if not product or product.status != "active": return fail("Product not found.", 404)
    return ok(product_json(db, product))


def farmer_profile(db, user):
    return db.scalar(select(Farmer).where(Farmer.user_id == user.user_id))


@api.post("/products")
@roles("farmer", "admin")
def create_product():
    db, data, user = get_session(), body_json(), g.current_user
    farmer = farmer_profile(db, user) if user.role == "farmer" else db.get(Farmer, data.get("farmer_id"))
    if not farmer or (user.role == "farmer" and farmer.verification_status != "approved"):
        return fail("An approved farm profile is required to list products.", 403)
    try:
        image_url = clean_product_image_url(data.get("image_url", ""))
    except ValueError as error:
        return fail(str(error))
    try:
        category_id = int(data.get("category_id"))
        price, stock = money(data.get("price")), int(data.get("available_quantity", 0))
        if price <= 0 or stock < 0: return fail("Price must be positive and stock cannot be negative.")
        if not db.get(Category, category_id): return fail("Choose a valid category.")
        product = Product(farmer_id=farmer.farmer_id, category_id=category_id,
            product_name=str(data.get("product_name", "")).strip(), description=str(data.get("description", "")),
            price=price, unit=str(data.get("unit", "kg")), available_quantity=stock,
            organic=bool(data.get("organic")), image_url=image_url, status="active")
        if not product.product_name: return fail("Product name is required.")
        db.add(product); db.commit()
        return ok(product_json(db, product), "Product added.", 201)
    except (ValueError, TypeError): return fail("Enter a valid category, price and stock quantity.")
    except SQLAlchemyError:
        db.rollback(); return fail("Product could not be saved.", 500)


@api.put("/products/<int:product_id>")
@roles("farmer", "admin")
def update_product(product_id):
    db, data, user = get_session(), body_json(), g.current_user
    product = db.get(Product, product_id)
    if not product: return fail("Product not found.", 404)
    farmer = farmer_profile(db, user) if user.role == "farmer" else None
    if user.role == "farmer" and (not farmer or product.farmer_id != farmer.farmer_id): return fail("You can only edit your own products.", 403)
    old_image_url = product.image_url
    try:
        if "image_url" in data:
            try:
                product.image_url = clean_product_image_url(data["image_url"])
            except ValueError as error:
                return fail(str(error))
        for key, column in (("product_name", "product_name"), ("description", "description"), ("unit", "unit"), ("organic", "organic"), ("status", "status")):
            if key in data: setattr(product, column, data[key])
        if "category_id" in data:
            if not db.get(Category, int(data["category_id"])): return fail("Choose a valid category.")
            product.category_id = int(data["category_id"])
        if "price" in data: product.price = money(data["price"])
        if "available_quantity" in data:
            product.available_quantity = int(data["available_quantity"])
            if product.available_quantity < 0: return fail("Stock cannot be negative.")
        if product.price <= 0: return fail("Price must be greater than zero.")
        db.commit()
        if old_image_url != product.image_url: delete_product_image(old_image_url)
        return ok(product_json(db, product), "Product updated.")
    except (ValueError, TypeError): return fail("Enter valid product values.")
    except SQLAlchemyError:
        db.rollback(); return fail("Product could not be updated.", 500)


@api.post("/products/<int:product_id>/image")
@roles("farmer", "admin")
def upload_product_image(product_id):
    db, user = get_session(), g.current_user
    product = db.get(Product, product_id)
    if not product: return fail("Product not found.", 404)
    farmer = farmer_profile(db, user) if user.role == "farmer" else None
    if user.role == "farmer" and (not farmer or farmer.verification_status != "approved"):
        return fail("An approved farm profile is required to upload product photos.", 403)
    if user.role == "farmer" and product.farmer_id != farmer.farmer_id:
        return fail("You can only upload photos for your own products.", 403)
    uploaded_file = request.files.get("product_image")
    try:
        new_image_url = save_product_image(uploaded_file)
    except ValueError as error:
        return fail(str(error))
    except OSError:
        current_app.logger.exception("Product image storage failed")
        return fail("The image could not be saved. Check that the uploads folder is writable.", 500)
    old_image_url = product.image_url
    product.image_url = new_image_url
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback(); delete_product_image(new_image_url)
        return fail("The image was received but could not be linked to the product.", 500)
    if old_image_url != new_image_url: delete_product_image(old_image_url)
    return ok(product_json(db, product), "Product photo uploaded.")


@api.delete("/products/<int:product_id>")
@roles("farmer", "admin")
def delete_product(product_id):
    db, user = get_session(), g.current_user
    product = db.get(Product, product_id)
    if not product: return fail("Product not found.", 404)
    farmer = farmer_profile(db, user) if user.role == "farmer" else None
    if user.role == "farmer" and (not farmer or product.farmer_id != farmer.farmer_id): return fail("You can only remove your own products.", 403)
    product.status = "inactive"
    db.commit(); return ok({}, "Product removed from the marketplace.")


@api.get("/farmers")
def farmers():
    db = get_session()
    rows = db.scalars(select(Farmer).where(Farmer.verification_status == "approved").order_by(Farmer.farm_name)).all()
    result = []
    for f in rows:
        user = db.get(User, f.user_id)
        count = db.scalar(select(func.count(Product.product_id)).where(Product.farmer_id == f.farmer_id, Product.status == "active")) or 0
        result.append({"farmer_id": f.farmer_id, "farm_name": f.farm_name, "farm_location": f.farm_location,
                       "description": f.description, "farming_method": f.farming_method,
                       "verification_status": f.verification_status, "latitude": float(f.latitude),
                       "longitude": float(f.longitude), "farmer_name": user.full_name if user else "Local farmer",
                       "product_count": count})
    return ok(result)


@api.get("/farmers/<int:farmer_id>")
def farmer_detail(farmer_id):
    db = get_session(); f = db.get(Farmer, farmer_id)
    if not f or f.verification_status != "approved": return fail("Farmer not found.", 404)
    user = db.get(User, f.user_id)
    return ok({"farmer_id": f.farmer_id, "farm_name": f.farm_name, "farmer_name": user.full_name,
               "farm_location": f.farm_location, "description": f.description,
               "farming_method": f.farming_method, "latitude": float(f.latitude), "longitude": float(f.longitude),
               "products": [product_json(db, p) for p in db.scalars(select(Product).where(Product.farmer_id == f.farmer_id, Product.status == "active")).all()]})


def get_cart(db, user_id):
    cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
    if not cart:
        cart = Cart(user_id=user_id); db.add(cart); db.flush()
    return cart


def cart_json(db, cart):
    lines, subtotal = [], Decimal("0.00")
    for item in cart.items:
        p = db.get(Product, item.product_id)
        if not p or p.status != "active": continue
        line = money(p.price * item.quantity); subtotal += line
        lines.append({"cart_item_id": item.cart_item_id, "product": product_json(db, p), "quantity": item.quantity, "line_total": float(line)})
    user = current_user(db)
    loyalty = db.scalar(select(LoyaltyPoint).where(LoyaltyPoint.user_id == user.user_id)) if user else None
    active_sub = bool(user and db.scalar(select(func.count(Subscription.subscription_id)).where(Subscription.user_id == user.user_id, Subscription.status == "active")))
    discount = money(subtotal * Decimal(5) / Decimal(100)) if active_sub else Decimal("0.00")
    fee = Decimal("0.00") if subtotal >= 499 else (Decimal("30.00") if subtotal else Decimal("0.00"))
    return {"cart_id": cart.cart_id, "items": lines, "item_count": sum(x["quantity"] for x in lines),
            "subtotal": float(subtotal), "delivery_fee": float(fee), "discount": float(discount),
            "loyalty_points": loyalty.points if loyalty else 0,
            "final_total": float(max(Decimal("0"), subtotal + fee - discount))}


@api.get("/cart")
@roles("consumer")
def read_cart():
    db = get_session(); cart = get_cart(db, g.current_user.user_id); db.commit()
    return ok(cart_json(db, cart))


@api.post("/cart/add")
@roles("consumer")
def add_cart():
    db, data = get_session(), body_json()
    try: product_id, quantity = int(data.get("product_id")), int(data.get("quantity", 1))
    except (ValueError, TypeError): return fail("Choose a valid product and quantity.")
    if quantity < 1 or quantity > 99: return fail("Quantity must be between 1 and 99.")
    product = db.get(Product, product_id)
    if not product or product.status != "active": return fail("Product is unavailable.", 404)
    cart = get_cart(db, g.current_user.user_id)
    item = db.scalar(select(CartItem).where(CartItem.cart_id == cart.cart_id, CartItem.product_id == product_id))
    new_qty = quantity + (item.quantity if item else 0)
    if new_qty > product.available_quantity: return fail("That quantity is not available in stock.")
    if item: item.quantity = new_qty
    else: db.add(CartItem(cart_id=cart.cart_id, product_id=product_id, quantity=quantity))
    db.commit(); return ok(cart_json(db, cart), "Added to your basket.")


@api.put("/cart/update")
@roles("consumer")
def update_cart():
    db, data = get_session(), body_json()
    try: item_id, quantity = int(data.get("cart_item_id")), int(data.get("quantity"))
    except (ValueError, TypeError): return fail("Enter a valid basket item and quantity.")
    cart = get_cart(db, g.current_user.user_id)
    item = db.get(CartItem, item_id)
    if not item or item.cart_id != cart.cart_id: return fail("Basket item not found.", 404)
    if quantity <= 0:
        db.delete(item)
    else:
        product = db.get(Product, item.product_id)
        if quantity > product.available_quantity: return fail("That quantity is not available in stock.")
        item.quantity = min(quantity, 99)
    db.commit(); return ok(cart_json(db, cart), "Basket updated.")


@api.delete("/cart/remove")
@roles("consumer")
def remove_cart():
    db, data = get_session(), body_json()
    item_id = data.get("cart_item_id") or request.args.get("cart_item_id")
    try: item_id = int(item_id)
    except (ValueError, TypeError): return fail("Choose a valid basket item.")
    cart = get_cart(db, g.current_user.user_id); item = db.get(CartItem, item_id)
    if not item or item.cart_id != cart.cart_id: return fail("Basket item not found.", 404)
    db.delete(item); db.commit(); return ok(cart_json(db, cart), "Item removed.")


@api.get("/delivery-slots")
def delivery_slots():
    db = get_session(); day = request.args.get("date", date.today().isoformat())
    try: service_date = date.fromisoformat(day)
    except ValueError: return fail("Enter a valid delivery date.")
    slots = db.scalars(select(DeliverySlot).where(DeliverySlot.status == "active").order_by(DeliverySlot.slot_id)).all()
    output = []
    for slot in slots:
        cap = db.scalar(select(SlotCapacity).where(SlotCapacity.slot_id == slot.slot_id, SlotCapacity.service_date == service_date))
        current = cap.current_orders if cap else 0
        output.append({"slot_id": slot.slot_id, "slot_name": slot.slot_name,
                       "start_time": slot.start_time.strftime("%H:%M"), "end_time": slot.end_time.strftime("%H:%M"),
                       "max_orders": slot.max_orders, "current_orders": current,
                       "available": max(0, slot.max_orders-current)})
    return ok(output)


@api.post("/orders")
@roles("consumer")
def create_order():
    db, data, user = get_session(), body_json(), g.current_user
    cart = get_cart(db, user.user_id)
    if not cart.items: return fail("Your basket is empty.")
    try:
        slot_id = int(data.get("slot_id"))
        delivery_date = date.fromisoformat(str(data.get("delivery_date", "")))
        lines = [(db.get(Product, item.product_id), item.quantity) for item in cart.items]
        if any(p is None for p, _q in lines): return fail("A product in your basket is no longer available.")
        full_name = str(data.get("name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        if not full_name or not PHONE_RE.match(phone):
            return fail("Enter a full name and a phone number with exactly 10 digits.")
        if db.scalar(select(User.user_id).where(User.phone == phone, User.user_id != user.user_id)):
            return fail("That phone number is already linked to another account.", 409)
        active_sub = db.scalar(select(Subscription).where(Subscription.user_id == user.user_id, Subscription.status == "active"))
        order = create_order_from_lines(db, user=user, lines=lines,
            address=str(data.get("address", user.address or "")), city=str(data.get("city", user.city or "Mira Road")),
            pincode=str(data.get("pincode", user.pincode or "401107")), delivery_date=delivery_date,
            slot_id=slot_id, payment_method=str(data.get("payment_method", "cod")),
            use_points=bool(data.get("use_points")), subscriber_discount=5 if active_sub else 0)
        user.full_name, user.phone = full_name, phone
        user.address, user.city, user.pincode = order.delivery_address, order.city, order.pincode
        for item in list(cart.items): db.delete(item)
        db.commit()
        return ok(order_json(db, order), "Order placed successfully.", 201)
    except ValueError as exc:
        db.rollback(); return fail(str(exc))
    except (IntegrityError, SQLAlchemyError):
        db.rollback(); return fail("We could not place this order. Please refresh and try again.", 409)


@api.get("/orders")
@auth_required
def list_orders():
    db, user = get_session(), g.current_user
    stmt = select(Order).order_by(desc(Order.created_at))
    if user.role == "consumer": stmt = stmt.where(Order.user_id == user.user_id)
    elif user.role == "farmer":
        farmer = farmer_profile(db, user)
        ids = select(OrderItem.order_id).join(Product).where(Product.farmer_id == farmer.farmer_id) if farmer else select(Order.order_id).where(False)
        stmt = stmt.where(Order.order_id.in_(ids))
    rows = db.scalars(stmt.limit(100)).unique().all()
    return ok([order_json(db, o) for o in rows])


@api.get("/orders/<int:order_id>")
@auth_required
def order_detail(order_id):
    db, user = get_session(), g.current_user
    order = db.get(Order, order_id)
    if not order: return fail("Order not found.", 404)
    allowed = user.role == "admin" or (user.role == "consumer" and order.user_id == user.user_id)
    if user.role == "farmer":
        f = farmer_profile(db, user)
        allowed = bool(f and any(db.get(Product, item.product_id).farmer_id == f.farmer_id for item in order.items))
    if not allowed: return fail("You cannot view this order.", 403)
    return ok(order_json(db, order))


@api.get("/subscriptions/plans")
def subscription_plans():
    db = get_session(); rows = db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.price)).all()
    return ok([{"plan_id": p.plan_id, "plan_name": p.plan_name, "frequency": p.frequency,
                "price": float(p.price), "discount_percent": p.discount_percent,
                "description": p.description, "delivery_slot": p.delivery_slot,
                "bonus_points": p.bonus_points} for p in rows])


@api.get("/subscriptions")
@roles("consumer")
def my_subscriptions():
    db = get_session(); rows = db.scalars(select(Subscription).where(Subscription.user_id == g.current_user.user_id).order_by(desc(Subscription.created_at))).all()
    return ok([subscription_json(s) for s in rows])


@api.post("/subscriptions")
@roles("consumer")
def create_subscription():
    db, data, user = get_session(), body_json(), g.current_user
    try: plan_id = int(data.get("plan_id"))
    except (ValueError, TypeError): return fail("Choose a subscription plan.")
    plan = db.get(SubscriptionPlan, plan_id)
    if not plan: return fail("Subscription plan not found.", 404)
    try:
        next_date = date.fromisoformat(str(data.get("next_delivery_date", (date.today()).isoformat())))
        if next_date < date.today(): return fail("The first delivery must be today or a future date.")
        slot_id = int(data.get("slot_id", 0))
    except (ValueError, TypeError): return fail("Enter a valid delivery date and slot.")
    slot = db.get(DeliverySlot, slot_id)
    if not slot or slot.status != "active": return fail("Choose an available delivery slot.")
    address = str(data.get("address", user.address or "")).strip()
    city = str(data.get("city", user.city or "Mira Road")).strip()
    pincode = str(data.get("pincode", user.pincode or "401107")).strip()
    if not address or len(pincode) != 6 or not pincode.isdigit(): return fail("Enter an address and six-digit pincode.")
    sub = Subscription(user_id=user.user_id, plan_id=plan.plan_id, plan_name=plan.plan_name,
        frequency=plan.frequency, start_date=date.today(), next_delivery_date=next_date,
        amount=plan.price, discount_percent=plan.discount_percent, status="active",
        delivery_slot=slot.slot_name, delivery_address=address, city=city, pincode=pincode)
    db.add(sub); db.flush()
    product_ids = data.get("product_ids") or []
    selected_products = set()
    if product_ids:
        for pid in product_ids[:10]:
            try: p = db.get(Product, int(pid))
            except (ValueError, TypeError): p = None
            if p and p.status == "active" and p.product_id not in selected_products:
                selected_products.add(p.product_id)
                db.add(SubscriptionItem(subscription_id=sub.subscription_id, product_id=p.product_id, quantity=1))
    if not selected_products:
        products = db.scalars(select(Product).where(Product.status == "active").order_by(Product.organic.desc(), Product.product_id).limit(4)).all()
        for p in products: db.add(SubscriptionItem(subscription_id=sub.subscription_id, product_id=p.product_id, quantity=1))
    user.address, user.city, user.pincode = address, city, pincode
    notify(db, user.user_id, "Subscription started", f"{plan.plan_name} is active. Your next delivery is {next_date.isoformat()}.")
    db.commit(); return ok(subscription_json(sub), "Subscription started.", 201)


def owned_subscription(db, sub_id, user):
    sub = db.get(Subscription, sub_id)
    if not sub: return None, fail("Subscription not found.", 404)
    if user.role != "admin" and sub.user_id != user.user_id: return None, fail("You cannot manage this subscription.", 403)
    return sub, None


@api.put("/subscriptions/<int:sub_id>/pause")
@roles("consumer", "admin")
def pause_subscription(sub_id):
    db, user = get_session(), g.current_user
    sub, err = owned_subscription(db, sub_id, user)
    if err: return err
    if sub.status != "active": return fail("Only an active subscription can be paused.")
    sub.status = "paused"; notify(db, sub.user_id, "Subscription paused", f"{sub.plan_name} is paused.")
    db.commit(); return ok(subscription_json(sub), "Subscription paused.")


@api.put("/subscriptions/<int:sub_id>/resume")
@roles("consumer", "admin")
def resume_subscription(sub_id):
    db, user = get_session(), g.current_user
    sub, err = owned_subscription(db, sub_id, user)
    if err: return err
    if sub.status != "paused": return fail("Only a paused subscription can be resumed.")
    sub.status = "active"
    if sub.next_delivery_date < date.today(): sub.next_delivery_date = date.today()
    notify(db, sub.user_id, "Subscription resumed", f"{sub.plan_name} is active again. Next delivery: {sub.next_delivery_date.isoformat()}.")
    db.commit(); return ok(subscription_json(sub), "Subscription resumed.")


@api.delete("/subscriptions/<int:sub_id>")
@roles("consumer", "admin")
def cancel_subscription(sub_id):
    db, user = get_session(), g.current_user
    sub, err = owned_subscription(db, sub_id, user)
    if err: return err
    sub.status = "cancelled"; notify(db, sub.user_id, "Subscription cancelled", f"{sub.plan_name} has been cancelled.")
    db.commit(); return ok(subscription_json(sub), "Subscription cancelled.")


@api.post("/subscriptions/<int:sub_id>/renew")
@roles("consumer", "admin")
def renew_subscription(sub_id):
    db, user = get_session(), g.current_user
    sub, err = owned_subscription(db, sub_id, user)
    if err: return err
    if sub.status != "active": return fail("Resume the subscription before renewing it.")
    if sub.last_generated_for == sub.next_delivery_date:
        return fail("This delivery period has already been renewed.", 409)
    # Manual/demo renewal creates now and advances the cadence.
    target = sub.next_delivery_date
    if target < date.today(): target = date.today()
    items = db.scalars(select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub.subscription_id)).all()
    lines = [(db.get(Product, i.product_id), i.quantity) for i in items]
    slot = db.scalar(select(DeliverySlot).where(DeliverySlot.slot_name == sub.delivery_slot, DeliverySlot.status == "active"))
    if not lines or not slot: return fail("This subscription does not have available items or a delivery slot.")
    try:
        order = create_order_from_lines(db, user=db.get(User, sub.user_id), lines=lines,
            address=sub.delivery_address, city=sub.city, pincode=sub.pincode,
            delivery_date=target, slot_id=slot.slot_id, payment_method="cod",
            subscription=sub, subscriber_discount=sub.discount_percent)
        sub.last_generated_for = sub.next_delivery_date
        sub.next_delivery_date = next_delivery_after(sub.frequency, sub.next_delivery_date)
        notify(db, sub.user_id, "Subscription renewed", f"Your basket order {order.order_number} has been created.")
        db.commit(); return ok(order_json(db, order), "Recurring order created.", 201)
    except ValueError as exc:
        db.rollback(); return fail(str(exc))


@api.get("/delivery/<int:order_id>")
@auth_required
def track_delivery(order_id):
    db, user = get_session(), g.current_user
    order = db.get(Order, order_id)
    if not order: return fail("Order not found.", 404)
    if user.role == "consumer" and order.user_id != user.user_id: return fail("You cannot track this order.", 403)
    if user.role == "farmer":
        f = farmer_profile(db, user)
        if not f or not any(db.get(Product, i.product_id).farmer_id == f.farmer_id for i in order.items): return fail("You cannot track this order.", 403)
    delivery = order.delivery
    if not delivery: return fail("Delivery information is not available.", 404)
    from services import area_coordinates
    c = area_coordinates(order.city, order.pincode)
    route = {"origin": {"lat": 19.2900, "lng": 72.8500}, "customer": {"lat": c[0], "lng": c[1]}, "stops": []}
    try:
        stored = __import__("json").loads(delivery.route_json or "{}")
        if stored.get("stops"): route = {"origin": stored.get("origin"), "stops": stored.get("stops"), "customer": route["customer"]}
    except (ValueError, TypeError): pass
    return ok({"order": order_json(db, order), "delivery": {"delivery_id": delivery.delivery_id,
        "status": delivery.delivery_status, "route_status": delivery.route_status,
        "estimated_time": delivery.estimated_time, "route_sequence": delivery.route_sequence,
        "route_group": delivery.route_group}, "route": route})


@api.put("/delivery/<int:delivery_id>/status")
@roles("farmer", "admin")
def update_delivery_status(delivery_id):
    db, data, user = get_session(), body_json(), g.current_user
    delivery = db.get(Delivery, delivery_id)
    if not delivery: return fail("Delivery not found.", 404)
    order = db.get(Order, delivery.order_id)
    if not order: return fail("Order not found.", 404)
    status = str(data.get("status", ""))
    allowed = {"Placed", "Confirmed", "Preparing", "Out for Delivery", "Delivered", "Cancelled", "Rejected"}
    if status not in allowed: return fail("Choose a valid delivery status.")
    if user.role == "farmer":
        f = farmer_profile(db, user)
        if not f or not any(db.get(Product, i.product_id).farmer_id == f.farmer_id for i in order.items): return fail("You cannot update this delivery.", 403)
    current_status = order.order_status
    if current_status in ("Delivered", "Cancelled", "Rejected"):
        return fail("This order is already closed.", 409)
    transitions = {
        "Placed": {"Confirmed", "Cancelled", "Rejected"},
        "Confirmed": {"Preparing", "Cancelled"},
        "Preparing": {"Out for Delivery", "Cancelled"},
        "Out for Delivery": {"Delivered"},
    }
    if status not in transitions.get(current_status, set()):
        return fail(f"Order status cannot move from {current_status} to {status}.", 409)
    if status in ("Cancelled", "Rejected"):
        for item in order.items:
            product = db.get(Product, item.product_id); product.available_quantity += item.quantity
        cap = db.scalar(select(SlotCapacity).where(SlotCapacity.slot_id == order.delivery_slot_id, SlotCapacity.service_date == order.delivery_date))
        if cap: cap.current_orders = max(0, cap.current_orders - 1)
        if order.payment: order.payment.payment_status = "voided_demo" if order.payment.payment_method == "demo_online" else "cancelled"
    notify_order_status(db, order, status)
    if status == "Out for Delivery": delivery.delivery_person = str(data.get("delivery_person", "Farm2Home Route Team"))
    db.commit(); return ok(order_json(db, order), f"Order marked {status.lower()}.")


@api.get("/reviews/mine")
@roles("consumer")
def my_reviews():
    db, user = get_session(), g.current_user
    rows = db.scalars(select(Review).where(Review.user_id == user.user_id).order_by(desc(Review.created_at))).all()
    return ok([{"review_id": r.review_id, "product_id": r.product_id, "order_id": r.order_id,
                "rating": r.rating, "comment": r.comment, "created_at": r.created_at.isoformat()} for r in rows])


@api.get("/reviews/<int:product_id>")
def product_reviews(product_id):
    db = get_session()
    rows = db.scalars(select(Review).where(Review.product_id == product_id).order_by(desc(Review.created_at))).all()
    items = []
    for r in rows:
        u = db.get(User, r.user_id)
        items.append({"review_id": r.review_id, "product_id": r.product_id, "user_id": r.user_id,
                      "user_name": u.full_name if u else "Customer", "rating": r.rating,
                      "comment": r.comment, "created_at": r.created_at.isoformat()})
    avg = db.scalar(select(func.avg(Review.rating)).where(Review.product_id == product_id)) or 0
    return ok({"reviews": items, "average_rating": round(float(avg), 1), "review_count": len(items)})


@api.post("/reviews")
@roles("consumer")
def add_review():
    db, data, user = get_session(), body_json(), g.current_user
    try: pid, rating = int(data.get("product_id")), int(data.get("rating")); oid = int(data.get("order_id"))
    except (ValueError, TypeError): return fail("Choose a product, delivered order and rating.")
    if rating < 1 or rating > 5: return fail("Rating must be from 1 to 5.")
    product, order = db.get(Product, pid), db.get(Order, oid)
    if not product or not order or order.user_id != user.user_id or order.order_status != "Delivered": return fail("Reviews are available only for products in your delivered orders.", 403)
    if not db.scalar(select(OrderItem.order_item_id).where(OrderItem.order_id == oid, OrderItem.product_id == pid)): return fail("That product was not included in this order.", 403)
    existing = db.scalar(select(Review).where(Review.user_id == user.user_id, Review.product_id == pid))
    if existing: return fail("You have already reviewed this product. You can edit your review.", 409)
    review = Review(user_id=user.user_id, product_id=pid, order_id=oid, rating=rating,
                    comment=str(data.get("comment", "")).strip()[:1000])
    db.add(review); db.commit()
    return ok({"review_id": review.review_id, "rating": review.rating, "comment": review.comment}, "Thank you for reviewing this product.", 201)


@api.put("/reviews/<int:review_id>")
@roles("consumer")
def edit_review(review_id):
    db, data, user = get_session(), body_json(), g.current_user
    review = db.get(Review, review_id)
    if not review: return fail("Review not found.", 404)
    if review.user_id != user.user_id: return fail("You can only edit your own review.", 403)
    try: rating = int(data.get("rating", review.rating))
    except (ValueError, TypeError): return fail("Rating must be from 1 to 5.")
    if rating < 1 or rating > 5: return fail("Rating must be from 1 to 5.")
    review.rating = rating; review.comment = str(data.get("comment", review.comment)).strip()[:1000]
    db.commit(); return ok({}, "Review updated.")


@api.delete("/reviews/<int:review_id>")
@roles("consumer")
def delete_review(review_id):
    db, user = get_session(), g.current_user; review = db.get(Review, review_id)
    if not review: return fail("Review not found.", 404)
    if review.user_id != user.user_id: return fail("You can only delete your own review.", 403)
    db.delete(review); db.commit(); return ok({}, "Review deleted.")


@api.get("/notifications")
@roles("consumer", "farmer", "admin")
def notifications():
    db, user = get_session(), g.current_user
    rows = db.scalars(select(Notification).where(Notification.user_id == user.user_id).order_by(desc(Notification.created_at)).limit(100)).all()
    return ok({"unread_count": sum(not n.is_read for n in rows), "items": [{"notification_id": n.notification_id,
        "title": n.title, "message": n.message, "is_read": n.is_read,
        "created_at": n.created_at.isoformat()} for n in rows]})


@api.put("/notifications/<int:notification_id>/read")
@auth_required
def notification_read(notification_id):
    db, user = get_session(), g.current_user; n = db.get(Notification, notification_id)
    if not n or (user.role != "admin" and n.user_id != user.user_id): return fail("Notification not found.", 404)
    n.is_read = True; db.commit(); return ok({}, "Notification marked read.")


@api.put("/notifications/read-all")
@auth_required
def notifications_read_all():
    db, user = get_session(), g.current_user
    rows = db.scalars(select(Notification).where(Notification.user_id == user.user_id, Notification.is_read.is_(False))).all()
    for n in rows: n.is_read = True
    db.commit(); return ok({"updated": len(rows)}, "Notifications marked read.")


@api.get("/loyalty")
@roles("consumer")
def loyalty_summary():
    db, user = get_session(), g.current_user
    loyalty = db.scalar(select(LoyaltyPoint).where(LoyaltyPoint.user_id == user.user_id))
    events = db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.user_id == user.user_id).order_by(desc(LoyaltyTransaction.created_at)).limit(30)).all()
    return ok({"points": loyalty.points if loyalty else 0, "redemption_rule": "100 points = ₹10 at checkout",
        "earning_rule": "₹100 delivered order = 10 points; active subscribers earn +10 bonus points",
        "history": [{"points_delta": x.points_delta, "note": x.note, "created_at": x.created_at.isoformat()} for x in events]})


@api.get("/consumer/dashboard")
@roles("consumer")
def consumer_dashboard():
    db, user = get_session(), g.current_user
    recent_orders = db.scalars(select(Order).where(Order.user_id == user.user_id)
                               .order_by(desc(Order.created_at)).limit(20)).all()
    subscriptions = db.scalars(select(Subscription).where(
        Subscription.user_id == user.user_id, Subscription.status == "active")
        .order_by(Subscription.next_delivery_date)).all()
    loyalty = db.scalar(select(LoyaltyPoint).where(LoyaltyPoint.user_id == user.user_id))
    totals, counts = {}, {}
    for order in db.scalars(select(Order).where(Order.user_id == user.user_id)).all():
        key = order.created_at.strftime("%Y-%m") if order.created_at else "unknown"
        totals[key] = totals.get(key, 0) + float(order.total_amount)
        counts[key] = counts.get(key, 0) + 1
    months = sorted(totals)[-6:]
    labels = [datetime.strptime(month, "%Y-%m").strftime("%b %Y") if month != "unknown" else "Unknown" for month in months]
    return ok({"total_orders": db.scalar(select(func.count(Order.order_id)).where(Order.user_id == user.user_id)) or 0,
        "active_subscriptions": len(subscriptions),
        "next_delivery": subscriptions[0].next_delivery_date.isoformat() if subscriptions else (recent_orders[0].delivery_date.isoformat() if recent_orders else None),
        "loyalty_points": loyalty.points if loyalty else 0,
        "recent_orders": [order_json(db, order) for order in recent_orders[:5]],
        "spending_chart": {"labels": labels, "values": [round(totals[month], 2) for month in months]},
        "orders_chart": {"labels": labels, "values": [counts[month] for month in months]}})


@api.get("/farmer/dashboard")
@roles("farmer")
def farmer_dashboard():
    db, user = get_session(), g.current_user
    farm = farmer_profile(db, user)
    if not farm:
        return fail("Farm profile not found.", 404)
    products = db.scalars(select(Product).where(Product.farmer_id == farm.farmer_id, Product.status == "active")).all()
    order_ids = select(OrderItem.order_id).join(Product).where(Product.farmer_id == farm.farmer_id)
    orders = db.scalars(select(Order).where(Order.order_id.in_(order_ids)).order_by(desc(Order.created_at))).unique().all()
    gross, monthly, product_sales = 0.0, {}, {}
    for order in orders:
        key = order.created_at.strftime("%Y-%m") if order.created_at else "unknown"
        for item in order.items:
            product = db.get(Product, item.product_id)
            if product and product.farmer_id == farm.farmer_id:
                value = float(item.price_at_purchase * item.quantity)
                gross += value
                monthly[key] = monthly.get(key, 0) + value
                product_sales[product.product_name] = product_sales.get(product.product_name, 0) + item.quantity
    subscription_ids = select(SubscriptionItem.subscription_id).join(Product).where(Product.farmer_id == farm.farmer_id)
    active_subscriptions = db.scalar(select(func.count(Subscription.subscription_id)).where(
        Subscription.status == "active", Subscription.subscription_id.in_(subscription_ids))) or 0
    farm_subscriptions = db.scalars(select(Subscription).join(SubscriptionItem)
        .join(Product).where(Product.farmer_id == farm.farmer_id)
        .order_by(Subscription.next_delivery_date).distinct()).unique().all()
    month_keys = sorted(monthly)[-6:]
    month_labels = [datetime.strptime(month, "%Y-%m").strftime("%b %Y") if month != "unknown" else "Unknown" for month in month_keys]
    popular_products = sorted(product_sales.items(), key=lambda entry: (-entry[1], entry[0]))[:8]
    subscription_rows = [{"subscription_id": sub.subscription_id, "plan_name": sub.plan_name,
        "frequency": sub.frequency, "next_delivery_date": sub.next_delivery_date.isoformat(),
        "status": sub.status, "city": sub.city, "pincode": sub.pincode,
        "delivery_slot": sub.delivery_slot,
        "items": [{"product_name": item.product.product_name, "quantity": item.quantity}
                  for item in sub.items if item.product and item.product.farmer_id == farm.farmer_id]}
        for sub in farm_subscriptions]
    return ok({"farm": {"farm_name": farm.farm_name, "verification_status": farm.verification_status},
        "total_sales": round(gross, 2), "today_orders": sum(order.delivery_date == date.today() for order in orders),
        "active_subscriptions": active_subscriptions,
        "pending_orders": sum(order.order_status in ("Placed", "Confirmed") for order in orders),
        "available_products": len(products), "estimated_revenue": round(gross * 0.9, 2),
        "products": [product_json(db, product) for product in products],
        "recent_orders": [order_json(db, order) for order in orders[:10]],
        "subscriptions": subscription_rows,
        "sales_chart": {"labels": month_labels, "values": [round(monthly[month], 2) for month in month_keys]},
        "product_chart": {"labels": [row[0] for row in popular_products], "values": [row[1] for row in popular_products]}})


@api.get("/admin/dashboard")
@roles("admin")
def admin_dashboard():
    db = get_session()
    count_values = db.execute(select(
        select(func.count(User.user_id)).scalar_subquery().label("total_users"),
        select(func.count(User.user_id)).where(User.role == "consumer").scalar_subquery().label("total_consumers"),
        select(func.count(Farmer.farmer_id)).scalar_subquery().label("total_farmers"),
        select(func.count(Product.product_id)).scalar_subquery().label("total_products"),
        select(func.count(Order.order_id)).scalar_subquery().label("total_orders"),
        select(func.count(Subscription.subscription_id)).where(Subscription.status == "active").scalar_subquery().label("active_subscriptions"),
        select(func.count(Delivery.delivery_id)).where(Delivery.delivery_status.not_in(["Delivered", "Cancelled", "Rejected"])).scalar_subquery().label("pending_deliveries"),
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.payment_status.in_(["paid", "pending"])).scalar_subquery().label("total_revenue"))).mappings().one()
    totals = dict(count_values)
    order_chart_rows = db.execute(select(Order.created_at, Order.total_amount)).all()
    subscription_dates = db.scalars(select(Subscription.created_at)).all()
    deliveries_by_status = db.execute(select(Delivery.delivery_status, func.count(Delivery.delivery_id))
                                      .group_by(Delivery.delivery_status)).all()
    categories = db.execute(select(Category.category_name, func.count(Product.product_id))
                            .outerjoin(Product).group_by(Category.category_id, Category.category_name)).all()
    recent_orders = db.scalars(select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product),
        selectinload(Order.delivery)).order_by(desc(Order.created_at)).limit(8)).all()
    recent_farmers = db.scalars(select(Farmer).options(selectinload(Farmer.user))
                                .order_by(desc(Farmer.created_at)).limit(8)).all()
    pending_farmers = db.scalars(select(Farmer).options(selectinload(Farmer.user))
                                 .where(Farmer.verification_status == "pending")
                                 .order_by(desc(Farmer.created_at)).limit(8)).all()
    monthly_revenue, monthly_orders, monthly_subscriptions = {}, {}, {}
    for created_at, amount in order_chart_rows:
        key = created_at.strftime("%Y-%m") if created_at else "unknown"
        monthly_revenue[key] = monthly_revenue.get(key, 0) + float(amount)
        monthly_orders[key] = monthly_orders.get(key, 0) + 1
    for created_at in subscription_dates:
        key = created_at.strftime("%Y-%m") if created_at else "unknown"
        monthly_subscriptions[key] = monthly_subscriptions.get(key, 0) + 1
    month_keys = sorted(monthly_revenue)[-6:]
    month_labels = [datetime.strptime(month, "%Y-%m").strftime("%b %Y") if month != "unknown" else "Unknown" for month in month_keys]
    sub_month_keys = sorted(monthly_subscriptions)[-6:]
    sub_month_labels = [datetime.strptime(month, "%Y-%m").strftime("%b %Y") if month != "unknown" else "Unknown" for month in sub_month_keys]
    def farmer_json(farm):
        return {"farmer_id": farm.farmer_id, "farm_name": farm.farm_name,
                "farm_location": farm.farm_location, "verification_status": farm.verification_status,
                "user": user_json(farm.user)}
    return ok({**totals, "total_revenue": float(totals["total_revenue"]),
        "recent_orders": [order_json(db, order) for order in recent_orders],
        "recent_farmers": [farmer_json(farm) for farm in recent_farmers],
        "pending_farmers": [farmer_json(farm) for farm in pending_farmers],
        "revenue_chart": {"labels": month_labels, "values": [round(monthly_revenue[month], 2) for month in month_keys]},
        "orders_chart": {"labels": month_labels, "values": [monthly_orders[month] for month in month_keys]},
        "subscription_chart": {"labels": sub_month_labels, "values": [monthly_subscriptions[month] for month in sub_month_keys]},
        "category_chart": {"labels": [row[0] for row in categories], "values": [row[1] for row in categories]},
        "delivery_chart": {"labels": [row[0] for row in deliveries_by_status], "values": [row[1] for row in deliveries_by_status]}})


@api.get("/admin/users")
@roles("admin")
def admin_users():
    db = get_session(); rows = db.scalars(select(User).order_by(desc(User.created_at)).limit(200)).all()
    return ok([user_json(u) | {"is_active": u.is_active, "created_at": u.created_at.isoformat()} for u in rows])


@api.put("/admin/users/<int:user_id>/status")
@roles("admin")
def admin_user_status(user_id):
    db, data = get_session(), body_json(); user = db.get(User, user_id)
    if not user: return fail("User not found.", 404)
    if user.user_id == g.current_user.user_id: return fail("You cannot deactivate your own admin account.", 400)
    user.is_active = bool(data.get("is_active", False)); db.commit()
    return ok(user_json(user), "User status updated.")


@api.get("/admin/farmers")
@roles("admin")
def admin_farmers():
    db = get_session(); rows = db.scalars(select(Farmer).order_by(Farmer.verification_status, Farmer.farm_name)).all()
    return ok([{ "farmer_id": f.farmer_id, "farm_name": f.farm_name, "farm_location": f.farm_location,
        "verification_status": f.verification_status, "farming_method": f.farming_method,
        "user": user_json(db.get(User, f.user_id))} for f in rows])


@api.put("/admin/farmers/<int:farmer_id>")
@roles("admin")
def admin_farmer_decision(farmer_id):
    db, data = get_session(), body_json(); f = db.get(Farmer, farmer_id)
    if not f: return fail("Farmer not found.", 404)
    decision = str(data.get("verification_status", ""))
    if decision not in ("approved", "rejected", "pending"): return fail("Choose approved, rejected or pending.")
    f.verification_status = decision
    notify(db, f.user_id, "Farm profile reviewed", f"Your farm application was {decision}.")
    db.commit(); return ok({"farmer_id": f.farmer_id, "verification_status": f.verification_status}, "Farmer status updated.")


@api.get("/admin/products")
@roles("admin")
def admin_products():
    db = get_session()
    review_stats = select(Review.product_id.label("product_id"), func.avg(Review.rating).label("average_rating"),
                          func.count(Review.review_id).label("review_count")).group_by(Review.product_id).subquery()
    stmt = select(Product, Farmer, User, Category, review_stats.c.average_rating, review_stats.c.review_count)        .join(Farmer, Product.farmer_id == Farmer.farmer_id)        .join(User, Farmer.user_id == User.user_id)        .join(Category, Product.category_id == Category.category_id)        .outerjoin(review_stats, review_stats.c.product_id == Product.product_id)        .order_by(Product.product_name).limit(300)
    return ok([product_summary_json(*row) for row in db.execute(stmt).all()])


@api.get("/admin/subscriptions")
@roles("admin")
def admin_subscriptions():
    db = get_session()
    rows = db.scalars(select(Subscription).options(
        selectinload(Subscription.user),
        selectinload(Subscription.items).selectinload(SubscriptionItem.product))
        .order_by(desc(Subscription.created_at)).limit(300)).all()
    return ok([subscription_json(sub) | {"user": user_json(sub.user)} for sub in rows])


@api.get("/admin/categories")
@roles("admin")
def admin_categories():
    db = get_session()
    return ok([{"category_id": c.category_id, "category_name": c.category_name,
                "description": c.description} for c in db.scalars(select(Category).order_by(Category.category_name)).all()])


@api.post("/admin/categories")
@roles("admin")
def admin_create_category():
    db, data = get_session(), body_json()
    name = str(data.get("category_name", "")).strip()
    if not name or len(name) > 80:
        return fail("Category name is required and must be 80 characters or fewer.")
    category = Category(category_name=name, description=str(data.get("description", "")).strip()[:255])
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return fail("A category with that name already exists.", 409)
    return ok({"category_id": category.category_id, "category_name": category.category_name,
               "description": category.description}, "Category created.", 201)


@api.put("/admin/categories/<int:category_id>")
@roles("admin")
def admin_update_category(category_id):
    db, data = get_session(), body_json()
    category = db.get(Category, category_id)
    if not category:
        return fail("Category not found.", 404)
    name = str(data.get("category_name", category.category_name)).strip()
    if not name or len(name) > 80:
        return fail("Category name is required and must be 80 characters or fewer.")
    category.category_name = name
    category.description = str(data.get("description", category.description)).strip()[:255]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return fail("A category with that name already exists.", 409)
    return ok({"category_id": category.category_id, "category_name": category.category_name,
               "description": category.description}, "Category updated.")


@api.delete("/admin/categories/<int:category_id>")
@roles("admin")
def admin_delete_category(category_id):
    db = get_session()
    category = db.get(Category, category_id)
    if not category:
        return fail("Category not found.", 404)
    in_use = db.scalar(select(func.count(Product.product_id)).where(Product.category_id == category_id)) or 0
    if in_use:
        return fail("This category is in use; move or remove its products first.", 409)
    db.delete(category)
    db.commit()
    return ok({}, "Category deleted.")


@api.get("/admin/deliveries")
@roles("admin")
def admin_deliveries():
    db = get_session(); rows = db.scalars(select(Delivery).order_by(Delivery.delivery_date, Delivery.delivery_slot, Delivery.route_sequence).limit(300)).all()
    return ok([{ "delivery_id": d.delivery_id, "order": order_json(db, db.get(Order, d.order_id), False),
        "delivery_status": d.delivery_status, "route_status": d.route_status,
        "route_sequence": d.route_sequence, "estimated_time": d.estimated_time, "route_group": d.route_group} for d in rows])


@api.get("/admin/slots")
@roles("admin")
def admin_slots():
    db = get_session(); rows = db.scalars(select(DeliverySlot).order_by(DeliverySlot.slot_id)).all()
    return ok([{ "slot_id": s.slot_id, "slot_name": s.slot_name,
        "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
        "max_orders": s.max_orders, "status": s.status} for s in rows])


@api.put("/admin/slots/<int:slot_id>")
@roles("admin")
def admin_update_slot(slot_id):
    db, data = get_session(), body_json(); slot = db.get(DeliverySlot, slot_id)
    if not slot: return fail("Delivery slot not found.", 404)
    if "max_orders" in data:
        try: value = int(data["max_orders"])
        except (TypeError, ValueError): return fail("Capacity must be a positive whole number.")
        if value < 1: return fail("Capacity must be at least one.")
        slot.max_orders = value
    if "status" in data:
        if data["status"] not in ("active", "inactive"): return fail("Status must be active or inactive.")
        slot.status = data["status"]
    db.commit(); return ok({"slot_id": slot.slot_id, "slot_name": slot.slot_name, "max_orders": slot.max_orders, "status": slot.status}, "Slot updated.")


@api.post("/admin/run-subscriptions")
@roles("admin")
def admin_run_subscriptions():
    db = get_session()
    try:
        result = process_due_subscriptions(db, date.today()); db.commit()
        return ok(result, "Subscription renewal job completed.")
    except SQLAlchemyError:
        db.rollback(); return fail("Renewal job failed; no changes were committed.", 500)


@api.errorhandler(404)
def api_not_found(_error):
    return fail("API endpoint not found.", 404)


@api.errorhandler(SQLAlchemyError)
def database_error(_error):
    try: get_session().rollback()
    except Exception: pass
    current_app.logger.exception("Database operation failed")
    return fail("A database operation failed. Please try again.", 500)
