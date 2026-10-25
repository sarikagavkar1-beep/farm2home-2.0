/* Farm2Home browser application — same-origin Fetch API, no client-side framework. */
(() => {
  'use strict';
  const API = '/api';
  const MAX_PRODUCT_PHOTO_BYTES = 5 * 1024 * 1024;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  let me = null, currentCart = null, currentProducts = [], currentRoute = '/', currentProduct = null;
  let homeMap = null, trackingMap = null, chartInstances = [];
  const chartColors = ['#1f6b45', '#f2a93b', '#84a886', '#d58b57', '#557d62', '#a8c69d'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const currency = value => `₹${Number(value || 0).toLocaleString('en-IN', {maximumFractionDigits: 2})}`;
  const phoneLink = value => { const phone=String(value||'').trim(); return /^\d{10}$/.test(phone)?`<a class="text-link" href="tel:${phone}">${phone}</a>`:'—'; };
  const fmtDate = value => value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', {day:'numeric', month:'short', year:'numeric'}) : '—';
  const slug = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const emojiFor = product => {
    const n = `${product?.product_name || ''} ${product?.category_name || ''}`.toLowerCase();
    if (/tomato/.test(n)) return '🍅'; if (/spinach|greens|amaranth|leafy/.test(n)) return '🥬';
    if (/mango/.test(n)) return '🥭'; if (/carrot/.test(n)) return '🥕'; if (/okra/.test(n)) return '🌿';
    if (/coriander|mint|herb/.test(n)) return '🌱'; if (/cucumber/.test(n)) return '🥒';
    if (/eggplant|brinjal/.test(n)) return '🍆'; if (/onion/.test(n)) return '🧅';
    if (/banana/.test(n)) return '🍌'; if (/pepper/.test(n)) return '🫑'; if (/corn/.test(n)) return '🌽';
    if (/papaya/.test(n)) return '🍈'; if (/pea/.test(n)) return '🫛'; if (/rice|grain/.test(n)) return '🌾';
    if (/dal|pulse|groundnut/.test(n)) return '🫘'; if (/drumstick/.test(n)) return '🌿';
    if (/gourd/.test(n)) return '🥒'; if (/curd|dairy/.test(n)) return '🥛'; if (/guava/.test(n)) return '🍐';
    if (/lemon/.test(n)) return '🍋'; if (/fruit/.test(n)) return '🍊'; return '🥗';
  };
  const safeImageUrl = value => {
    const raw=String(value || '').trim(); if(!raw) return '';
    try { const url=new URL(raw,window.location.href); return ['http:','https:'].includes(url.protocol)?url.href:''; }
    catch { return ''; }
  };
  const artFor = product => {
    const url=safeImageUrl(product?.image_url);
    return url?`<img class="product-photo" src="${esc(url)}" alt="${esc(product?.product_name || 'Fresh produce')}" loading="lazy" referrerpolicy="no-referrer" data-fallback="${esc(emojiFor(product))}">`:`<span class="produce-emoji">${emojiFor(product)}</span>`;
  };
  const toast = (message, type = 'success') => {
    const region = $('#toastRegion'); if (!region) return;
    const item = document.createElement('div'); item.className = `toast ${type === 'error' ? 'error' : ''}`;
    item.innerHTML = `<i class="bi ${type === 'error' ? 'bi-exclamation-circle' : 'bi-check-circle'}"></i><span>${esc(message)}</span>`;
    region.append(item); setTimeout(() => item.remove(), 3600);
  };
  async function api(path, options = {}) {
    const headers = {...(options.headers || {})};
    if (options.body && typeof options.body !== 'string' && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
    const response = await fetch(`${API}${path}`, {...options, headers, credentials:'same-origin'});
    let payload;
    try { payload = await response.json(); } catch { payload = {success:false, message:'The server returned an unreadable response.'}; }
    if (!response.ok || payload.success === false) throw new Error(payload.message || `Request failed (${response.status}).`);
    return payload.data;
  }
  function setBusy(element, busy, label) {
    if (!element) return;
    element.classList.toggle('loading', busy);
    if (busy) { element.dataset.originalText = element.innerHTML; element.innerHTML = `<i class="bi bi-arrow-repeat"></i> ${esc(label || 'Working…')}`; }
    else if (element.dataset.originalText) { element.innerHTML = element.dataset.originalText; delete element.dataset.originalText; }
  }
  function showModal(id) { const node = document.getElementById(id); if (node) { node.hidden = false; document.body.style.overflow = 'hidden'; } }
  function closeModal(id) { const node = document.getElementById(id); if (node) node.hidden = true; if (!$('.modal-backdrop:not([hidden])')) document.body.style.overflow = ''; }
  function openAuth(mode = 'login') { setAuthMode(mode); showModal('authModal'); }
  function setAuthMode(mode) {
    const register = mode === 'register';
    $$('.auth-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.authMode === mode));
    $('#authTitle').textContent = register ? 'Join the neighborhood.' : 'Come on in.';
    $('#authSubtitle').textContent = register ? 'Create your Farm2Home account.' : 'Sign in to see your harvest.';
    $('#authSubmit').innerHTML = `${register ? 'Create account' : 'Log in'} <i class="bi bi-arrow-right"></i>`;
    $('#registerFields').hidden = !register;
    const pass = $('#authForm [name="password"]'); pass.autocomplete = register ? 'new-password' : 'current-password';
    const phone = $('#authForm [name="phone"]'); if (phone) phone.required = register;
    const role = $('#registerRole'); if (role) toggleFarmerFields(role.value);
  }
  function toggleFarmerFields(role) {
    const farmer = role === 'farmer';
    $('#farmNameField').hidden = !farmer; $('#farmLocationField').hidden = !farmer;
    const input = $('#farmNameField input'); if (input) input.required = farmer;
  }
  function syncHeader() {
    const loggedIn = Boolean(me);
    $('#loginOpen').hidden = loggedIn; $('#registerOpen').hidden = loggedIn;
    $('#profileMenu').hidden = !loggedIn;
    const consumerNav = $('#consumerDashboardNav'); if (consumerNav) consumerNav.hidden = me?.role !== 'consumer';
    const farmerNav = $('#farmerDashboardNav'); if (farmerNav) farmerNav.hidden = me?.role !== 'farmer';
    if (me) {
      $('#profileName').textContent = me.full_name.split(' ')[0];
      $('#profileAvatar').textContent = me.full_name.charAt(0).toUpperCase();
      $('#dashboardName').textContent = `Hello, ${me.full_name.split(' ')[0]}.`;
      $('#dashboardAvatar').textContent = me.full_name.charAt(0).toUpperCase();
      $('#dashboardRole').textContent = me.role === 'farmer' ? 'Local grower' : me.role;
    }
    loadCartCount(); loadNotificationBadge();
  }
  async function refreshMe() {
    try { const data = await api('/auth/me'); me = data.user; }
    catch { me = null; }
    syncHeader();
  }
  function pageForPath(path) {
    if (path.startsWith('/product/')) return 'shop';
    if (path.startsWith('/track/')) return 'track';
    if (path === '/shop') return 'shop'; if (path === '/farmers') return 'farmers';
    if (path === '/subscriptions') return 'subscriptions'; if (path === '/cart') return 'cart';
    if (path === '/checkout') return 'checkout'; if (path === '/dashboard') return me?.role === 'admin' ? 'admin' : 'dashboard';
    if (path === '/orders') return 'orders'; if (path === '/notifications') return 'notifications';
    if (path === '/admin') return 'admin'; return 'home';
  }
  function navigate(path, opts = {}) {
    if (!path || path === '#') return;
    if (path.startsWith('/#')) { history.pushState({}, '', path); showPage('home'); setTimeout(() => document.querySelector(path.slice(2))?.scrollIntoView({behavior:'smooth'}), 30); return; }
    if (path.startsWith('#')) { document.querySelector(path)?.scrollIntoView({behavior:'smooth'}); return; }
    if (!opts.keepScroll) window.scrollTo({top:0, behavior:'smooth'});
    if (location.pathname !== path) history.pushState({}, '', path);
    currentRoute = path; showPage(pageForPath(path));
    $$('.main-nav a').forEach(a => a.classList.toggle('active', a.dataset.route === path));
    $('#mainNav').classList.remove('open'); $('#mobileMenuToggle').setAttribute('aria-expanded','false');
    if (path.startsWith('/product/')) loadProductModal(Number(path.split('/').pop()));
  }
  function showPage(name) {
    $$('.page').forEach(page => page.classList.remove('active'));
    const page = $(`#page-${name}`); if (page) page.classList.add('active');
    closeModal('productModal');
    if (name === 'home') { loadProducts('featuredProducts', '', 4); initHomeMap(); }
    if (name === 'shop') loadShop(); if (name === 'farmers') loadFarmers();
    if (name === 'subscriptions') { loadPlans(); loadSubscriptions(); }
    if (name === 'cart') loadCartPage(); if (name === 'checkout') prepareCheckout();
    if (name === 'dashboard') loadDashboard(); if (name === 'orders') loadOrders();
    if (name === 'notifications') loadNotificationsPage(); if (name === 'admin') loadAdminDashboard();
    if (name === 'track') loadTracking(Number(location.pathname.split('/').pop()));
  }
  function productCard(p, index = 0) {
    const rating = Number(p.rating || 0);
    const stock = Number(p.available_quantity || 0);
    return `<article class="product-card" data-product-card="${p.product_id}"><div class="product-image product-image-${(index%4)+1}" data-action="product-detail" data-id="${p.product_id}" role="button" tabindex="0" aria-label="View ${esc(p.product_name)}">${artFor(p)}${p.organic ? '<span class="organic-tag">✳ ORGANIC</span>' : ''}<span class="stock-tag ${stock<=5?'low':''}">${stock<=5?`Only ${stock} left`:'Fresh stock'}</span><span class="badge-fresh"><i class="bi bi-arrow-up-right"></i></span></div><div class="product-info"><div class="product-meta"><span>${esc(p.category_name || 'Farm produce')}</span><span class="product-rating">★ ${rating ? rating.toFixed(1) : 'New'}${p.review_count?` <small>(${p.review_count})</small>`:''}</span></div><h3>${esc(p.product_name)}</h3><div class="product-farm">${esc(p.farmer_name)} · ${esc(p.farmer_location)}</div><div class="product-buy-row"><div class="product-price">${currency(p.price)} <small>/ ${esc(p.unit)}</small></div><button class="add-button" data-action="add-cart" data-id="${p.product_id}" aria-label="Add ${esc(p.product_name)} to basket" ${stock<1?'disabled':''}><i class="bi bi-plus-lg"></i></button></div></div></article>`;
  }
  async function loadProducts(targetId = 'featuredProducts', query = '', limit = 4) {
    const target = document.getElementById(targetId); if (!target) return;
    try {
      const qs = new URLSearchParams(); if (query) qs.set('q', query);
      if ($('#categoryFilter')?.value) qs.set('category', $('#categoryFilter').value);
      if ($('#organicFilter')?.checked) qs.set('organic', 'true');
      if ($('#sortFilter')?.value) qs.set('sort', $('#sortFilter').value);
      const rows = await api(`/products${qs.size?`?${qs}`:''}`); currentProducts = rows;
      target.innerHTML = rows.slice(0, limit).map(productCard).join('') || '';
      if (targetId === 'shopProducts') $('#shopEmpty').hidden = rows.length > 0;
      loadCategories();
    } catch (error) { target.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p></div>`; }
  }
  async function loadCategories() {
    const select = $('#categoryFilter'); if (!select || select.dataset.loaded) return;
    try { const rows = await api('/categories'); const current = select.value;
      select.innerHTML = '<option value="">All produce</option>' + rows.map(c => `<option value="${esc(c.category_name)}">${esc(c.category_name)}</option>`).join('');
      select.value = current; select.dataset.loaded = 'true';
    } catch { /* marketplace still works without filters */ }
  }
  function loadShop() { loadProducts('shopProducts', $('#productSearch')?.value || '', 100); }
  async function addToCart(id, button) {
    if (!me) { openAuth('login'); toast('Sign in to add produce to your basket.','error'); return; }
    setBusy(button, true, 'Adding');
    try { const data = await api('/cart/add', {method:'POST', body:{product_id:id, quantity:1}}); currentCart = data; updateCartCount(data.item_count); toast('Added to your basket.'); }
    catch (error) { toast(error.message, 'error'); }
    finally { setBusy(button, false); }
  }
  function updateCartCount(value) { $('#cartCount').textContent = Number(value || 0); $('#cartCount').classList.remove('cart-pop'); void $('#cartCount').offsetWidth; $('#cartCount').classList.add('cart-pop'); }
  async function loadCartCount() {
    if (!me || me.role !== 'consumer') { updateCartCount(0); return; }
    try { currentCart = await api('/cart'); updateCartCount(currentCart.item_count); }
    catch { updateCartCount(0); }
  }
  function renderSummary(target, cart) {
    if (!target || !cart) return;
    target.innerHTML = `<div class="summary-line"><span>Subtotal</span><b>${currency(cart.subtotal)}</b></div><div class="summary-line"><span>Delivery</span><b>${cart.delivery_fee?currency(cart.delivery_fee):'Free'}</b></div>${cart.discount?`<div class="summary-line"><span>Subscriber savings</span><b>−${currency(cart.discount)}</b></div>`:''}<div class="summary-line total"><span>Estimated total</span><b>${currency(cart.final_total)}</b></div><small class="summary-line" style="font-size:8px">Free delivery on baskets over ₹499</small>`;
  }
  async function loadCartPage() {
    const list = $('#cartItems'), summary = $('#summaryLines');
    if (!me || me.role !== 'consumer') { list.innerHTML = '<div class="signed-out-note">Sign in as a customer to keep a basket and place a demo order.<br><button class="btn btn-primary" style="margin-top:13px" onclick="window.openFarmAuth()">Log in</button></div>'; summary.innerHTML = ''; $('#checkoutButton').disabled = true; return; }
    $('#checkoutButton').disabled = false;
    try {
      const cart = await api('/cart'); currentCart = cart; updateCartCount(cart.item_count);
      if (!cart.items.length) { list.innerHTML = '<div class="signed-out-note">Your basket is empty. There is plenty of good produce waiting for you.</div>'; summary.innerHTML = '<div class="summary-line total"><span>Total</span><b>₹0</b></div>'; $('#checkoutButton').disabled = true; return; }
      list.innerHTML = cart.items.map((item, i) => `<div class="cart-item"><div class="cart-product-art">${artFor(item.product)}</div><div><h3>${esc(item.product.product_name)}</h3><small>${esc(item.product.farmer_name)} · ${currency(item.product.price)} / ${esc(item.product.unit)}</small></div><div class="quantity-control"><button data-action="quantity" data-item="${item.cart_item_id}" data-qty="${item.quantity-1}" aria-label="Decrease quantity">−</button><span>${item.quantity}</span><button data-action="quantity" data-item="${item.cart_item_id}" data-qty="${item.quantity+1}" aria-label="Increase quantity">+</button></div><strong class="cart-price">${currency(item.line_total)}</strong><button class="remove-item" data-action="remove-cart" data-item="${item.cart_item_id}" aria-label="Remove ${esc(item.product.product_name)}"><i class="bi bi-x-lg"></i></button></div>`).join('');
      renderSummary(summary, cart);
    } catch (error) { list.innerHTML = `<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function changeQuantity(itemId, qty) {
    try { const data = await api('/cart/update', {method:'PUT', body:{cart_item_id:itemId, quantity:qty}}); currentCart = data; updateCartCount(data.item_count); loadCartPage(); toast('Basket updated.'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function removeCart(itemId) {
    try { const data = await api('/cart/remove', {method:'DELETE', body:{cart_item_id:itemId}}); currentCart=data; updateCartCount(data.item_count); loadCartPage(); toast('Item removed.'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function prepareCheckout() {
    if (!me || me.role !== 'consumer') { openAuth('login'); toast('Please sign in as a customer to check out.','error'); navigate('/cart'); return; }
    const form = $('#checkoutForm'); form.elements.name.value = me.full_name || ''; form.elements.phone.value = me.phone || '';
    form.elements.address.value = me.address || ''; form.elements.city.value = me.city || 'Mira Road'; form.elements.pincode.value = me.pincode || '401107';
    const today = new Date(); today.setMinutes(today.getMinutes()-today.getTimezoneOffset());
    $('#deliveryDate').min = today.toISOString().slice(0,10); $('#deliveryDate').value = today.toISOString().slice(0,10);
    await loadCartForCheckout(); await loadSlots();
    try { const data = await api('/loyalty'); $('#pointsHint').textContent = `${data.points} points available · 100 points = ₹10.`; $('#usePoints').disabled = data.points < 100; }
    catch { $('#pointsHint').textContent = '100 points = ₹10. Sign in to use your reward balance.'; }
  }
  async function loadCartForCheckout() {
    try { currentCart = await api('/cart');
      $('#checkoutSummaryLines').innerHTML = currentCart.items.map(i=>`<div class="summary-line"><span>${esc(i.product.product_name)} × ${i.quantity}</span><b>${currency(i.line_total)}</b></div>`).join('') + `<div class="summary-line"><span>Delivery</span><b>${currentCart.delivery_fee?currency(currentCart.delivery_fee):'Free'}</b></div><div class="summary-line total"><span>Basket subtotal</span><b>${currency(currentCart.subtotal)}</b></div>`;
      if (!currentCart.items.length) { toast('Your basket is empty.','error'); navigate('/shop'); }
    } catch(error) { toast(error.message,'error'); navigate('/cart'); }
  }
  async function loadSlots() {
    const input = $('#deliveryDate'); if (!input?.value) return;
    try { const slots = await api(`/delivery-slots?date=${encodeURIComponent(input.value)}`);
      $('#deliverySlot').innerHTML = slots.map(s=>`<option value="${s.slot_id}" ${s.available<1?'disabled':''}>${esc(s.slot_name)} · ${s.start_time}–${s.end_time} · ${s.available} spots</option>`).join('');
      if (!slots.some(s=>s.available>0)) toast('No slots available for that date; please choose another day.','error');
    } catch(error) { $('#deliverySlot').innerHTML='<option value="">Slots unavailable</option>'; toast(error.message,'error'); }
  }
  async function placeOrder(event) {
    event.preventDefault(); const form = event.currentTarget, button = $('#placeOrderButton');
    const fd = new FormData(form); const payload = {name:fd.get('name'), phone:fd.get('phone'), address:fd.get('address'), city:fd.get('city'), pincode:fd.get('pincode'), delivery_date:fd.get('delivery_date'), slot_id:Number(fd.get('slot_id')), payment_method:fd.get('payment_method'), use_points:$('#usePoints').checked};
    if (!/^\d{10}$/.test(payload.phone) || !/^\d{6}$/.test(payload.pincode)) { toast('Enter a 10-digit phone and 6-digit pincode.','error'); return; }
    setBusy(button,true,'Placing your order');
    try { const order = await api('/orders',{method:'POST',body:payload}); toast(`Order ${order.order_number} is on its way.`); navigate('/orders'); }
    catch(error) { toast(error.message,'error'); }
    finally { setBusy(button,false); }
  }
  async function loadFarmers() {
    const target = $('#farmersGrid'); if (!target) return;
    try { const rows=await api('/farmers');
      target.innerHTML=rows.map(f=>`<article class="farmer-card"><div class="farmer-monogram">${esc(f.farm_name.split(' ').map(w=>w[0]).join('').slice(0,2))}</div><span class="eyebrow">NEAR ${esc(f.farm_location).toUpperCase()}</span><h3>${esc(f.farm_name)}</h3><div class="farmer-location"><i class="bi bi-geo-alt"></i> ${esc(f.farm_location)}, Mira-Bhayandar</div><p>${esc(f.description)}</p><div class="farmer-stat"><span>${esc(f.farming_method)}</span><b>${f.product_count} listings</b></div></article>`).join('') || '<div class="empty-state">More farm profiles are on their way.</div>';
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function loadPlans() {
    const target=$('#planGrid'); if (!target) return;
    try { const plans=await api('/subscriptions/plans');
      target.innerHTML=plans.filter(p=>['Weekly Fresh Basket','Bi-Weekly Family Basket','Monthly Organic Basket'].includes(p.plan_name)).map((p,i)=>`<article class="plan-card ${i===1?'popular':''}">${i===1?'<span class="popular-label">NEIGHBOR FAVORITE</span>':''}<span class="plan-frequency">${esc(p.frequency==='biweekly'?'EVERY TWO WEEKS':p.frequency.toUpperCase())}</span><h3>${esc(p.plan_name)}</h3><p>${esc(p.description)}</p><div class="plan-price">${currency(p.price)}<small> / delivery</small></div><ul><li><i class="bi bi-check2"></i> ${p.discount_percent}% subscriber savings</li><li><i class="bi bi-check2"></i> ${esc(p.delivery_slot)} delivery window</li><li><i class="bi bi-check2"></i> +${p.bonus_points} bonus points on delivery</li><li><i class="bi bi-check2"></i> Pause, resume or cancel anytime</li></ul><button class="btn ${i===1?'btn-cream':'btn-primary'}" data-action="subscribe" data-plan="${p.plan_id}">Choose this basket <i class="bi bi-arrow-right"></i></button></article>`).join('');
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function subscribe(planId) {
    if (!me || me.role !== 'consumer') { openAuth('login'); toast('Sign in as a customer to start a basket.','error'); return; }
    try { const slots=await api(`/delivery-slots?date=${new Date().toISOString().slice(0,10)}`); const slot=slots.find(x=>x.available>0) || slots[0];
      if (!slot) throw new Error('No delivery windows are available.');
      const result=await api('/subscriptions',{method:'POST',body:{plan_id:planId,slot_id:slot.slot_id,address:me.address || 'Mira-Bhayandar',city:me.city || 'Mira Road',pincode:me.pincode || '401107',next_delivery_date:new Date(Date.now()+86400000).toISOString().slice(0,10)}});
      toast(`${result.plan_name} is now active.`); loadSubscriptions(); loadNotificationBadge();
    } catch(error) { toast(error.message,'error'); }
  }
  async function loadSubscriptions() {
    const target=$('#subscriptionList'); if (!target) return;
    if (!me || me.role !== 'consumer') { target.innerHTML='<div class="signed-out-note">Sign in as a customer to manage your recurring baskets.</div>'; return; }
    try { const rows=await api('/subscriptions');
      target.innerHTML=rows.map(s=>`<article class="subscription-row"><div><h4>${esc(s.plan_name)}</h4><small>${esc(s.frequency)} · next ${fmtDate(s.next_delivery_date)} · ${currency(s.amount)}</small></div><span class="status-badge ${s.status}">${esc(s.status)}</span><div class="subscription-actions">${s.status==='active'?`<button class="table-action warn" data-action="sub-pause" data-id="${s.subscription_id}">Pause</button>`:s.status==='paused'?`<button class="table-action" data-action="sub-resume" data-id="${s.subscription_id}">Resume</button>`:''}${s.status!=='cancelled'?`<button class="table-action danger" data-action="sub-cancel" data-id="${s.subscription_id}">Cancel</button><button class="table-action" data-action="sub-renew" data-id="${s.subscription_id}">Renew now</button>`:''}</div></article>`).join('') || '<div class="signed-out-note">No baskets yet. Choose a plan above to get started.</div>';
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function subscriptionAction(action,id) {
    try {
      if (action==='sub-cancel' && !window.confirm('Cancel this recurring basket? You can start a new one later.')) return;
      const method=action==='sub-cancel'?'DELETE':action==='sub-renew'?'POST':'PUT';
      const suffix=action==='sub-pause'?'pause':action==='sub-resume'?'resume':action==='sub-renew'?'renew':'';
      const result=await api(`/subscriptions/${id}${suffix?`/${suffix}`:''}`,{method});
      toast(action==='sub-renew'?`Renewal order ${result.order_number} created.`:'Subscription updated.'); loadSubscriptions(); loadNotificationBadge();
    } catch(error) { toast(error.message,'error'); }
  }
  function statusClass(status) { return status==='Delivered'?'delivered':status==='Cancelled'||status==='Rejected'?'cancelled':status==='Preparing'||status==='Out for Delivery'?'progress':'placed'; }
  async function loadOrders() {
    const target=$('#ordersList'); if (!target) return;
    if (!me) { target.innerHTML='<div class="signed-out-note">Sign in to see order history.</div>'; return; }
    try {
      const [orders, reviews] = await Promise.all([
        api('/orders'), me.role === 'consumer' ? api('/reviews/mine') : Promise.resolve([])
      ]);
      const ownReviews = new Map(reviews.map(r => [Number(r.product_id), r]));
      target.innerHTML=orders.map(o=>{
        const reviewActions = me.role === 'consumer' && o.order_status === 'Delivered' ? o.items.map(item=>{
          const existing = ownReviews.get(Number(item.product_id));
          if (existing && Number(existing.order_id) === Number(o.order_id)) return `<span class="review-actions"><button class="table-action" data-action="edit-review" data-review="${existing.review_id}" data-rating="${existing.rating}" data-comment="${esc(existing.comment)}">Edit ${esc(item.product_name)} review</button><button class="table-action danger" data-action="delete-review" data-review="${existing.review_id}">Delete</button></span>`;
          if (existing) return '';
          return `<button class="table-action" data-action="review-order" data-order="${o.order_id}" data-product="${item.product_id}">Review ${esc(item.product_name)}</button>`;
        }).join('') : '';
        return `<article class="order-card"><div><h3>${esc(o.order_number)} <span class="status-badge ${statusClass(o.order_status)}">${esc(o.order_status)}</span></h3><p>${esc(o.items.map(i=>`${i.product_name} × ${i.quantity}`).join(' · '))}</p><div class="order-card-meta"><span><i class="bi bi-calendar3"></i> ${fmtDate(o.delivery_date)}</span><span><i class="bi bi-clock"></i> ${esc(o.delivery_slot)}</span><span><i class="bi bi-geo-alt"></i> ${esc(o.city)}</span></div></div><div class="order-card-side"><strong>${currency(o.total_amount)}</strong><div><button class="table-action" data-action="track" data-id="${o.order_id}">Track delivery</button>${reviewActions}</div></div></article>`;
      }).join('') || '<div class="signed-out-note">No orders yet. Your next good meal is a few clicks away.</div>';
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function openReview(orderId,productId) {
    if (!productId) return toast('No reviewable product was found.','error');
    const rating=window.prompt('Give this product a rating from 1 to 5:', '5'); if (rating===null) return;
    const comment=window.prompt('Share a short note about your harvest:', 'Fresh and lovely.'); if (comment===null) return;
    try { await api('/reviews',{method:'POST',body:{order_id:Number(orderId),product_id:Number(productId),rating:Number(rating),comment}}); toast('Thank you for sharing your review.'); loadOrders(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function editReview(reviewId,rating,comment) {
    const nextRating=window.prompt('Update your rating from 1 to 5:',String(rating)); if(nextRating===null)return;
    const nextComment=window.prompt('Update your review note:',comment||''); if(nextComment===null)return;
    if(!/^[1-5]$/.test(nextRating.trim()))return toast('Rating must be from 1 to 5.','error');
    try { await api(`/reviews/${reviewId}`,{method:'PUT',body:{rating:Number(nextRating),comment:nextComment}}); toast('Review updated.'); loadOrders(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function deleteReview(reviewId) {
    if(!window.confirm('Delete this review?'))return;
    try { await api(`/reviews/${reviewId}`,{method:'DELETE'}); toast('Review deleted.'); loadOrders(); }
    catch(error) { toast(error.message,'error'); }
  }
  function metric(icon,label,value) { return `<article class="metric-card"><span class="metric-icon"><i class="bi ${icon}"></i></span><small>${esc(label)}</small><strong>${esc(value)}</strong></article>`; }
  function renderChart(canvasId, type, labels, values, label) {
    const ctx=document.getElementById(canvasId); if (!ctx || !window.Chart) return;
    const existing=Chart.getChart(ctx); if (existing) existing.destroy();
    const isLine=type==='line';
    const chart=new Chart(ctx,{type,data:{labels:labels || [],datasets:[{label,data:values || [],borderColor:chartColors[0],backgroundColor:isLine?'rgba(31,107,69,.1)':chartColors,borderWidth:isLine?2:0,borderRadius:isLine?0:6,fill:isLine,tension:.35,pointRadius:isLine?3:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:type==='doughnut',position:'bottom',labels:{boxWidth:8,font:{size:9}}}},scales:type==='doughnut'?{}:{x:{grid:{display:false},ticks:{font:{size:8},color:'#839187'}},y:{beginAtZero:true,grid:{color:'#eef2ed'},ticks:{font:{size:8},color:'#839187'}}}}});
    chartInstances.push(chart);
  }
  async function loadDashboard() {
    if (!me) { $('#dashboardContent').innerHTML='<div class="signed-out-note">Sign in to open your personal Farm2Home dashboard.<br><button class="btn btn-primary" style="margin-top:13px" onclick="window.openFarmAuth()">Log in</button></div>'; return; }
    if (me.role==='admin') return navigate('/admin');
    const target=$('#dashboardContent'); target.innerHTML='<div class="dashboard-loading">Loading your dashboard…</div>';
    try {
      if (me.role==='farmer') return await renderFarmerDashboard(await api('/farmer/dashboard'));
      const [d, loyalty, subscriptions, reviews]=await Promise.all([api('/consumer/dashboard'),api('/loyalty'),api('/subscriptions'),api('/reviews/mine')]);
      const active=subscriptions.filter(item=>item.status==='active');
      const activeRows=active.map(item=>`<article class="subscription-row"><div><h4>${esc(item.plan_name)}</h4><small>${esc(item.frequency)} · ${currency(item.amount)} · next ${fmtDate(item.next_delivery_date)}</small></div><span class="status-badge active">Active</span><a class="table-action" href="/subscriptions" data-route="/subscriptions">Manage</a></article>`).join('') || '<div class="signed-out-note">No active basket yet. Choose a weekly, bi-weekly or monthly plan.</div>';
      const rewardRows=loyalty.history.map(item=>`<div class="summary-line"><span>${esc(item.note)} · ${fmtDate(item.created_at)}</span><b class="${item.points_delta<0?'danger-text':'green-text'}">${item.points_delta>0?'+':''}${item.points_delta} pts</b></div>`).join('') || '<p class="chart-legend">Delivered orders and rewards will appear here.</p>';
      const deliveryRows=d.recent_orders.map(o=>`<tr><td>${esc(o.order_number)}</td><td>${fmtDate(o.delivery_date)} · ${esc(o.delivery_slot)}</td><td><span class="status-badge ${statusClass(o.order_status)}">${esc(o.order_status)}</span></td><td><button class="table-action" data-action="track" data-id="${o.order_id}">Track route</button></td></tr>`).join('') || '<tr><td colspan="4">No deliveries yet.</td></tr>';
      const reviewRows=reviews.map(item=>`<article class="review-row"><div><div class="stars">${'★'.repeat(Number(item.rating))}</div><p>${esc(item.comment)}</p><small>${new Date(item.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</small></div><span class="review-actions"><button class="table-action" data-action="edit-review" data-review="${item.review_id}" data-rating="${item.rating}" data-comment="${esc(item.comment)}">Edit</button><button class="table-action danger" data-action="delete-review" data-review="${item.review_id}">Delete</button></span></article>`).join('') || '<div class="signed-out-note">No reviews yet. Share a note after a delivered order.</div>';
      $('#dashboardTitle').textContent=`Good to see you, ${me.full_name.split(' ')[0]}.`;
      target.innerHTML=`<div class="metric-grid">${metric('bi-bag-check','Total orders',d.total_orders)}${metric('bi-arrow-repeat','Active baskets',d.active_subscriptions)}${metric('bi-truck','Next delivery',d.next_delivery?fmtDate(d.next_delivery):'Not scheduled')}${metric('bi-stars','Loyalty points',d.loyalty_points)}</div><div class="dashboard-panels"><section class="dashboard-card"><div class="dashboard-toolbar"><h3>Your monthly spend</h3><span class="chart-legend">₹ · last 6 months</span></div><div style="height:210px"><canvas id="consumerSpendChart"></canvas></div></section><section class="dashboard-card"><div class="dashboard-toolbar"><h3>Orders over time</h3><span class="chart-legend">orders</span></div><div style="height:210px"><canvas id="consumerOrderChart"></canvas></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Recent orders</h3><a class="text-link" href="/orders" data-route="/orders">All orders <i class="bi bi-arrow-right"></i></a></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Delivery</th><th>Status</th><th>Total</th><th></th></tr></thead><tbody>${d.recent_orders.map(o=>`<tr><td>${esc(o.order_number)}</td><td>${fmtDate(o.delivery_date)} · ${esc(o.delivery_slot)}</td><td><span class="status-badge ${statusClass(o.order_status)}">${esc(o.order_status)}</span></td><td>${currency(o.total_amount)}</td><td><button class="table-action" data-action="track" data-id="${o.order_id}">Track</button></td></tr>`).join('') || '<tr><td colspan="5">No orders yet.</td></tr>'}</tbody></table></div></section><section class="dashboard-card full" id="consumerDeliveries"><div class="dashboard-toolbar"><h3>Your deliveries</h3><span class="chart-legend">Follow each order's status and route.</span></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Delivery window</th><th>Status</th><th></th></tr></thead><tbody>${deliveryRows}</tbody></table></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Your active baskets</h3><a class="text-link" href="/subscriptions" data-route="/subscriptions">Manage baskets <i class="bi bi-arrow-right"></i></a></div>${activeRows}</section><section class="dashboard-card" id="consumerRewards"><h3>Reward activity</h3><p class="chart-legend">100 points = ₹10 · Earn 10 points per ₹100 delivered; subscribers earn a bonus.</p>${rewardRows}<a class="text-link" href="/checkout" data-route="/checkout">Use rewards at checkout <i class="bi bi-arrow-right"></i></a></section><section class="dashboard-card"><h3>Your next basket</h3><p style="font-size:10px">${d.next_delivery?`Fresh produce is planned for <b>${fmtDate(d.next_delivery)}</b>.`:'Choose a subscription to make your next delivery predictable.'}</p><a class="text-link" href="/subscriptions" data-route="/subscriptions">Explore baskets <i class="bi bi-arrow-right"></i></a></section><section class="dashboard-card" id="consumerReviews"><div class="dashboard-toolbar"><h3>Your reviews</h3><a class="text-link" href="/orders" data-route="/orders">Review a delivered order</a></div>${reviewRows}</section><section class="dashboard-card" id="consumerSettings"><h3>Account settings</h3><dl class="account-detail-list"><div><dt>Full name</dt><dd>${esc(me.full_name)}</dd></div><div><dt>Email</dt><dd>${esc(me.email)}</dd></div><div><dt>Phone</dt><dd>${esc(me.phone)}</dd></div><div><dt>Address</dt><dd>${esc(me.address||'Not added')}</dd></div><div><dt>City / area</dt><dd>${esc(me.city||'Not added')}</dd></div><div><dt>Pincode</dt><dd>${esc(me.pincode||'Not added')}</dd></div></dl><p class="chart-legend">Profile details are read-only in this demonstration.</p></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Recommended produce</h3><a class="text-link" href="/shop" data-route="/shop">Browse all produce <i class="bi bi-arrow-right"></i></a></div><div class="product-grid" id="consumerRecommended"></div></section></div>`;
      renderChart('consumerSpendChart','bar',d.spending_chart.labels,d.spending_chart.values,'Spending');
      renderChart('consumerOrderChart','line',d.orders_chart.labels,d.orders_chart.values,'Orders');
      loadProducts('consumerRecommended','',4);
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function renderFarmerDashboard(d) {
    const target=$('#dashboardContent');
    $('#dashboardTitle').textContent=d.farm?.farm_name || 'Farm dashboard';
    const status=d.farm?.verification_status;
    const orderRows=d.recent_orders.map(o=>{
      let action='—';
      if(o.delivery?.delivery_id && !['Delivered','Cancelled','Rejected'].includes(o.order_status)) {
        if(o.order_status==='Placed') action=`<button class="table-action" data-action="farmer-status" data-delivery="${o.delivery.delivery_id}" data-status="Confirmed">Accept</button><button class="table-action danger" data-action="farmer-status" data-delivery="${o.delivery.delivery_id}" data-status="Rejected">Reject</button>`;
        else {
          const next=o.order_status==='Confirmed'?'Preparing':o.order_status==='Preparing'?'Out for Delivery':'Delivered';
          const label=o.order_status==='Confirmed'?'Prepare':o.order_status==='Preparing'?'Dispatch':'Deliver';
          action=`<button class="table-action" data-action="farmer-status" data-delivery="${o.delivery.delivery_id}" data-status="${next}">${label}</button>`;
        }
      }
      return `<tr><td>${esc(o.order_number)}</td><td>${fmtDate(o.delivery_date)} · ${esc(o.delivery_slot)}</td><td>${esc(o.items.map(i=>`${i.product_name} × ${i.quantity}`).join(', '))}</td><td><span class="status-badge ${statusClass(o.order_status)}">${esc(o.order_status)}</span></td><td>${action}</td></tr>`;
    }).join('') || '<tr><td colspan="5">No orders yet.</td></tr>';
    const subscriptionRows=(d.subscriptions||[]).map(sub=>`<tr><td>${esc(sub.plan_name)}</td><td>${esc(sub.items.map(item=>`${item.product_name} × ${item.quantity}`).join(', '))}</td><td>${fmtDate(sub.next_delivery_date)} · ${esc(sub.delivery_slot)}</td><td>${esc(sub.city)} · ${esc(sub.pincode)}</td><td>${esc(sub.status)}</td></tr>`).join('') || '<tr><td colspan="5">No active subscription deliveries include your produce yet.</td></tr>';
    const productRows=d.products.map(p=>`<tr><td>${esc(p.product_name)}${p.low_stock?' <span class="status-badge paused">LOW</span>':''}</td><td>${esc(p.category_name)}</td><td>${currency(p.price)} / ${esc(p.unit)}</td><td>${p.available_quantity}</td><td><button class="table-action" data-action="product-edit" data-id="${p.product_id}">Edit product</button><button class="table-action" data-action="product-image" data-id="${p.product_id}">${p.image_url?'Replace photo':'Upload photo'}</button><button class="table-action" data-action="product-detail" data-id="${p.product_id}">View reviews</button><button class="table-action" data-action="product-stock" data-id="${p.product_id}" data-stock="${p.available_quantity}">Update stock</button><button class="table-action danger" data-action="delete-product" data-id="${p.product_id}">Remove</button></td></tr>`).join('') || '<tr><td colspan="5">No listings yet.</td></tr>';
    target.innerHTML=`${status!=='approved'?`<div class="notification-item unread" style="margin-bottom:13px"><div class="notification-icon"><i class="bi bi-hourglass-split"></i></div><div><h3>Farm profile ${esc(status)}</h3><p>Your products can be managed here; customers will see them after approval.</p></div></div>`:''}<div class="metric-grid">${metric('bi-currency-rupee','Total sales',currency(d.total_sales))}${metric('bi-bag',"Today's orders",d.today_orders)}${metric('bi-arrow-repeat','Active subscriptions',d.active_subscriptions)}${metric('bi-hourglass','Pending orders',d.pending_orders)}${metric('bi-boxes','Available products',d.available_products)}</div><div class="dashboard-panels"><section class="dashboard-card"><h3>Sales over time</h3><div style="height:200px"><canvas id="farmerSalesChart"></canvas></div></section><section class="dashboard-card"><h3>Products by demand</h3><div style="height:200px"><canvas id="farmerProductsChart"></canvas></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Incoming orders</h3><span class="chart-legend">Accept or reject new orders, then update preparation and delivery status.</span></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Date / slot</th><th>Items</th><th>Status</th><th>Update</th></tr></thead><tbody>${orderRows}</tbody></table></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Subscription delivery schedule</h3><span class="chart-legend">Only baskets containing your listed produce are shown.</span></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Plan</th><th>Your items</th><th>Next delivery</th><th>Customer area</th><th>Status</th></tr></thead><tbody>${subscriptionRows}</tbody></table></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Your produce</h3><span class="chart-legend">Low stock is flagged at five or fewer units.</span></div><form class="inline-product-form" id="farmerProductForm"><label>Product<input name="product_name" required placeholder="e.g. Fresh okra"></label><label>Category<select name="category_id" id="farmerCategory" required></select></label><label>Price ₹<input name="price" type="number" min="1" step=".01" required></label><label>Unit<input name="unit" value="kg" required></label><label>Stock<input name="available_quantity" type="number" min="0" value="12" required></label><label class="product-image-field">Upload product photo<input name="product_image" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"><small>Choose a JPG, PNG or WEBP file up to 5 MB. An uploaded file takes priority over the URL below.</small></label><label class="product-image-field">Image URL<input name="image_url" type="url" maxlength="500" placeholder="https://example.com/produce.jpg"><small>Optional: paste a public direct image link; leave blank for the illustration.</small></label><label class="inline-checkbox"><input type="checkbox" name="organic"> Organic</label><button class="btn btn-primary" type="submit">Add produce</button></form><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Actions</th></tr></thead><tbody>${productRows}</tbody></table></div></section><section class="dashboard-card"><h3>Expected revenue</h3><strong style="font-size:25px;color:var(--green)">${currency(d.estimated_revenue)}</strong><p style="font-size:9px">Illustrative net estimate; platform fees are not charged in this project demo.</p></section><section class="dashboard-card"><h3>Farm profile</h3><p style="font-size:10px">${esc(status)} · local customers around Mira-Bhayandar</p><a class="text-link" href="/farmers" data-route="/farmers">View farmer profiles <i class="bi bi-arrow-right"></i></a></section></div>`;
    renderChart('farmerSalesChart','line',d.sales_chart.labels,d.sales_chart.values,'Sales');
    renderChart('farmerProductsChart','doughnut',d.product_chart.labels,d.product_chart.values,'Units');
    try { const cats=await api('/categories'); $('#farmerCategory').innerHTML=cats.map(c=>`<option value="${c.category_id}">${esc(c.category_name)}</option>`).join(''); } catch {}
  }
  async function loadAdminDashboard() {
    if (!me) { $('#adminContent').innerHTML='<div class="signed-out-note">Sign in with the admin demo account to manage the marketplace.<br><button class="btn btn-primary" style="margin-top:13px" onclick="window.openFarmAuth()">Log in as admin</button></div>'; return; }
    if (me.role!=='admin') { $('#adminContent').innerHTML='<div class="signed-out-note">This dashboard is available only to admins.</div>'; return; }
    const target=$('#adminContent'); target.innerHTML='<div class="dashboard-loading">Loading marketplace analytics…</div>';
    try {
      const d=await api('/admin/dashboard');
      const farmerRows=d.recent_farmers.map(f=>`<tr><td>${esc(f.farm_name)}</td><td>${esc(f.user.full_name)}</td><td>${phoneLink(f.user.phone)}</td><td>${esc(f.farm_location)}</td><td><span class="status-badge ${f.verification_status}">${esc(f.verification_status)}</span></td></tr>`).join('') || '<tr><td colspan="5">No farm profiles yet.</td></tr>';
      const orderRows=d.recent_orders.map(o=>`<tr><td>${esc(o.order_number)}</td><td>${esc(o.delivery_address)}</td><td>${fmtDate(o.delivery_date)}</td><td><span class="status-badge ${statusClass(o.order_status)}">${esc(o.order_status)}</span></td><td>${currency(o.total_amount)}</td></tr>`).join('') || '<tr><td colspan="5">No orders yet.</td></tr>';
      target.innerHTML=`<div class="metric-grid">${metric('bi-people','Total users',d.total_users)}${metric('bi-person','Consumers',d.total_consumers)}${metric('bi-flower1','Farmers',d.total_farmers)}${metric('bi-basket','Products',d.total_products)}${metric('bi-box-seam','Orders',d.total_orders)}${metric('bi-arrow-repeat','Active subscriptions',d.active_subscriptions)}${metric('bi-truck','Pending deliveries',d.pending_deliveries)}${metric('bi-currency-rupee','Demo revenue',currency(d.total_revenue))}</div><div class="dashboard-panels"><section class="dashboard-card"><h3>Monthly orders</h3><div style="height:210px"><canvas id="adminOrdersChart"></canvas></div></section><section class="dashboard-card"><h3>Monthly revenue</h3><div style="height:210px"><canvas id="adminRevenueChart"></canvas></div></section><section class="dashboard-card"><h3>Subscription growth</h3><div style="height:210px"><canvas id="adminSubscriptionChart"></canvas></div></section><section class="dashboard-card"><h3>Product categories</h3><div style="height:210px"><canvas id="adminCategoryChart"></canvas></div></section><section class="dashboard-card"><h3>Delivery status</h3><div style="height:210px"><canvas id="adminDeliveryChart"></canvas></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Farm applications</h3><a class="text-link" href="/farmers" data-route="/farmers">Farm directory <i class="bi bi-arrow-right"></i></a></div><div class="admin-pending-list">${d.pending_farmers.map(f=>`<div class="admin-pending"><div><b>${esc(f.farm_name)}</b><small>${esc(f.user.full_name)} · ${phoneLink(f.user.phone)} · ${esc(f.farm_location)}</small></div><div class="admin-actions"><button class="table-action" data-action="approve-farmer" data-id="${f.farmer_id}" data-decision="approved">Approve</button><button class="table-action danger" data-action="approve-farmer" data-id="${f.farmer_id}" data-decision="rejected">Reject</button></div></div>`).join('') || '<div class="empty-mini">No farm applications waiting.</div>'}</div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Recent farmers</h3><span class="chart-legend">Latest registered grower profiles</span></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Farm</th><th>Account</th><th>Mobile</th><th>Area</th><th>Status</th></tr></thead><tbody>${farmerRows}</tbody></table></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Recent orders</h3><a class="text-link" href="/orders" data-route="/orders">View orders <i class="bi bi-arrow-right"></i></a></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Customer address</th><th>Date</th><th>Status</th><th>Total</th></tr></thead><tbody>${orderRows}</tbody></table></div></section><section class="dashboard-card full"><div class="dashboard-toolbar"><h3>Marketplace management</h3><span class="chart-legend">Manage users, farms, listings, categories, orders, subscriptions, delivery and slots.</span></div><div class="admin-section-tabs">${[['users','Users'],['products','Products'],['categories','Categories'],['farmers','Farmers'],['orders','Orders'],['subscriptions','Subscriptions'],['deliveries','Deliveries'],['slots','Delivery slots']].map(([key,label])=>`<button class="table-action" data-action="admin-section" data-section="${key}">${label}</button>`).join('')}<button class="table-action" data-action="run-renewals">Run due subscription demo</button></div><h3 id="adminManagementTitle" style="margin-top:16px">Users</h3><div id="adminManagementPanel"><div class="dashboard-loading">Loading management data…</div></div></section></div>`;
      renderChart('adminOrdersChart','bar',d.orders_chart.labels,d.orders_chart.values,'Orders');
      renderChart('adminRevenueChart','line',d.revenue_chart.labels,d.revenue_chart.values,'Revenue');
      renderChart('adminSubscriptionChart','line',d.subscription_chart.labels,d.subscription_chart.values,'Subscriptions');
      renderChart('adminCategoryChart','doughnut',d.category_chart.labels,d.category_chart.values,'Products');
      renderChart('adminDeliveryChart','doughnut',d.delivery_chart.labels,d.delivery_chart.values,'Deliveries');
      await loadAdminSection('users');
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function loadAdminSection(section='users') {
    const panel=$('#adminManagementPanel'); if(!panel)return;
    const labels={users:'Users',products:'Products',categories:'Categories',farmers:'Farmers',orders:'Orders',subscriptions:'Subscriptions',deliveries:'Deliveries',slots:'Delivery slots'};
    $('#adminManagementTitle').textContent=labels[section]||'Marketplace management';
    panel.innerHTML='<div class="dashboard-loading">Loading management data…</div>';
    try {
      let rows=[];
      if(section==='users') {
        rows=await api('/admin/users');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Access</th><th></th></tr></thead><tbody>${rows.map(u=>`<tr><td>${esc(u.full_name)}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${u.is_active?'Active':'Inactive'}</td><td><button class="table-action ${u.is_active?'danger':''}" data-action="admin-user-status" data-id="${u.user_id}" data-active="${!u.is_active}">${u.is_active?'Deactivate':'Activate'}</button></td></tr>`).join('')||'<tr><td colspan="5">No users.</td></tr>'}</tbody></table></div>`;
      } else if(section==='products') {
        rows=await api('/admin/products');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Product</th><th>Farm</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.product_name)}</td><td>${esc(x.farmer_name)}</td><td>${esc(x.category_name)}</td><td>${currency(x.price)} / ${esc(x.unit)}</td><td>${x.available_quantity}</td><td>${esc(x.status)}</td><td><button class="table-action" data-action="admin-product-status" data-id="${x.product_id}" data-status="${x.status==='active'?'inactive':'active'}">${x.status==='active'?'Pause':'Activate'}</button><button class="table-action danger" data-action="admin-product-delete" data-id="${x.product_id}">Remove</button></td></tr>`).join('')||'<tr><td colspan="7">No products.</td></tr>'}</tbody></table></div>`;
      } else if(section==='categories') {
        rows=await api('/admin/categories');
        panel.innerHTML=`<div class="dashboard-toolbar"><span class="chart-legend">Eight seed categories; categories with products cannot be deleted.</span><button class="table-action" data-action="admin-category-create">Add category</button></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Name</th><th>Description</th><th></th></tr></thead><tbody>${rows.map(c=>`<tr><td>${esc(c.category_name)}</td><td>${esc(c.description)}</td><td><button class="table-action" data-action="admin-category-edit" data-id="${c.category_id}" data-name="${esc(c.category_name)}" data-description="${esc(c.description)}">Edit</button><button class="table-action danger" data-action="admin-category-delete" data-id="${c.category_id}">Delete</button></td></tr>`).join('')||'<tr><td colspan="3">No categories.</td></tr>'}</tbody></table></div>`;
      } else if(section==='farmers') {
        rows=await api('/admin/farmers');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Farm</th><th>Owner</th><th>Mobile</th><th>Area</th><th>Status</th><th>Decision</th></tr></thead><tbody>${rows.map(f=>`<tr><td>${esc(f.farm_name)}</td><td>${esc(f.user.full_name)}</td><td>${phoneLink(f.user.phone)}</td><td>${esc(f.farm_location)}</td><td>${esc(f.verification_status)}</td><td>${f.verification_status==='pending'?`<button class="table-action" data-action="approve-farmer" data-id="${f.farmer_id}" data-decision="approved">Approve</button><button class="table-action danger" data-action="approve-farmer" data-id="${f.farmer_id}" data-decision="rejected">Reject</button>`:`<button class="table-action" data-action="approve-farmer" data-id="${f.farmer_id}" data-decision="pending">Set pending</button>`}</td></tr>`).join('')||'<tr><td colspan="6">No farm profiles.</td></tr>'}</tbody></table></div>`;
      } else if(section==='orders') {
        rows=await api('/orders');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Area / slot</th><th>Date</th><th>Status</th><th>Total</th><th></th></tr></thead><tbody>${rows.map(o=>`<tr><td>${esc(o.order_number)}</td><td>${esc(o.city)} · ${esc(o.delivery_slot)}</td><td>${fmtDate(o.delivery_date)}</td><td>${esc(o.order_status)}</td><td>${currency(o.total_amount)}</td><td>${o.delivery?.delivery_id && !['Delivered','Cancelled','Rejected'].includes(o.order_status)?`<button class="table-action" data-action="admin-order-status" data-delivery="${o.delivery.delivery_id}" data-status="${esc(o.order_status)}">Update status</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="6">No orders.</td></tr>'}</tbody></table></div>`;
      } else if(section==='subscriptions') {
        rows=await api('/admin/subscriptions');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Customer</th><th>Basket</th><th>Next delivery</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.user.full_name)}</td><td>${esc(x.plan_name)}</td><td>${fmtDate(x.next_delivery_date)}</td><td>${esc(x.status)}</td><td>${x.status==='active'?`<button class="table-action warn" data-action="sub-pause" data-id="${x.subscription_id}">Pause</button>`:x.status==='paused'?`<button class="table-action" data-action="sub-resume" data-id="${x.subscription_id}">Resume</button>`:''}${x.status!=='cancelled'?`<button class="table-action danger" data-action="sub-cancel" data-id="${x.subscription_id}">Cancel</button>`:''}</td></tr>`).join('')||'<tr><td colspan="5">No subscriptions.</td></tr>'}</tbody></table></div>`;
      } else if(section==='deliveries') {
        rows=await api('/admin/deliveries');
        panel.innerHTML=`<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Order</th><th>Route group</th><th>Stop</th><th>ETA</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.order.order_number)} · ${esc(x.order.city)}</td><td>${esc(x.route_group||'Neighborhood')}</td><td>${x.route_sequence||'—'}</td><td>${esc(x.estimated_time||'—')}</td><td>${esc(x.delivery_status)}</td><td>${!['Delivered','Cancelled','Rejected'].includes(x.delivery_status)?`<button class="table-action" data-action="admin-delivery-status" data-id="${x.delivery_id}" data-status="${esc(x.delivery_status)}">Update status</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="6">No deliveries.</td></tr>'}</tbody></table></div>`;
      } else if(section==='slots') {
        rows=await api('/admin/slots');
        panel.innerHTML=`<div class="dashboard-toolbar"><span class="chart-legend">Capacity is enforced at checkout for each delivery date.</span><button class="table-action" data-action="manage-slots">Edit all capacities</button></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Window</th><th>Hours</th><th>Max orders</th><th>Status</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.slot_name)}</td><td>${x.start_time}–${x.end_time}</td><td>${x.max_orders}</td><td>${esc(x.status)}</td></tr>`).join('')||'<tr><td colspan="4">No slots.</td></tr>'}</tbody></table></div>`;
      }
    } catch(error) { panel.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function adminUserStatus(id,isActive) {
    try { await api(`/admin/users/${id}/status`,{method:'PUT',body:{is_active:isActive}}); toast('User access updated.'); loadAdminSection('users'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminProductStatus(id,status) {
    try { await api(`/products/${id}`,{method:'PUT',body:{status}}); toast(`Product ${status==='active'?'activated':'paused'}.`); loadAdminSection('products'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminProductDelete(id) {
    if(!window.confirm('Remove this listing from the marketplace? Order history will be retained.'))return;
    try { await api(`/products/${id}`,{method:'DELETE'}); toast('Product removed.'); loadAdminSection('products'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminCategoryCreate() {
    const name=window.prompt('New category name:'); if(name===null)return;
    const description=window.prompt('Short description:','Seasonal local produce'); if(description===null)return;
    try { await api('/admin/categories',{method:'POST',body:{category_name:name,description}}); toast('Category created.'); loadAdminSection('categories'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminCategoryEdit(id,name,description) {
    const nextName=window.prompt('Category name:',name); if(nextName===null)return;
    const nextDescription=window.prompt('Short description:',description); if(nextDescription===null)return;
    try { await api(`/admin/categories/${id}`,{method:'PUT',body:{category_name:nextName,description:nextDescription}}); toast('Category updated.'); loadAdminSection('categories'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminCategoryDelete(id) {
    if(!window.confirm('Delete this category? Categories containing products cannot be removed.'))return;
    try { await api(`/admin/categories/${id}`,{method:'DELETE'}); toast('Category deleted.'); loadAdminSection('categories'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminOrderStatus(deliveryId,current) {
    const choices=['Confirmed','Preparing','Out for Delivery','Delivered','Cancelled','Rejected'];
    const suggestion=current==='Placed'?'Confirmed':choices[(choices.indexOf(current)+1+choices.length)%choices.length];
    const next=window.prompt(`Enter order status: ${choices.join(', ')}`,suggestion); if(next===null)return;
    try { await api(`/delivery/${deliveryId}/status`,{method:'PUT',body:{status:next.trim()}}); toast(`Order marked ${next.trim()}.`); loadAdminSection('orders'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminDeliveryStatus(id,current) { return adminOrderStatus(id,current); }
  async function farmerStatus(deliveryId,status) {
    try { await api(`/delivery/${deliveryId}/status`,{method:'PUT',body:{status}}); toast(`Order updated to ${status}.`); loadDashboard(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function addFarmerProduct(event) {
    event.preventDefault(); const f=event.target; if(!(f instanceof HTMLFormElement)) return;
    const fd=new FormData(f), button=$('button[type="submit"]',f);
    setBusy(button,true,'Saving');
    try {
      const selected=fd.get('product_image'), photo=selected instanceof File&&selected.size>0?selected:null;
      if(photo&&photo.size>MAX_PRODUCT_PHOTO_BYTES)throw new Error('Product images must be 5 MB or smaller.');
      const created=await api('/products',{method:'POST',body:{product_name:fd.get('product_name'),category_id:Number(fd.get('category_id')),price:Number(fd.get('price')),unit:fd.get('unit'),available_quantity:Number(fd.get('available_quantity')),organic:fd.has('organic'),image_url:photo?'':String(fd.get('image_url')||'').trim()}});
      if(photo){
        const upload=new FormData(); upload.append('product_image',photo,photo.name);
        try { await api(`/products/${created.product_id}/image`,{method:'POST',body:upload}); toast('Produce and photo added.'); }
        catch(uploadError) { toast(`Produce was added, but the photo could not be uploaded: ${uploadError.message}. Use Upload photo on the listing to retry.`,'error'); }
      } else toast('Produce added to your listings.');
      loadDashboard();
    }
    catch(error) { toast(error.message,'error'); }
    finally { setBusy(button,false); }
  }
  function uploadProductImage(id) {
    const picker=document.createElement('input'); picker.type='file'; picker.accept='.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';
    picker.addEventListener('change',async()=>{
      const photo=picker.files?.[0]; if(!photo)return;
      if(photo.size>MAX_PRODUCT_PHOTO_BYTES){toast('Product images must be 5 MB or smaller.','error');return;}
      const upload=new FormData(); upload.append('product_image',photo,photo.name);
      try { await api(`/products/${id}/image`,{method:'POST',body:upload}); toast('Product photo uploaded.'); loadDashboard(); }
      catch(error) { toast(error.message,'error'); }
    });
    picker.click();
  }
  async function loadNotificationsPage() {
    const target=$('#notificationsList'); if (!me) { target.innerHTML='<div class="signed-out-note">Sign in to see account updates.</div>'; return; }
    try { const d=await api('/notifications'); target.innerHTML=d.items.map(n=>`<article class="notification-item ${n.is_read?'':'unread'}"><span class="notification-icon"><i class="bi bi-bell"></i></span><div><h3>${esc(n.title)}</h3><p>${esc(n.message)}</p></div><small>${new Date(n.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short'})}</small>${!n.is_read?`<button class="table-action" data-action="notification-read" data-id="${n.notification_id}">Mark read</button>`:''}</article>`).join('') || '<div class="signed-out-note">No notifications just yet.</div>'; $('#notificationDot').hidden = d.unread_count===0; }
    catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  async function loadNotificationBadge() {
    if (!me) { $('#notificationDot').hidden=true; return; }
    try { const d=await api('/notifications'); $('#notificationDot').hidden=d.unread_count===0; } catch { $('#notificationDot').hidden=true; }
  }
  async function showNotificationModal() {
    if (!me) { openAuth('login'); return; }
    try { const d=await api('/notifications'); $('#notificationModalList').innerHTML=d.items.slice(0,5).map(n=>`<div class="mini-notification"><b>${esc(n.title)}</b><p>${esc(n.message)}</p><small>${new Date(n.created_at).toLocaleString('en-IN')}</small></div>`).join('') || '<p>No updates yet.</p>'; showModal('notificationModal'); }
    catch(error) { toast(error.message,'error'); }
  }
  async function markNotification(id) { try { await api(`/notifications/${id}/read`,{method:'PUT'}); loadNotificationsPage(); loadNotificationBadge(); } catch(error) { toast(error.message,'error'); } }
  async function loadProductModal(id) {
    try { const p=await api(`/products/${id}`); currentProduct=p;
      const reviews=await api(`/reviews/${id}`);
      $('#productModalBody').innerHTML=`<div class="product-dialog-body"><div class="product-dialog-art">${artFor(p)}</div><div class="product-dialog-copy"><span class="eyebrow">${esc(p.category_name)} ${p.organic?'· ORGANIC':''}</span><h2 id="productDialogTitle">${esc(p.product_name)}</h2><div class="product-meta"><span>${esc(p.farmer_name)} · ${esc(p.farmer_location)}</span><span class="product-rating">★ ${reviews.average_rating || 'New'}</span></div><p>${esc(p.description)}</p><strong class="product-price">${currency(p.price)} <small>/ ${esc(p.unit)}</small></strong><p class="route-tag">${p.available_quantity<=5?`Only ${p.available_quantity} left`:'Fresh stock available'}</p><button class="btn btn-primary" data-action="add-cart" data-id="${p.product_id}">Add to basket <i class="bi bi-plus-lg"></i></button></div></div><div style="margin-top:20px"><b style="font-size:11px">Neighbor notes (${reviews.review_count})</b>${reviews.reviews.slice(0,3).map(r=>`<p style="font-size:10px;margin:8px 0 0">★ ${r.rating} · ${esc(r.user_name)} — ${esc(r.comment)}</p>`).join('') || '<p style="font-size:10px">Be the first to share a note after your delivery.</p>'}</div>`;
      showModal('productModal');
    } catch(error) { toast(error.message,'error'); }
  }
  async function loadTracking(orderId) {
    const target=$('#trackingContent'); if (!orderId || !me) { target.innerHTML='<div class="signed-out-note">Sign in and choose an order to see its route.</div>'; return; }
    try { const d=await api(`/delivery/${orderId}`); const status=d.delivery.status; const steps=['Placed','Confirmed','Preparing','Out for Delivery','Delivered']; const current=steps.indexOf(status);
      target.innerHTML=`<div class="tracking-grid"><div class="tracking-map" id="trackingMap"></div><section class="tracking-detail"><span class="eyebrow">ORDER ${esc(d.order.order_number)}</span><h2>${esc(d.order.city)} · ${esc(d.order.delivery_slot)}</h2><p style="font-size:10px">Planned for ${fmtDate(d.order.delivery_date)} · ${esc(d.order.delivery_address)}</p><div class="tracking-progress">${steps.map((s,i)=>`<div class="progress-step ${i<current?'done':i===current?'current':''}"><span class="progress-dot">${i<current?'✓':i+1}</span><div><b>${s}</b><small>${i===current?'Current update':i<current?'Completed':'Up next'}</small></div></div>`).join('')}</div><div class="route-note"><b>Smart Delivery Optimization</b><br>Rule-based route group: ${esc(d.delivery.route_group || 'Neighborhood route')}. Sequence stop ${d.delivery.route_sequence || 1}; estimated ${esc(d.delivery.estimated_time || 'to be updated')}. Simulated map position.</div></section></div>`;
      setTimeout(()=>initTrackingMap(d.route),40);
    } catch(error) { target.innerHTML=`<div class="signed-out-note">${esc(error.message)}</div>`; }
  }
  function initHomeMap() {
    const node=$('#homeMap'); if (!window.L || !node) return;
    if (homeMap) { setTimeout(()=>homeMap.invalidateSize(),40); return; }
    homeMap=L.map(node,{scrollWheelZoom:false,zoomControl:false}).setView([19.286,72.852],12);
    L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a> · <a href="https://www.openstreetmap.de/germanstyle.html">OpenStreetMap.de</a>',maxZoom:19}).addTo(homeMap);
    const pts=[[19.2900,72.8500],[19.284,72.867],[19.300,72.855],[19.276,72.861],[19.265,72.868]];
    pts.forEach((pt,i)=>L.circleMarker(pt,{radius:i?7:9,color:'#fff',weight:3,fillColor:i?'#F2A93B':'#1F6B45',fillOpacity:1}).addTo(homeMap).bindPopup(i?`Neighborhood stop ${i}`:'Farm hub · Mira-Bhayandar'));
    L.polyline(pts,{color:'#1F6B45',weight:3,dashArray:'7 8',opacity:.8}).addTo(homeMap);
  }
  function initTrackingMap(route) {
    if (!window.L || !$('#trackingMap')) return;
    if (trackingMap) { trackingMap.remove(); trackingMap=null; }
    const points=[]; if (route?.origin) points.push([route.origin.lat,route.origin.lng]);
    (route?.stops || []).forEach(stop=>points.push([stop.lat,stop.lng]));
    if (!points.length && route?.customer) points.push([route.customer.lat,route.customer.lng]);
    trackingMap=L.map('trackingMap',{scrollWheelZoom:false}).setView(points[0]||[19.286,72.852],12);
    L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a> · <a href="https://www.openstreetmap.de/germanstyle.html">OpenStreetMap.de</a>',maxZoom:19}).addTo(trackingMap);
    points.forEach((pt,i)=>L.circleMarker(pt,{radius:i?7:9,color:'#fff',weight:3,fillColor:i?'#F2A93B':'#1F6B45',fillOpacity:1}).addTo(trackingMap).bindPopup(i?`Delivery stop ${i}`:'Farm hub'));
    if(points.length>1){L.polyline(points,{color:'#1F6B45',weight:4,dashArray:'8 8'}).addTo(trackingMap);trackingMap.fitBounds(points,{padding:[24,24]});}
  }
  async function adminFarmerDecision(id, decision) {
    try { await api(`/admin/farmers/${id}`,{method:'PUT',body:{verification_status:decision}}); toast(`Farm profile ${decision}.`); loadAdminDashboard(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function adminRunRenewals() {
    try { const result=await api('/admin/run-subscriptions',{method:'POST',body:{}}); toast(`Renewal check complete · ${result.created_order_ids.length} order(s) created.`); loadAdminDashboard(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function manageSlots() {
    try { const slots=await api('/admin/slots');
      for (const slot of slots) {
        const answer=window.prompt(`${slot.slot_name} capacity (currently ${slot.max_orders}; type a new number, or leave blank to skip):`,String(slot.max_orders));
        if (answer===null) break; if (!answer.trim() || Number(answer)===slot.max_orders) continue;
        await api(`/admin/slots/${slot.slot_id}`,{method:'PUT',body:{max_orders:Number(answer)}});
      }
      toast('Delivery slot settings saved.'); loadAdminDashboard();
    } catch(error) { toast(error.message,'error'); }
  }
  async function editStock(id, current) {
    const value=window.prompt('Set the new available stock quantity:',String(current)); if (value===null) return;
    try { await api(`/products/${id}`,{method:'PUT',body:{available_quantity:Number(value)}}); toast('Stock updated.'); loadDashboard(); }
    catch(error) { toast(error.message,'error'); }
  }
  async function editProduct(id) {
    try {
      const p=await api(`/products/${id}`);
      const name=window.prompt('Product name:',p.product_name); if(name===null)return;
      const price=window.prompt('Price (₹):',String(p.price)); if(price===null)return;
      const unit=window.prompt('Unit (kg, bunch, pack…):',p.unit); if(unit===null)return;
      const stock=window.prompt('Available quantity:',String(p.available_quantity)); if(stock===null)return;
      const organic=window.prompt('Organic? Enter yes or no:',p.organic?'yes':'no'); if(organic===null)return;
      const imageUrl=window.prompt('Direct public image URL (leave blank to clear):',p.image_url||''); if(imageUrl===null)return;
      const number=Number(price),quantity=Number(stock);
      if(!name.trim()||!Number.isFinite(number)||number<=0||!Number.isInteger(quantity)||quantity<0||!unit.trim()||!['yes','no'].includes(organic.trim().toLowerCase())||(imageUrl.trim()&&!safeImageUrl(imageUrl.trim())))throw new Error('Enter valid product details and a direct HTTP or HTTPS image URL, or leave the image URL blank.');
      await api(`/products/${id}`,{method:'PUT',body:{product_name:name.trim(),price:number,unit:unit.trim(),available_quantity:quantity,organic:organic.trim().toLowerCase()==='yes',image_url:imageUrl.trim()}});
      toast('Product details updated.'); loadDashboard();
    } catch(error) { toast(error.message,'error'); }
  }
  async function deleteProduct(id) {
    if (!window.confirm('Remove this listing from the marketplace? Order history will be retained.')) return;
    try { await api(`/products/${id}`,{method:'DELETE'}); toast('Product removed.'); loadDashboard(); }
    catch(error) { toast(error.message,'error'); }
  }
  function initReveals() {
    if (!('IntersectionObserver' in window)) { $$('.reveal').forEach(x=>x.classList.add('in-view')); return; }
    const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in-view');observer.unobserve(e.target);}}),{threshold:.12});
    $$('.reveal').forEach(el=>observer.observe(el));
  }
  const testimonials=[
    {initial:'A',name:'Aditi K.',place:'Mira Road',text:'We love knowing who grew our vegetables. The morning slot is reliable, and the greens taste like they were picked for our kitchen.'},
    {initial:'N',name:'Neel J.',place:'Bhayandar East',text:'The basket makes weekday cooking feel easier. I can see the farms, plan the delivery and pause whenever our routine changes.'},
    {initial:'S',name:'Sara F.',place:'Kashimira',text:'Fresh produce, thoughtful packing and a route that arrives when promised. It feels good to support growers from our side of town.'}
  ]; let testimonialIndex=0;
  function setTestimonial(index){testimonialIndex=(index+testimonials.length)%testimonials.length;const t=testimonials[testimonialIndex];const card=$('#testimonialCard');if(!card)return;card.querySelector('blockquote').textContent=t.text;card.querySelector('.testimonial-author .avatar').textContent=t.initial;card.querySelector('.testimonial-author b').textContent=t.name;card.querySelector('.testimonial-author small').textContent=`${t.place} · Farm2Home customer`;}
  async function login(email,password) { const data=await api('/auth/login',{method:'POST',body:{email,password}}); me=data.user; syncHeader(); closeModal('authModal'); toast(`Welcome, ${me.full_name.split(' ')[0]}.`); if(currentRoute==='/admin'||me.role==='admin')navigate('/dashboard');else if(currentRoute==='/')loadProducts('featuredProducts','',4); else showPage(pageForPath(currentRoute)); }
  async function submitAuth(event) {
    event.preventDefault();const form=event.currentTarget,fd=new FormData(form),mode=$('.auth-tab.active')?.dataset.authMode||'login',button=$('#authSubmit');setBusy(button,true,mode==='register'?'Creating account':'Signing in');
    try {
      if(mode==='login') await login(fd.get('email'),fd.get('password'));
      else { const phone=String(fd.get('phone')||''); if(!/^\d{10}$/.test(phone))throw new Error('Phone number must be exactly 10 digits.');
        const role=fd.get('role'); const payload={full_name:fd.get('full_name'),email:fd.get('email'),password:fd.get('password'),phone,role,city:fd.get('city'),pincode:fd.get('pincode'),farm_name:fd.get('farm_name'),farm_location:fd.get('farm_location')};
        const data=await api('/auth/register',{method:'POST',body:payload});me=data.user;syncHeader();closeModal('authModal');toast(role==='farmer'?'Farm profile submitted for approval.':'Your account is ready.');if(role==='farmer')navigate('/dashboard');
      }
    } catch(error) { toast(error.message,'error'); }
    finally { setBusy(button,false); }
  }
  async function logout() { try { await api('/auth/logout',{method:'POST',body:{}}); } catch {} me=null;currentCart=null;syncHeader();toast('You have signed out.');navigate('/'); }
  function handleClick(event) {
    const route=event.target.closest('[data-route]');
    if(route){event.preventDefault();navigate(route.dataset.route);if(route.id==='navSearchButton')setTimeout(()=>$('#productSearch')?.focus(),250);return;}
    const scroll=event.target.closest('[data-scroll]');if(scroll){event.preventDefault();const id=scroll.dataset.scroll,route=scroll.dataset.scrollRoute;if(route&&location.pathname!==route)navigate(route);else if(!route&&location.pathname!=='/')navigate('/');const revealTarget=(attempt=0)=>{const target=document.querySelector(id);if(target){target.scrollIntoView({behavior:'smooth'});return;}if(attempt<40)setTimeout(()=>revealTarget(attempt+1),100);};setTimeout(()=>revealTarget(),30);return;}
    const close=event.target.closest('[data-close]');if(close){closeModal(close.dataset.close);return;}
    const authMode=event.target.closest('[data-auth-mode]');if(authMode){setAuthMode(authMode.dataset.authMode);return;}
    const demo=event.target.closest('[data-demo-login]');if(demo){const role=demo.dataset.demoLogin;const email=role==='consumer'?'consumer@farm2home.test':role==='admin'?'admin@farm2home.test':'farmer1@farm2home.test';login(email,'Farm2Home123!').catch(e=>toast(e.message,'error'));return;}
    const action=event.target.closest('[data-action]');if(action){const {action:kind,id,item,qty,plan,order,product,delivery,status,decision,section,review,rating,comment,active,name,description}=action.dataset;
      if(kind==='add-cart')addToCart(Number(id),action);if(kind==='product-detail')loadProductModal(Number(id));
      if(kind==='quantity')changeQuantity(Number(item),Number(qty));if(kind==='remove-cart')removeCart(Number(item));
      if(kind==='subscribe')subscribe(Number(plan));if(kind==='sub-pause'||kind==='sub-resume'||kind==='sub-cancel'||kind==='sub-renew')subscriptionAction(kind,Number(id));
      if(kind==='track')navigate(`/track/${id}`);if(kind==='review-order')openReview(order,product);
      if(kind==='farmer-status')farmerStatus(Number(delivery),status);if(kind==='approve-farmer')adminFarmerDecision(Number(id),decision);
      if(kind==='run-renewals')adminRunRenewals();if(kind==='manage-slots')manageSlots();
      if(kind==='product-stock')editStock(Number(id),Number(action.dataset.stock));if(kind==='delete-product')deleteProduct(Number(id));
      if(kind==='notification-read')markNotification(Number(id));
      if(kind==='edit-review')editReview(Number(review),Number(rating),comment||'');
      if(kind==='delete-review')deleteReview(Number(review));
      if(kind==='product-edit')editProduct(Number(id));
      if(kind==='product-image')uploadProductImage(Number(id));
      if(kind==='admin-section')loadAdminSection(section);
      if(kind==='admin-user-status')adminUserStatus(Number(id),active==='true');
      if(kind==='admin-product-status')adminProductStatus(Number(id),status);
      if(kind==='admin-product-delete')adminProductDelete(Number(id));
      if(kind==='admin-category-create')adminCategoryCreate();
      if(kind==='admin-category-edit')adminCategoryEdit(Number(id),name||'',description||'');
      if(kind==='admin-category-delete')adminCategoryDelete(Number(id));
      if(kind==='admin-order-status')adminOrderStatus(Number(delivery),status);
      if(kind==='admin-delivery-status')adminDeliveryStatus(Number(id),status);
      return;
    }
  }
  function init() {
    document.addEventListener('error',event=>{
      const image=event.target;
      if(image instanceof HTMLImageElement&&image.classList.contains('product-photo')){
        const fallback=document.createElement('span'); fallback.className='produce-emoji'; fallback.textContent=image.dataset.fallback||'🥗'; image.replaceWith(fallback);
      }
    },true);
    document.addEventListener('click',handleClick);
    $('#loginOpen').addEventListener('click',()=>openAuth('login'));$('#registerOpen').addEventListener('click',()=>openAuth('register'));
    $('#farmerJoinButton').addEventListener('click',()=>{openAuth('register');$('#registerRole').value='farmer';toggleFarmerFields('farmer');});
    $('#farmerJoinPageButton').addEventListener('click',()=>{openAuth('register');$('#registerRole').value='farmer';toggleFarmerFields('farmer');});
    $('#logoutButton').addEventListener('click',logout);$('#notificationButton').addEventListener('click',showNotificationModal);
    $('#mobileMenuToggle').addEventListener('click',()=>{const open=$('#mainNav').classList.toggle('open');$('#mobileMenuToggle').setAttribute('aria-expanded',String(open));});
    $('#profileTrigger').addEventListener('click',()=>{const menu=$('.profile-dropdown');menu.hidden=!menu.hidden;});
    $('#authForm').addEventListener('submit',submitAuth);$('#registerRole').addEventListener('change',e=>toggleFarmerFields(e.target.value));
    $('#checkoutButton').addEventListener('click',()=>navigate('/checkout'));$('#checkoutForm').addEventListener('submit',placeOrder);$('#deliveryDate').addEventListener('change',loadSlots);
    $('#productSearch').addEventListener('input',()=>loadProducts('shopProducts',$('#productSearch').value,100));$('#categoryFilter').addEventListener('change',loadShop);$('#sortFilter').addEventListener('change',loadShop);$('#organicFilter').addEventListener('change',loadShop);
    $('#dashboardRefresh').addEventListener('click',loadDashboard);$('#adminRefresh').addEventListener('click',loadAdminDashboard);
    $('#notificationModal').addEventListener('click',e=>{if(e.target===$('#notificationModal'))closeModal('notificationModal');});
    $$('.modal-backdrop').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)closeModal(m.id);}));
    document.addEventListener('keydown',e=>{if(e.key==='Escape')$$('.modal-backdrop:not([hidden])').forEach(m=>closeModal(m.id));if(e.key==='Enter'&&e.target.matches('[data-action="product-detail"]'))loadProductModal(Number(e.target.dataset.id));});
    $('#testimonialPrev').addEventListener('click',()=>setTestimonial(testimonialIndex-1));$('#testimonialNext').addEventListener('click',()=>setTestimonial(testimonialIndex+1));
    $('#helpButton').addEventListener('click',()=>toast('Need help? This demo uses simulated payments and route locations. Email hello@farm2home.test.'));
    document.addEventListener('submit',e=>{if(e.target.id==='farmerProductForm')addFarmerProduct(e);});
    window.addEventListener('popstate',()=>{currentRoute=location.pathname;showPage(pageForPath(currentRoute));});
    window.addEventListener('scroll',()=>$('#siteHeader').classList.toggle('scrolled',window.scrollY>14),{passive:true});
    refreshMe().then(()=>{currentRoute=location.pathname;showPage(pageForPath(currentRoute));});
    initReveals();initHomeMap();
  }
  window.openFarmAuth=()=>openAuth('login');
  window.addEventListener('DOMContentLoaded',init);
})();
