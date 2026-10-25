"""Farm2Home relational models. All monetary values use fixed-precision decimals."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, Text, Time, UniqueConstraint, Index, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('consumer','farmer','admin')", name="ck_users_role"),
        CheckConstraint("phone IS NULL OR length(phone) = 10", name="ck_users_phone_length"),
        Index("ix_users_role_created", "role", "created_at"),
    )
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(10), unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="consumer")
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(80))
    pincode: Mapped[str | None] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    farmer: Mapped[Farmer | None] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    cart: Mapped[Cart | None] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    loyalty: Mapped[LoyaltyPoint | None] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user")


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (CheckConstraint("verification_status IN ('pending','approved','rejected')", name="ck_farmer_status"),)
    farmer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    farm_name: Mapped[str] = mapped_column(String(140), nullable=False)
    farm_location: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    farming_method: Mapped[str] = mapped_column(String(100), default="Seasonal local farming")
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), default=19.2900, nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), default=72.8500, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="farmer")
    products: Mapped[list[Product]] = relationship(back_populates="farmer")


class Category(Base):
    __tablename__ = "categories"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price"),
        CheckConstraint("available_quantity >= 0", name="ck_product_stock"),
        Index("ix_product_status_category", "status", "category_id"),
    )
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.farmer_id", ondelete="RESTRICT"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.category_id", ondelete="RESTRICT"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False, default="kg")
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    organic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    farmer: Mapped[Farmer] = relationship(back_populates="products")
    category: Mapped[Category] = relationship(back_populates="products")
    reviews: Mapped[list[Review]] = relationship(back_populates="product")


class Cart(Base):
    __tablename__ = "carts"
    cart_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="cart")
    items: Mapped[list[CartItem]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity"),
    )
    cart_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.cart_id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class DeliverySlot(Base):
    __tablename__ = "delivery_slots"
    slot_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    start_time: Mapped[object] = mapped_column(Time, nullable=False)
    end_time: Mapped[object] = mapped_column(Time, nullable=False)
    max_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    capacities: Mapped[list[SlotCapacity]] = relationship(back_populates="slot", cascade="all, delete-orphan")


class SlotCapacity(Base):
    __tablename__ = "slot_capacities"
    __table_args__ = (UniqueConstraint("slot_id", "service_date", name="uq_slot_date"), CheckConstraint("current_orders >= 0", name="ck_capacity_nonnegative"))
    capacity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("delivery_slots.slot_id", ondelete="CASCADE"), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slot: Mapped[DeliverySlot] = relationship(back_populates="capacities")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    plan_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    delivery_slot: Mapped[str] = mapped_column(String(40), default="Morning", nullable=False)
    bonus_points: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (CheckConstraint("status IN ('active','paused','cancelled')", name="ck_subscription_status"),)
    subscription_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.plan_id", ondelete="RESTRICT"), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_generated_for: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    delivery_slot: Mapped[str] = mapped_column(String(40), default="Morning", nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="subscriptions")
    plan: Mapped[SubscriptionPlan] = relationship(back_populates="subscriptions")
    items: Mapped[list[SubscriptionItem]] = relationship(back_populates="subscription", cascade="all, delete-orphan")


class SubscriptionItem(Base):
    __tablename__ = "subscription_items"
    __table_args__ = (UniqueConstraint("subscription_id", "product_id", name="uq_subscription_product"), CheckConstraint("quantity > 0", name="ck_subscription_item_quantity"))
    subscription_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subscription: Mapped[Subscription] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_order_total"),
        CheckConstraint("order_status IN ('Placed','Confirmed','Preparing','Out for Delivery','Delivered','Cancelled','Rejected')", name="ck_order_status"),
        Index("ix_order_date_status", "delivery_date", "order_status"),
    )
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.subscription_id", ondelete="SET NULL"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    loyalty_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_slot: Mapped[str] = mapped_column(String(40), nullable=False)
    delivery_slot_id: Mapped[int] = mapped_column(ForeignKey("delivery_slots.slot_id", ondelete="RESTRICT"), nullable=False)
    order_status: Mapped[str] = mapped_column(String(32), default="Placed", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")
    delivery: Mapped[Delivery | None] = relationship(back_populates="order", cascade="all, delete-orphan", uselist=False)
    payment: Mapped[Payment | None] = relationship(back_populates="order", cascade="all, delete-orphan", uselist=False)
    slot: Mapped[DeliverySlot] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_order_product"), CheckConstraint("quantity > 0", name="ck_order_item_quantity"), CheckConstraint("price_at_purchase >= 0", name="ck_order_item_price"))
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (CheckConstraint("delivery_status IN ('Placed','Confirmed','Preparing','Out for Delivery','Delivered','Cancelled','Rejected')", name="ck_delivery_status"),)
    delivery_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id", ondelete="CASCADE"), unique=True, nullable=False)
    delivery_person: Mapped[str | None] = mapped_column(String(100))
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_slot: Mapped[str] = mapped_column(String(40), nullable=False)
    route_status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), default="Placed", nullable=False)
    current_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    current_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    estimated_time: Mapped[str | None] = mapped_column(String(80))
    route_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    route_group: Mapped[str] = mapped_column(String(120), default="")
    route_json: Mapped[str] = mapped_column(Text, default="[]")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    order: Mapped[Order] = relationship(back_populates="delivery")


class Payment(Base):
    __tablename__ = "payments"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id", ondelete="CASCADE"), unique=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    order: Mapped[Order] = relationship(back_populates="payment")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"), UniqueConstraint("user_id", "product_id", name="uq_review_user_product"))
    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped[User] = relationship()
    product: Mapped[Product] = relationship(back_populates="reviews")


class LoyaltyPoint(Base):
    __tablename__ = "loyalty_points"
    loyalty_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    user: Mapped[User] = relationship(back_populates="loyalty")


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_loyalty_event"), CheckConstraint("points_delta <> 0", name="ck_loyalty_delta"))
    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    points_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    event_key: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)
    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    message: Mapped[str] = mapped_column(String(600), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
