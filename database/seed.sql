-- Fictional Farm2Home sample data for local demonstrations.
-- Password for every demo account: Farm2Home123!
-- Hash method: pbkdf2:sha256 (never store plaintext passwords).
USE farm2home;
SET FOREIGN_KEY_CHECKS = 1;

INSERT IGNORE INTO users (user_id,full_name,email,password_hash,phone,role,address,city,pincode,is_active) VALUES
(1,'Farm2Home Admin','admin@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000001','admin','Demo Admin Office','Mira Road','401107',1),
(2,'Aditi Kulkarni','consumer@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000011','consumer','Mira Road Main Road','Mira Road','401107',1),
(3,'Neel Joshi','consumer2@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000012','consumer','Bhayandar East Main Road','Bhayandar East','401105',1),
(4,'Sara Fernandes','consumer3@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000013','consumer','Kashimira Main Road','Kashimira','401107',1),
(5,'Ishaan Desai','consumer4@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000014','consumer','Bhayandar West Main Road','Bhayandar West','401101',1),
(6,'Diya Mhatre','consumer5@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000015','consumer','Uttan Main Road','Uttan','401106',1),
(7,'Arjun Rao','consumer6@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9000000016','consumer','Mira Road East Main Road','Mira Road East','401107',1),
(8,'Aarav Patil','farmer1@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9100000001','farmer','Mira Road, Mira-Bhayandar','Mira Road','401107',1),
(9,'Meera Naik','farmer2@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9100000002','farmer','Bhayandar East, Mira-Bhayandar','Bhayandar East','401105',1),
(10,'Rohan Sawant','farmer3@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9100000003','farmer','Bhayandar West, Mira-Bhayandar','Bhayandar West','401101',1),
(11,'Anaya More','farmer4@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9100000004','farmer','Uttan, Mira-Bhayandar','Uttan','401106',1),
(12,'Kabir Shah','farmer5@farm2home.test','pbkdf2:sha256:600000$Mbr9hr33x5Ii9zrY$65d554ef3c7f766c91b55ea86951111fc2b81b71eb042eab99a14a6e58971d8d','9100000005','farmer','Kashimira, Mira-Bhayandar','Kashimira','401107',1);

INSERT IGNORE INTO farmers (farmer_id,user_id,farm_name,farm_location,description,farming_method,verification_status,latitude,longitude) VALUES
(1,8,'Green Valley Farm','Mira Road','Seasonal vegetables grown with care near the coast.','Natural seasonal farming','approved',19.285100,72.871000),
(2,9,'Sunrise Fields','Bhayandar East','Fruit and greens from a small family-run plot.','Integrated sustainable farming','approved',19.301000,72.856000),
(3,10,'Coastal Harvest Co-op','Bhayandar West','A grower cooperative serving neighboring families.','Community-supported farming','approved',19.292000,72.836000),
(4,11,'Uttan Orchard','Uttan','Fruit, herbs and vegetables from the Uttan belt.','Low-input mixed farming','approved',19.270000,72.785000),
(5,12,'Kashimira Organics','Kashimira','Organic-practice greens and pantry produce.','Organic practices','approved',19.266000,72.868000);

INSERT IGNORE INTO categories (category_id,category_name,description) VALUES
(1,'Vegetables','Seasonal staples picked close to home.'),(2,'Fruits','Bright, seasonal fruit from local growers.'),
(3,'Leafy Vegetables','Tender greens harvested in small batches.'),(4,'Grains','Everyday grains from trusted farms.'),
(5,'Pulses','Wholesome pantry staples.'),(6,'Organic Produce','Produce grown with organic practices.'),
(7,'Dairy','Fresh dairy from local producers.'),(8,'Farm Products','Small-batch produce and farm goods.');

INSERT IGNORE INTO delivery_slots (slot_id,slot_name,start_time,end_time,max_orders,status) VALUES
(1,'Morning','08:00:00','11:00:00',18,'active'),
(2,'Afternoon','12:00:00','15:00:00',18,'active'),
(3,'Evening','16:00:00','19:00:00',18,'active');

INSERT IGNORE INTO subscription_plans (plan_id,plan_name,frequency,price,discount_percent,description,delivery_slot,bonus_points) VALUES
(1,'Weekly Fresh Basket','weekly',549.00,5,'A colorful weekly selection of seasonal farm staples.','Morning',10),
(2,'Bi-Weekly Family Basket','biweekly',999.00,7,'A family-sized box arriving every two weeks.','Morning',10),
(3,'Monthly Organic Basket','monthly',1799.00,10,'A curated organic-practice selection once a month.','Morning',10),
(4,'Weekly Greens Box','weekly',399.00,5,'Leafy greens and fresh herbs for the week.','Morning',10),
(5,'Seasonal Farm Box','monthly',1299.00,8,'A changing monthly box based on the harvest.','Morning',10);

