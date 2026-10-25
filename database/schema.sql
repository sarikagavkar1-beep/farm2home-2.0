-- Farm2Home MySQL 8 schema. Import into a database named farm2home.
CREATE DATABASE IF NOT EXISTS farm2home CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE farm2home;

CREATE TABLE IF NOT EXISTS users (
  user_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  phone VARCHAR(10) NOT NULL,
  role ENUM('consumer','farmer','admin') NOT NULL DEFAULT 'consumer',
  address VARCHAR(255) NULL,
  city VARCHAR(80) NULL,
  pincode VARCHAR(6) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email),
  UNIQUE KEY uq_users_phone (phone),
  KEY ix_users_role_created (role, created_at),
  CONSTRAINT ck_users_phone_length CHECK (CHAR_LENGTH(phone) = 10),
  CONSTRAINT ck_users_pincode_length CHECK (pincode IS NULL OR pincode = '' OR CHAR_LENGTH(pincode) = 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS farmers (
  farmer_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  farm_name VARCHAR(140) NOT NULL,
  farm_location VARCHAR(160) NOT NULL,
  description TEXT NOT NULL,
  farming_method VARCHAR(100) NOT NULL DEFAULT 'Seasonal local farming',
  verification_status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  latitude DECIMAL(9,6) NOT NULL DEFAULT 19.290000,
  longitude DECIMAL(9,6) NOT NULL DEFAULT 72.850000,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (farmer_id),
  UNIQUE KEY uq_farmers_user (user_id),
  CONSTRAINT fk_farmers_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS categories (
  category_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_name VARCHAR(80) NOT NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  PRIMARY KEY (category_id),
  UNIQUE KEY uq_categories_name (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
  product_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  farmer_id INT UNSIGNED NOT NULL,
  category_id INT UNSIGNED NOT NULL,
  product_name VARCHAR(140) NOT NULL,
  description TEXT NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  unit VARCHAR(24) NOT NULL DEFAULT 'kg',
  available_quantity INT NOT NULL DEFAULT 0,
  organic BOOLEAN NOT NULL DEFAULT FALSE,
  image_url VARCHAR(500) NOT NULL DEFAULT '',
  status ENUM('active','inactive') NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id),
  KEY ix_products_farmer (farmer_id),
  KEY ix_products_category (category_id),
  KEY ix_product_status_category (status, category_id),
  CONSTRAINT ck_product_price CHECK (price >= 0),
  CONSTRAINT ck_product_stock CHECK (available_quantity >= 0),
  CONSTRAINT fk_products_farmer FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id) ON DELETE RESTRICT,
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS carts (
  cart_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (cart_id),
  UNIQUE KEY uq_carts_user (user_id),
  CONSTRAINT fk_carts_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cart_items (
  cart_item_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  cart_id INT UNSIGNED NOT NULL,
  product_id INT UNSIGNED NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  PRIMARY KEY (cart_item_id),
  UNIQUE KEY uq_cart_product (cart_id, product_id),
  CONSTRAINT ck_cart_item_quantity CHECK (quantity > 0),
  CONSTRAINT fk_cart_items_cart FOREIGN KEY (cart_id) REFERENCES carts(cart_id) ON DELETE CASCADE,
  CONSTRAINT fk_cart_items_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS delivery_slots (
  slot_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  slot_name VARCHAR(40) NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  max_orders INT NOT NULL DEFAULT 20,
  status ENUM('active','inactive') NOT NULL DEFAULT 'active',
  PRIMARY KEY (slot_id),
  UNIQUE KEY uq_delivery_slots_name (slot_name),
  CONSTRAINT ck_delivery_slot_capacity CHECK (max_orders > 0),
  CONSTRAINT ck_delivery_slot_times CHECK (end_time > start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slot_capacities (
  capacity_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  slot_id INT UNSIGNED NOT NULL,
  service_date DATE NOT NULL,
  current_orders INT NOT NULL DEFAULT 0,
  PRIMARY KEY (capacity_id),
  UNIQUE KEY uq_slot_date (slot_id, service_date),
  CONSTRAINT ck_capacity_nonnegative CHECK (current_orders >= 0),
  CONSTRAINT fk_slot_capacities_slot FOREIGN KEY (slot_id) REFERENCES delivery_slots(slot_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subscription_plans (
  plan_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  plan_name VARCHAR(120) NOT NULL,
  frequency ENUM('weekly','biweekly','monthly') NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  discount_percent INT NOT NULL DEFAULT 5,
  description TEXT NOT NULL,
  delivery_slot VARCHAR(40) NOT NULL DEFAULT 'Morning',
  bonus_points INT NOT NULL DEFAULT 10,
  PRIMARY KEY (plan_id),
  UNIQUE KEY uq_subscription_plan_name (plan_name),
  CONSTRAINT ck_plan_price CHECK (price > 0),
  CONSTRAINT ck_plan_discount CHECK (discount_percent BETWEEN 0 AND 100),
  CONSTRAINT ck_plan_bonus CHECK (bonus_points >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subscriptions (
  subscription_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  plan_id INT UNSIGNED NOT NULL,
  plan_name VARCHAR(120) NOT NULL,
  frequency ENUM('weekly','biweekly','monthly') NOT NULL,
  start_date DATE NOT NULL,
  next_delivery_date DATE NOT NULL,
  last_generated_for DATE NULL,
  amount DECIMAL(10,2) NOT NULL,
  discount_percent INT NOT NULL DEFAULT 5,
  status ENUM('active','paused','cancelled') NOT NULL DEFAULT 'active',
  delivery_slot VARCHAR(40) NOT NULL DEFAULT 'Morning',
  delivery_address VARCHAR(255) NOT NULL,
  city VARCHAR(80) NOT NULL,
  pincode VARCHAR(6) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subscription_id),
  KEY ix_subscriptions_user (user_id),
  KEY ix_subscriptions_next_delivery (next_delivery_date),
  CONSTRAINT ck_subscription_discount CHECK (discount_percent BETWEEN 0 AND 100),
  CONSTRAINT ck_subscription_pincode CHECK (CHAR_LENGTH(pincode) = 6),
  CONSTRAINT fk_subscriptions_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_subscriptions_plan FOREIGN KEY (plan_id) REFERENCES subscription_plans(plan_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subscription_items (
  subscription_item_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  subscription_id INT UNSIGNED NOT NULL,
  product_id INT UNSIGNED NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  PRIMARY KEY (subscription_item_id),
  UNIQUE KEY uq_subscription_product (subscription_id, product_id),
  CONSTRAINT ck_subscription_item_quantity CHECK (quantity > 0),
  CONSTRAINT fk_subscription_items_subscription FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
  CONSTRAINT fk_subscription_items_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
  order_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_number VARCHAR(24) NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  subscription_id INT UNSIGNED NULL,
  subtotal DECIMAL(10,2) NOT NULL DEFAULT 0,
  delivery_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
  discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  loyalty_used INT NOT NULL DEFAULT 0,
  total_amount DECIMAL(10,2) NOT NULL,
  delivery_address VARCHAR(255) NOT NULL,
  city VARCHAR(80) NOT NULL,
  pincode VARCHAR(6) NOT NULL,
  delivery_date DATE NOT NULL,
  delivery_slot VARCHAR(40) NOT NULL,
  delivery_slot_id INT UNSIGNED NOT NULL,
  order_status ENUM('Placed','Confirmed','Preparing','Out for Delivery','Delivered','Cancelled','Rejected') NOT NULL DEFAULT 'Placed',
  payment_status ENUM('pending','paid','failed','cancelled','voided_demo') NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (order_id),
  UNIQUE KEY uq_orders_number (order_number),
  KEY ix_orders_user (user_id),
  KEY ix_order_date_status (delivery_date, order_status),
  CONSTRAINT ck_order_total CHECK (total_amount >= 0),
  CONSTRAINT ck_order_subtotal CHECK (subtotal >= 0),
  CONSTRAINT ck_order_pincode CHECK (CHAR_LENGTH(pincode) = 6),
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_orders_subscription FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id) ON DELETE SET NULL,
  CONSTRAINT fk_orders_slot FOREIGN KEY (delivery_slot_id) REFERENCES delivery_slots(slot_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id INT UNSIGNED NOT NULL,
  product_id INT UNSIGNED NOT NULL,
  quantity INT NOT NULL,
  price_at_purchase DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (order_item_id),
  UNIQUE KEY uq_order_product (order_id, product_id),
  CONSTRAINT ck_order_item_quantity CHECK (quantity > 0),
  CONSTRAINT ck_order_item_price CHECK (price_at_purchase >= 0),
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deliveries (
  delivery_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id INT UNSIGNED NOT NULL,
  delivery_person VARCHAR(100) NULL,
  delivery_date DATE NOT NULL,
  delivery_slot VARCHAR(40) NOT NULL,
  route_status VARCHAR(30) NOT NULL DEFAULT 'planned',
  delivery_status ENUM('Placed','Confirmed','Preparing','Out for Delivery','Delivered','Cancelled','Rejected') NOT NULL DEFAULT 'Placed',
  current_latitude DECIMAL(9,6) NULL,
  current_longitude DECIMAL(9,6) NULL,
  estimated_time VARCHAR(80) NULL,
  route_sequence INT NOT NULL DEFAULT 1,
  route_group VARCHAR(120) NOT NULL DEFAULT '',
  route_json JSON NULL,
  delivered_at DATETIME NULL,
  PRIMARY KEY (delivery_id),
  UNIQUE KEY uq_deliveries_order (order_id),
  KEY ix_deliveries_route (delivery_date, delivery_slot, route_group, route_sequence),
  CONSTRAINT fk_deliveries_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payments (
  payment_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id INT UNSIGNED NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  payment_method ENUM('cod','demo_online') NOT NULL,
  transaction_reference VARCHAR(80) NOT NULL,
  payment_status VARCHAR(20) NOT NULL,
  payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (payment_id),
  UNIQUE KEY uq_payments_order (order_id),
  CONSTRAINT ck_payment_amount CHECK (amount >= 0),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reviews (
  review_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  product_id INT UNSIGNED NOT NULL,
  order_id INT UNSIGNED NOT NULL,
  rating TINYINT UNSIGNED NOT NULL,
  comment VARCHAR(1000) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (review_id),
  UNIQUE KEY uq_review_user_product (user_id, product_id),
  KEY ix_reviews_product (product_id, created_at),
  CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS loyalty_points (
  loyalty_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  points INT NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (loyalty_id),
  UNIQUE KEY uq_loyalty_user (user_id),
  CONSTRAINT ck_loyalty_points_nonnegative CHECK (points >= 0),
  CONSTRAINT fk_loyalty_points_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS loyalty_transactions (
  transaction_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  points_delta INT NOT NULL,
  event_key VARCHAR(120) NOT NULL,
  note VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transaction_id),
  UNIQUE KEY uq_loyalty_event (user_id, event_key),
  CONSTRAINT ck_loyalty_delta CHECK (points_delta <> 0),
  CONSTRAINT fk_loyalty_transactions_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
  notification_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  title VARCHAR(140) NOT NULL,
  message VARCHAR(600) NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (notification_id),
  KEY ix_notifications_user_read (user_id, is_read),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
