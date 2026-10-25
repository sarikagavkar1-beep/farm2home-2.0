USE farm2home;

-- SELECT, WHERE and ORDER BY: browse available organic produce from least to most expensive.
SELECT product_id, product_name, price, unit, available_quantity
FROM products
WHERE status = 'active' AND organic = TRUE AND available_quantity > 0
ORDER BY price ASC, product_name ASC;

-- JOIN: show each product with its category and local farm.
SELECT p.product_name, c.category_name, f.farm_name, f.farm_location, p.price, p.unit
FROM products AS p
JOIN categories AS c ON c.category_id = p.category_id
JOIN farmers AS f ON f.farmer_id = p.farmer_id
WHERE p.status = 'active'
ORDER BY f.farm_name, p.product_name;

-- Aggregate functions and GROUP BY: catalog size, average price and total listed stock by category.
SELECT c.category_name,
       COUNT(p.product_id) AS product_count,
       ROUND(AVG(p.price), 2) AS average_price,
       SUM(p.available_quantity) AS listed_units
FROM categories AS c
LEFT JOIN products AS p ON p.category_id = c.category_id AND p.status = 'active'
GROUP BY c.category_id, c.category_name
ORDER BY product_count DESC, c.category_name;

-- HAVING: show categories with at least two active products.
SELECT c.category_name, COUNT(p.product_id) AS product_count
FROM categories AS c
JOIN products AS p ON p.category_id = c.category_id
WHERE p.status = 'active'
GROUP BY c.category_id, c.category_name
HAVING COUNT(p.product_id) >= 2
ORDER BY product_count DESC;

-- Monthly revenue, grouped from order snapshots (delivered demo revenue).
SELECT DATE_FORMAT(o.created_at, '%Y-%m') AS order_month,
       COUNT(*) AS order_count,
       SUM(o.total_amount) AS demo_revenue
FROM orders AS o
WHERE o.order_status = 'Delivered'
GROUP BY DATE_FORMAT(o.created_at, '%Y-%m')
ORDER BY order_month DESC;

-- Correlated subquery: customers whose delivered-order spend exceeds the average customer spend.
SELECT u.user_id, u.full_name,
       (SELECT SUM(o.total_amount) FROM orders AS o
        WHERE o.user_id = u.user_id AND o.order_status = 'Delivered') AS delivered_spend
FROM users AS u
WHERE u.role = 'consumer'
  AND COALESCE((SELECT SUM(o.total_amount) FROM orders AS o
                WHERE o.user_id = u.user_id AND o.order_status = 'Delivered'), 0)
      > COALESCE((SELECT AVG(customer_spend) FROM
                  (SELECT SUM(o2.total_amount) AS customer_spend
                   FROM orders AS o2 WHERE o2.order_status = 'Delivered'
                   GROUP BY o2.user_id) AS customer_totals), 0)
ORDER BY delivered_spend DESC;

-- JOIN plus aggregate: farmer order-line revenue and units (not accounting net revenue).
SELECT f.farmer_id, f.farm_name,
       SUM(oi.quantity) AS units_sold,
       SUM(oi.quantity * oi.price_at_purchase) AS gross_order_line_value
FROM farmers AS f
JOIN products AS p ON p.farmer_id = f.farmer_id
JOIN order_items AS oi ON oi.product_id = p.product_id
JOIN orders AS o ON o.order_id = oi.order_id
WHERE o.order_status NOT IN ('Cancelled','Rejected')
GROUP BY f.farmer_id, f.farm_name
ORDER BY gross_order_line_value DESC;

-- UPDATE example (run only when deliberately changing a specific slot):
-- UPDATE delivery_slots SET max_orders = 20 WHERE slot_id = 1;

-- DELETE example (run only for a specific test basket line):
-- DELETE FROM cart_items WHERE cart_item_id = 999 AND cart_id = 999;

-- Safe transactional preview for an administrative change:
-- START TRANSACTION;
-- UPDATE products SET available_quantity = 12 WHERE product_id = 1;
-- SELECT product_id, product_name, available_quantity FROM products WHERE product_id = 1;
-- COMMIT;