INSERT IGNORE INTO products (product_id,farmer_id,category_id,product_name,description,price,unit,available_quantity,organic,image_url,status) VALUES
(1,1,1,'Organic Tomatoes','Juicy vine-ripened tomatoes.',60.00,'kg',20,1,'','active'),
(2,2,3,'Baby Spinach','Tender spinach leaves for everyday meals.',45.00,'bunch',19,1,'','active'),
(3,3,2,'Alphonso Mangoes','Seasonal sweet mangoes from the grower.',180.00,'kg',18,0,'','active'),
(4,4,1,'Farm Carrots','Crunchy, bright carrots harvested this week.',55.00,'kg',17,1,'','active'),
(5,5,1,'Fresh Okra','Small-batch okra with a crisp bite.',52.00,'kg',16,0,'','active'),
(6,1,3,'Coriander Bunch','Fragrant coriander picked to order.',18.00,'bunch',15,1,'','active'),
(7,2,1,'Green Cucumbers','Cool and crisp cucumbers.',38.00,'kg',14,0,'','active'),
(8,3,1,'Purple Eggplant','Glossy brinjal from a nearby farm.',48.00,'kg',13,1,'','active'),
(9,4,1,'Red Onions','Kitchen-ready red onions.',42.00,'kg',12,0,'','active'),
(10,5,2,'Sweet Bananas','Naturally sweet local bananas.',60.00,'dozen',23,0,'','active'),
(11,1,3,'Leafy Amaranth','Vibrant amaranth greens.',25.00,'bunch',22,1,'','active'),
(12,2,1,'Red Bell Peppers','Colorful sweet peppers.',110.00,'kg',21,1,'','active'),
(13,3,1,'Fresh Sweet Corn','Tender cobs picked at the right time.',40.00,'each',20,0,'','active'),
(14,4,2,'Seasonal Papaya','Ripe papaya with a mellow sweetness.',50.00,'kg',19,0,'','active'),
(15,5,6,'Organic Green Peas','Sweet peas grown with organic practices.',95.00,'kg',18,1,'','active'),
(16,1,4,'Brown Rice','Locally milled everyday brown rice.',95.00,'kg',17,0,'','active'),
(17,2,5,'Toor Dal','Cleaned and sorted toor dal.',145.00,'kg',16,0,'','active'),
(18,3,1,'Tender Drumsticks','Fresh drumsticks for sambar and curries.',65.00,'bunch',15,1,'','active'),
(19,4,3,'Fresh Mint','Cooling mint leaves.',20.00,'bunch',14,1,'','active'),
(20,5,8,'Local Groundnuts','Small-batch roasted-ready groundnuts.',120.00,'kg',13,0,'','active'),
(21,1,1,'Bottle Gourd','Tender lauki harvested nearby.',36.00,'each',12,0,'','active'),
(22,2,3,'Red Amaranth','Colorful nutrient-rich leafy greens.',28.00,'bunch',23,1,'','active'),
(23,3,7,'Farm Fresh Curd','Creamy cultured curd from a local dairy.',75.00,'500g',22,0,'','active'),
(24,4,2,'Seasonal Guava','Aromatic guavas from the seasonal harvest.',85.00,'kg',21,1,'','active'),
(25,5,6,'Organic Lemon','Bright lemons grown with organic practices.',70.00,'kg',20,1,'','active');

INSERT IGNORE INTO carts (cart_id,user_id) VALUES (1,2),(2,3),(3,4),(4,5),(5,6),(6,7);
INSERT IGNORE INTO loyalty_points (loyalty_id,user_id,points) VALUES
(1,1,320),(2,2,180),(3,3,180),(4,4,180),(5,5,180),(6,6,180),(7,7,180),
(8,8,120),(9,9,120),(10,10,120),(11,11,120),(12,12,120);

