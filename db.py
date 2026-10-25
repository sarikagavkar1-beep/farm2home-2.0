"""Small SQLAlchemy 2.x database layer for Farm2Home."""
from __future__ import annotations

import os
from pathlib import Path
from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def init_database(app):
    """Bind SQLAlchemy to DATABASE_URL (MySQL) or a local demo SQLite file."""
    global _engine, _SessionLocal
    url = app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{Path(app.instance_path) / 'farm2home.sqlite3'}"
    parsed_url = make_url(url)
    # SQLAlchemy's bare mysql:// defaults to MySQLdb; this project deliberately
    # installs PyMySQL instead, so normalize only the driver's dialect name.
    if parsed_url.get_backend_name() == "mysql" and parsed_url.get_driver_name() in (None, "mysqldb"):
        parsed_url = parsed_url.set(drivername="mysql+pymysql")
    connect_args = {}
    if parsed_url.get_backend_name() == "mysql" and "ssl" in parsed_url.query:
        # Provider DSNs encode `ssl` as a URL string; PyMySQL requires an SSL
        # options mapping instead. Preserve an explicit disable, otherwise use
        # TLS and validate the certificate chain against the system trust store.
        query = dict(parsed_url.query)
        ssl_mode = str(query.pop("ssl") or "").strip().lower()
        parsed_url = parsed_url.set(query=query)
        if ssl_mode not in ("", "0", "false", "no", "off", "disabled", "disable", "none"):
            verify_host = any(token in ssl_mode for token in ("verify", "identity", "strict"))
            connect_args["ssl"] = {"verify_mode": "CERT_REQUIRED", "check_hostname": verify_host}
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    if parsed_url.get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False}
        options = {}
    if connect_args:
        options["connect_args"] = connect_args
    _engine = create_engine(parsed_url, future=True, **options)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False, future=True)
    app.extensions["farm2home_engine"] = _engine
    app.extensions["farm2home_sessionmaker"] = _SessionLocal
    return _engine


def get_session() -> Session:
    if "farm2home_db" not in g:
        maker = current_app.extensions["farm2home_sessionmaker"]
        g.farm2home_db = maker()
    return g.farm2home_db


def close_session(_error=None):
    session = g.pop("farm2home_db", None)
    if session is not None:
        session.close()


def create_schema(app):
    from models import (  # noqa: F401 — register all metadata before create_all
        Cart, CartItem, Category, Delivery, DeliverySlot, Farmer, LoyaltyPoint,
        LoyaltyTransaction, Notification, Order, OrderItem, Payment, Product,
        Review, SlotCapacity, Subscription, SubscriptionItem, SubscriptionPlan, User,
    )
    engine = app.extensions["farm2home_engine"]
    Base.metadata.create_all(engine)


def session_factory(app):
    return app.extensions["farm2home_sessionmaker"]