INSERT IGNORE INTO subscriptions (subscription_id,user_id,plan_id,plan_name,frequency,start_date,next_delivery_date,amount,discount_percent,status,delivery_slot,delivery_address,city,pincode) VALUES
(1,2,1,'Weekly Fresh Basket','weekly',CURRENT_DATE - INTERVAL 14 DAY,CURRENT_DATE + INTERVAL 1 DAY,549.00,5,'active','Morning','Mira Road Main Road','Mira Road','401107'),
(2,3,2,'Bi-Weekly Family Basket','biweekly',CURRENT_DATE - INTERVAL 14 DAY,CURRENT_DATE + INTERVAL 2 DAY,999.00,7,'active','Afternoon','Bhayandar East Main Road','Bhayandar East','401105'),
(3,4,3,'Monthly Organic Basket','monthly',CURRENT_DATE - INTERVAL 14 DAY,CURRENT_DATE + INTERVAL 3 DAY,1799.00,10,'paused','Evening','Kashimira Main Road','Kashimira','401107');
INSERT IGNORE INTO subscription_items (subscription_item_id,subscription_id,product_id,quantity) VALUES
(1,1,1,1),(2,1,2,1),(3,1,6,1),(4,1,11,1),
(5,2,3,1),(6,2,4,1),(7,2,7,1),(8,2,8,1),
(9,3,15,1),(10,3,16,1),(11,3,19,1),(12,3,25,1);

-- Fictional order history: the first eight are delivered; the last two are in progress.
INSERT IGNORE INTO orders (order_id,order_number,user_id,subscription_id,subtotal,delivery_fee,discount_amount,loyalty_used,total_amount,delivery_address,city,pincode,delivery_date,delivery_slot,delivery_slot_id,order_status,payment_status) VALUES
(1,'F2H-DEMO-1001',2,NULL,105.00,30.00,0.00,0,135.00,'Mira Road Main Road','Mira Road','401107',CURRENT_DATE-INTERVAL 10 DAY,'Morning',1,'Delivered','paid'),
(2,'F2H-DEMO-1002',3,NULL,235.00,30.00,0.00,0,265.00,'Bhayandar East Main Road','Bhayandar East','401105',CURRENT_DATE-INTERVAL 9 DAY,'Afternoon',2,'Delivered','paid'),
(3,'F2H-DEMO-1003',4,NULL,156.00,30.00,0.00,0,186.00,'Kashimira Main Road','Kashimira','401107',CURRENT_DATE-INTERVAL 8 DAY,'Evening',3,'Delivered','paid'),
(4,'F2H-DEMO-1004',5,NULL,102.00,30.00,0.00,0,132.00,'Bhayandar West Main Road','Bhayandar West','401101',CURRENT_DATE-INTERVAL 7 DAY,'Morning',1,'Delivered','paid'),
(5,'F2H-DEMO-1005',6,NULL,135.00,30.00,0.00,0,165.00,'Uttan Main Road','Uttan','401106',CURRENT_DATE-INTERVAL 6 DAY,'Afternoon',2,'Delivered','paid'),
(6,'F2H-DEMO-1006',7,NULL,185.00,30.00,0.00,0,215.00,'Mira Road East Main Road','Mira Road East','401107',CURRENT_DATE-INTERVAL 5 DAY,'Evening',3,'Delivered','paid'),
(7,'F2H-DEMO-1007',2,NULL,150.00,30.00,0.00,0,180.00,'Mira Road Main Road','Mira Road','401107',CURRENT_DATE-INTERVAL 4 DAY,'Morning',1,'Delivered','paid'),
(8,'F2H-DEMO-1008',3,NULL,85.00,30.00,0.00,0,115.00,'Bhayandar East Main Road','Bhayandar East','401105',CURRENT_DATE-INTERVAL 3 DAY,'Afternoon',2,'Delivered','paid'),
(9,'F2H-DEMO-1009',4,NULL,156.00,30.00,0.00,0,186.00,'Kashimira Main Road','Kashimira','401107',CURRENT_DATE+INTERVAL 1 DAY,'Evening',3,'Preparing','pending'),
(10,'F2H-DEMO-1010',5,NULL,258.00,30.00,0.00,0,288.00,'Bhayandar West Main Road','Bhayandar West','401101',CURRENT_DATE+INTERVAL 2 DAY,'Morning',1,'Confirmed','pending');
INSERT IGNORE INTO order_items (order_item_id,order_id,product_id,quantity,price_at_purchase) VALUES
(1,1,1,1,60.00),(2,1,2,1,45.00),(3,2,3,1,180.00),(4,2,4,1,55.00),
(5,3,5,1,52.00),(6,3,6,1,18.00),(7,3,7,1,38.00),(8,3,8,1,48.00),
(9,4,9,1,42.00),(10,4,10,1,60.00),(11,5,11,1,25.00),(12,5,12,1,110.00),
(13,6,13,1,40.00),(14,6,14,1,50.00),(15,6,15,1,95.00),(16,7,16,1,95.00),(17,7,4,1,55.00),
(18,8,18,1,65.00),(19,8,19,1,20.00),(20,9,20,1,120.00),(21,9,21,1,36.00),(22,10,22,1,28.00),(23,10,23,1,75.00),(24,10,24,1,85.00),(25,10,25,1,70.00);

INSERT IGNORE INTO payments (payment_id,order_id,amount,payment_method,transaction_reference,payment_status) VALUES
(1,1,135.00,'cod','DEMO-REF-1001','paid'),(2,2,265.00,'demo_online','DEMO-REF-1002','simulated_success'),
(3,3,265.00,'cod','DEMO-REF-1003','paid'),(4,4,90.00,'demo_online','DEMO-REF-1004','simulated_success'),
(5,5,165.00,'cod','DEMO-REF-1005','paid'),(6,6,215.00,'demo_online','DEMO-REF-1006','simulated_success'),
(7,7,180.00,'cod','DEMO-REF-1007','paid'),(8,8,115.00,'demo_online','DEMO-REF-1008','simulated_success'),
(9,9,186.00,'cod','DEMO-REF-1009','pending'),(10,10,288.00,'demo_online','DEMO-REF-1010','pending');
INSERT IGNORE INTO deliveries (delivery_id,order_id,delivery_date,delivery_slot,route_status,delivery_status,current_latitude,current_longitude,estimated_time,route_sequence,route_group,route_json,delivered_at) VALUES
(1,1,CURRENT_DATE-INTERVAL 10 DAY,'Morning','completed','Delivered',19.285100,72.871000,'Delivered',1,'401107|Morning','{}',CURRENT_TIMESTAMP),
(2,2,CURRENT_DATE-INTERVAL 9 DAY,'Afternoon','completed','Delivered',19.301000,72.856000,'Delivered',1,'401105|Afternoon','{}',CURRENT_TIMESTAMP),
(3,3,CURRENT_DATE-INTERVAL 8 DAY,'Evening','completed','Delivered',19.266000,72.868000,'Delivered',1,'401107|Evening','{}',CURRENT_TIMESTAMP),
(4,4,CURRENT_DATE-INTERVAL 7 DAY,'Morning','completed','Delivered',19.292000,72.836000,'Delivered',1,'401101|Morning','{}',CURRENT_TIMESTAMP),
(5,5,CURRENT_DATE-INTERVAL 6 DAY,'Afternoon','completed','Delivered',19.270000,72.785000,'Delivered',1,'401106|Afternoon','{}',CURRENT_TIMESTAMP),
(6,6,CURRENT_DATE-INTERVAL 5 DAY,'Evening','completed','Delivered',19.284000,72.876000,'Delivered',1,'401107|Evening','{}',CURRENT_TIMESTAMP),
(7,7,CURRENT_DATE-INTERVAL 4 DAY,'Morning','completed','Delivered',19.280000,72.870000,'Delivered',1,'401107|Morning','{}',CURRENT_TIMESTAMP),
(8,8,CURRENT_DATE-INTERVAL 3 DAY,'Afternoon','completed','Delivered',19.300000,72.855000,'Delivered',1,'401105|Afternoon','{}',CURRENT_TIMESTAMP),
(9,9,CURRENT_DATE+INTERVAL 1 DAY,'Evening','optimized','Preparing',19.266000,72.868000,'~28 min from farm',1,'401107|Evening','{}',NULL),
(10,10,CURRENT_DATE+INTERVAL 2 DAY,'Morning','optimized','Confirmed',19.292000,72.836000,'~31 min from farm',1,'401101|Morning','{}',NULL);
INSERT IGNORE INTO slot_capacities (capacity_id,slot_id,service_date,current_orders) VALUES
(1,3,CURRENT_DATE+INTERVAL 1 DAY,1),(2,1,CURRENT_DATE+INTERVAL 2 DAY,1);

INSERT IGNORE INTO reviews (review_id,user_id,product_id,order_id,rating,comment) VALUES
(1,2,1,1,5,'Picked this morning and tasted wonderful.'),
(2,3,3,2,4,'Great local quality and careful packing.'),
(3,4,5,3,5,'Fresh produce and an easy delivery.'),
(4,5,9,4,4,'Good quality from a farm nearby.'),
(5,6,11,5,5,'Tender greens and a reliable delivery.');
INSERT IGNORE INTO notifications (notification_id,user_id,title,message,is_read) VALUES
(1,2,'A fresh start','Browse this week''s harvest from local Mira-Bhayandar farms.',0),
(2,3,'Order delivered','Your fresh basket has arrived. Tell your neighbors what you think.',0),
(3,4,'Subscription paused','Your Monthly Organic Basket is paused. Resume when you are ready.',0),
(4,5,'Order confirmed','Your next delivery is being prepared by local growers.',0),
(5,6,'Welcome to the marketplace','Discover a more direct connection to the people who grow your food.',0),
(6,8,'Welcome, Green Valley Farm','Your approved farm profile is ready for product listings.',0);
