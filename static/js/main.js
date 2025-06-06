let cart = JSON.parse(localStorage.getItem('cart')) || [];
let products = [];

// Load categories from backend
function loadCategories() {
  fetch('/api/categories')
    .then(res => res.json())
    .then(categories => {
      const list = document.getElementById('categoryList');
      const menu = document.getElementById('productCategoriesMenu');
      list.innerHTML = '<li class="list-group-item list-group-item-action" onclick="loadProducts()">All</li>';
      menu.innerHTML = '<li><a class="dropdown-item" href="#" onclick="loadProducts()">All</a></li>';
      categories.forEach(cat => {
        list.innerHTML += `<li class="list-group-item list-group-item-action" onclick="loadProducts('${cat.name}')">${cat.name}</li>`;
        menu.innerHTML += `<li><a class="dropdown-item" href="#" onclick="loadProducts('${cat.name}')">${cat.name}</a></li>`;
      });
    });
}

// Load products (optionally filtered)
function loadProducts(category = '', search = '') {
  let url = '/api/products?';
  if (category) url += `category=${encodeURIComponent(category)}&`;
  if (search) url += `search=${encodeURIComponent(search)}`;

  fetch(url)
    .then(res => res.json())
    .then(products => {
      const grid = document.getElementById('productGrid');
      grid.innerHTML = '';
      products.forEach(p => {
        grid.innerHTML += `
          <div class="col-md-4 mb-4">
            <div class="product-card">
              <img src="/static/images/${p.image}" class="product-img mb-2" alt="${p.name}">
              <h5>${p.name}</h5>
              <p class="text-muted">₹${p.price}</p>
              <button class="btn btn-outline-primary btn-sm mb-2" onclick="addToCart(${p.id})">Add to Cart</button>
            </div>
          </div>
        `;
      });
      document.getElementById('cartCount').innerText = cart.reduce((sum, i) => sum + i.qty, 0);
    });
}

// Search products via header search input
function searchProducts() {
  const q = document.getElementById('searchInput').value;
  loadProducts('', q);
}

// Add product to cart
function addToCart(id) {
  const qtyElem = document.getElementById('qty-' + id);
  const addQty = parseInt(qtyElem.innerText);
  const stock = parseInt(document.querySelector(`.qty-plus[data-id="${id}"]`).getAttribute("data-stock"));

  const existing = cart.find(item => item.id === id);
  let currentQty = existing ? existing.qty : 0;

  if (currentQty + addQty > stock) {
    alert(`Cannot add more than available stock (${stock})`);
    return;
  }

  if (existing) {
    existing.qty += addQty;
  } else {
    cart.push({ id: id, qty: addQty });
  }

  localStorage.setItem("cart", JSON.stringify(cart));  // ✅ Persist it
  updateCartCount();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".add-cart-btn").forEach(btn => {
    btn.addEventListener("click", function () {
      const id = parseInt(this.getAttribute("data-id"));
      addToCart(id);
    });
  });
});


function updateCartCount() {
  const totalQty = cart.reduce((sum, i) => sum + i.qty, 0);
  const cartBadge = document.getElementById('cartCount');
  cartBadge.innerText = totalQty;
  cartBadge.style.display = totalQty > 0 ? 'inline-block' : 'none';
}

// Show cart items (simple alert for now)
function showCart() {
  alert('Cart:\n' + cart.map(i => `ID:${i.id} x ${i.qty}`).join('\n'));
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadCategories();
  loadProducts();
});

 
document.addEventListener("DOMContentLoaded", function () {
  // Handle minus button
  document.querySelectorAll(".qty-minus").forEach(btn => {
    btn.addEventListener("click", function () {
      const id = btn.getAttribute("data-id");
      const qtyElem = document.getElementById("qty-" + id);
      let count = parseInt(qtyElem.innerText);
      if (count > 1) {
        count--;
        qtyElem.innerText = count;
        animateQty(qtyElem);
        updateButtons(id, count);
      }
    });
  });

  // Handle plus button
  document.querySelectorAll(".qty-plus").forEach(btn => {
    btn.addEventListener("click", function () {
      const id = btn.getAttribute("data-id");
      const qtyElem = document.getElementById("qty-" + id);
      const max = parseInt(btn.getAttribute("data-stock"));
      let count = parseInt(qtyElem.innerText);
      if (count < max) {
        count++;
        qtyElem.innerText = count;
        animateQty(qtyElem);
        updateButtons(id, count, max);
      }
    });
  });

  // Update enable/disable state of buttons
  function updateButtons(id, count, max = null) {
    const minusBtn = document.querySelector(`.qty-minus[data-id="${id}"]`);
    const plusBtn = document.querySelector(`.qty-plus[data-id="${id}"]`);
    if (!max) {
      const plus = document.querySelector(`.qty-plus[data-id="${id}"]`);
      max = parseInt(plus.getAttribute("data-stock"));
    }
    minusBtn.disabled = count <= 1;
    plusBtn.disabled = count >= max;
  }

  // Animate count
  function animateQty(elem) {
    elem.classList.add("qty-animate");
    setTimeout(() => elem.classList.remove("qty-animate"), 150);
  }

  // Initial check
  document.querySelectorAll(".qty-plus").forEach(btn => {
    const id = btn.getAttribute("data-id");
    const qtyElem = document.getElementById("qty-" + id);
    const count = parseInt(qtyElem.innerText);
    updateButtons(id, count);
  });
});

function fetchProductsAndRenderCart() {
  fetch('/api/products')
    .then(res => res.json())
    .then(data => {
      products = data;
      updateCartUI();
    });
}

document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("cart-body")) {
    fetchProductsAndRenderCart();
  } else {
    updateCartBadge();
  }
});

function updateCartUI() {
  const cartBody = document.getElementById("cart-body");
  if (!cartBody || products.length === 0) return;

  cartBody.innerHTML = "";
  let subtotal = 0;
  let shippingTotal = 0;

  cart.forEach((item, index) => {
    const product = products.find(p => p.id === item.id);
    if (!product) return;

    const itemSubtotal = item.qty * product.price;
    const itemShipping = item.qty * (product.shipping_charge || 0);

    subtotal += itemSubtotal;
    shippingTotal += itemShipping;

    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${index + 1}</td>
      <td>
    <img src="/static/images/${product.image}" style="width: 60px; height: 60px; object-fit: contain;" alt="${product.name}">  
        </td>
      <td class="text-start">${product.name}</td>
      <td>₹${product.price.toFixed(2)}</td>
      <td>
        <div class="d-flex justify-content-center align-items-center gap-1">
          <button class="btn btn-sm btn-outline-secondary" onclick="changeQty(${item.id}, -1)">−</button>
          <span class="px-2" id="qty-${item.id}">${item.qty}</span>
          <button class="btn btn-sm btn-outline-secondary" onclick="changeQty(${item.id}, 1)">+</button>
        </div>
      </td>
      <td>₹${itemSubtotal.toFixed(2)}</td>
      <td>
        <button class="btn btn-sm btn-danger" onclick="removeFromCart(${item.id})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;

    cartBody.appendChild(row);
  });

  // Update totals
  const subtotalElem = document.getElementById("subtotal");
  const shippingElem = document.getElementById("shipping"); 
  const totalElem = document.getElementById("total");

  if (subtotalElem) subtotalElem.innerText = `₹${subtotal.toFixed(2)}`;
  if (shippingElem) shippingElem.innerText = `₹${shippingTotal.toFixed(2)}`;
  if (totalElem) totalElem.innerText = `₹${(subtotal + shippingTotal).toFixed(2)}`;

const checkoutBtn = document.getElementById("checkoutBtn");
if (checkoutBtn) {
  if ((subtotal + shippingTotal) <= 0) {
    checkoutBtn.classList.add("disabled");
    checkoutBtn.setAttribute("aria-disabled", "true");
    checkoutBtn.onclick = (e) => e.preventDefault();  // prevent navigation
  } else {
    checkoutBtn.classList.remove("disabled");
    checkoutBtn.removeAttribute("aria-disabled");
    checkoutBtn.onclick = null;
  }
}

  localStorage.setItem("cart", JSON.stringify(cart));
  updateCartBadge();
}


function changeQty(id, delta) {
  const item = cart.find(i => parseInt(i.id) === parseInt(id));
  const product = products.find(p => parseInt(p.id) === parseInt(id));

  if (!item || !product) return;

  const maxStock = parseInt(product.stock);
  const currentQty = parseInt(item.qty);
  let newQty = currentQty + delta;

  if (newQty < 1) newQty = 1;
  if (newQty > maxStock) {
    alert(`Only ${maxStock} items available in stock.`);
    return;
  }

  item.qty = newQty;
  localStorage.setItem("cart", JSON.stringify(cart));
  updateCartUI();
}

// Admin category new//////////////
function toggleCategoryForm(show) {
  const formSection = document.getElementById('category-form-section');
  if (formSection) {
    formSection.style.display = show ? 'block' : 'none';
    if (show) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }
}

//////////////////////////////////
function removeFromCart(id) {
  const index = cart.findIndex(i => i.id === id);
  if (index >= 0) cart.splice(index, 1);
  updateCartUI();
}

function updateCartBadge() {
  let cart = JSON.parse(localStorage.getItem('cart')) || [];
  const totalQty = cart.reduce((sum, item) => sum + item.qty, 0);

  const badge = document.getElementById('cartCount');
  if (badge) {
    badge.innerText = totalQty;
    badge.style.display = totalQty > 0 ? 'inline-block' : 'none';
  }
}

function toggleAddForm(show) {
  const formCard = document.getElementById('add-form-card');
  const tableSection = document.getElementById('product-table-section');
  const filterSection = document.getElementById('filter-section');
  formCard.style.display = show ? 'block' : 'none';
  tableSection.style.display = show ? 'none' : 'block';
  filterSection.style.display = show ? 'none' : 'block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
 }

function resetFormAndShow(show) {
    const form = document.getElementById('productForm');
    form.reset();
    form.action = "/admin/add_product";
    document.getElementById('formSubmitBtn').innerText = "Add";
    document.getElementById('form-subtitle').innerText = "Add New Product";

    // ✅ Set default values
    document.getElementById('stock').value = 1;
    document.getElementById('shipping_charge').value = 0.0;
    document.querySelector('input[name="image"]').required = true;

    toggleAddForm(show);
  }

function loadEditForm(button) {
  document.getElementById('productForm').action = `/admin/edit_product/${button.dataset.id}`;
  document.getElementById('name').value = button.dataset.name;
  document.getElementById('price').value = button.dataset.price;
  document.getElementById('stock').value = button.dataset.stock;
  document.getElementById('category_id').value = button.dataset.category; 
  document.getElementById('description').value = button.dataset.description || "";
  document.getElementById('shipping_charge').value = button.dataset.shipping || 0;

  const subSelect = document.getElementById('sub_category_id');
  const categoryId = button.dataset.category;
  const subcategoryId = button.dataset.subcategory;

  const currentImage = button.dataset.image;
  document.getElementById("currentImage").innerText = currentImage ? `Current: ${currentImage}` : "No image uploaded";

  document.querySelector('input[name="image"]').required = false;
    // Fetch subcategories and preselect
  fetch(`/admin/get_subcategories/${categoryId}`)
    .then(res => res.json())
    .then(data => {
      if (data.subcategories.length > 0) {
        subSelect.innerHTML = '<option value="">-- Select Subcategory --</option>';
        data.subcategories.forEach(sub => {
          const opt = document.createElement('option');
          opt.value = sub.id;
          opt.textContent = sub.name;
          subSelect.appendChild(opt);
        });
        subSelect.disabled = false;
        subSelect.setAttribute('required', 'required');
        subSelect.value = subcategoryId;
      } else {
        subSelect.innerHTML = '<option value="">No subcategories</option>';
        subSelect.disabled = true;
        subSelect.removeAttribute('required');
      }
    });
  
  document.getElementById('formSubmitBtn').innerText = "Update";
  document.getElementById('form-subtitle').innerText = "Edit Product";
  toggleAddForm(true);
}

function lookupPincodeDetails() {
  const pin = document.getElementById('pincode').value;
  if (pin.length === 6) {
    fetch(`https://api.postalpincode.in/pincode/${pin}`)
      .then(res => res.json())
      .then(data => {
        if (data[0].Status === "Success") {
          const info = data[0].PostOffice[0];
          document.getElementById('city').value = info.District;
          document.getElementById('state').value = info.State;
        } else {
          alert("Invalid Pincode");
          document.getElementById('city').value = '';
          document.getElementById('state').value = '';
        }
      });
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const pincodeInput = document.querySelector('input[name="pincode"]');
  const cityInput = document.querySelector('input[name="city"]');
  const stateInput = document.querySelector('input[name="state"]');

  pincodeInput.addEventListener('blur', function () {
    const pincode = this.value.trim();
    if (pincode.length === 6 && /^\d+$/.test(pincode)) {
      fetch(`https://api.postalpincode.in/pincode/${pincode}`)
        .then(res => res.json())
        .then(data => {
          if (data[0].Status === "Success") {
            const postOffice = data[0].PostOffice[0];
            cityInput.value = postOffice.District;
            stateInput.value = postOffice.State;
          } else {
            cityInput.value = '';
            stateInput.value = '';
            alert("Invalid Pincode");
          }
        });
    } else {
      cityInput.value = '';
      stateInput.value = '';
    }
  });

  // Optional: Prevent non-numeric input for phone and pincode
  document.querySelector('input[name="phone"]').addEventListener('input', function () {
    this.value = this.value.replace(/\D/g, '').slice(0, 10);
  });

  document.querySelector('input[name="pincode"]').addEventListener('input', function () {
    this.value = this.value.replace(/\D/g, '').slice(0, 6);
  });
});

function updateCheckoutSummary() {
  const cart = JSON.parse(localStorage.getItem("cart") || "[]");

  fetch("/api/products")
    .then(res => res.json())
    .then(products => {
      let subtotal = 0;
      let shippingTotal = 0;

      cart.forEach(item => {
        const product = products.find(p => p.id === item.id);
        if (product) {
          subtotal += product.price * item.qty;
          shippingTotal += (product.shipping_charge || 0) * item.qty;
        }
      });

      document.getElementById("subtotal").innerText = `₹${subtotal.toFixed(2)}`;
      document.getElementById("shipping").innerText = `₹${shippingTotal.toFixed(2)}`;
      document.getElementById("total").innerText = `₹${(subtotal + shippingTotal).toFixed(2)}`;
    });
}

// RazorPay payment
document.addEventListener("DOMContentLoaded", function () {

  if (document.getElementById("rzp-button1")) {
    updateCheckoutSummary(); 
  }

  const payBtn = document.getElementById("rzp-button1");
  if (payBtn) {
    payBtn.addEventListener("click", async function () { 
      const addressId = document.querySelector("select[name='address_id']").value;
      const cart = JSON.parse(localStorage.getItem("cart") || "[]");

      const response = await fetch("/create_razorpay_order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart, address_id: addressId })
      });

      const data = await response.json();
      if (!data.success) {
        alert("Failed to create order: " + data.message);
        return;
      }
    
      const options = { 
        Key:window.RAZORPAY_KEY,
        amount: data.amount, // in paise
        currency: "INR",
        name: "BuySell App",
        description: "Order Payment",
        order_id: data.razorpay_order_id,
        handler: async function (response) {
 
          const confirmRes = await fetch("/checkout/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              address_id: addressId,
              cart: cart
            })
          });

          const result = await confirmRes.json();
          if (result.success) {
            window.location.href = "/order-success?order_id=" + result.order_id;
          } else {
            alert("Payment succeeded but order failed to save.");
          }
        },
        prefill: {
          name: "",
          email: "",
          contact: ""
        },
        theme: {
          color: "#343a40"
        }
      };

      const rzp = new Razorpay(options);
      rzp.open();
    });
  }
});

// Product description card ////////////
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('.product-click-area').forEach(card => {
    card.addEventListener('click', function () {
      const data = JSON.parse(this.getAttribute('data-product'));

      document.getElementById('modalImage').src = '/static/images/' + data.image;
      document.getElementById('modalPrice').innerText = data.price.toFixed(2);
      document.getElementById('modalStock').innerText = data.stock;
      document.getElementById('modalShipping').innerText = (data.shipping_charge || 0).toFixed(2);

      const descList = document.getElementById('modalDescription');
      descList.innerHTML = '';
      if (data.description) {
        const lines = data.description.split(/\r?\n|•/).filter(Boolean);
        lines.forEach(line => {
          const li = document.createElement('li');
          li.textContent = line.trim();
          descList.appendChild(li);
        });
      }

      const modal = new bootstrap.Modal(document.getElementById('productModal'));
      modal.show();
    });
  });
});

// Contact form spinner //////////////////////
document.addEventListener("DOMContentLoaded", function () {
  const contactForm = document.querySelector("form[action='/contact']");

  if (contactForm) {
    contactForm.addEventListener("submit", function () {
      const modal = new bootstrap.Modal(document.getElementById("sendingModal"));
      modal.show();
    });
  }
});

/////////////////////////////////////////////

// Forgot password form spinner //////////////////////
document.addEventListener("DOMContentLoaded", function () {
  const forgotForm = document.getElementById("forgotForm");

  if (forgotForm) {
    forgotForm.addEventListener("submit", function () {
      const btn = document.getElementById("sendPasswordBtn");
      const text = document.getElementById("sendText");
      const spinner = document.getElementById("sendSpinner");

      btn.disabled = true;
      text.textContent = "Please wait...";
      spinner.classList.remove("d-none");
    });
  }
});

// Customer track_order.html /////////////////////////////////
document.addEventListener("DOMContentLoaded", function () {
    const status = "{{ order.status }}";
    const activeLine = document.querySelector('.progress-line-active');

    if (status === "Pending") activeLine.style.width = "15%";
    else if (status === "Shipped") activeLine.style.width = "50%";
    else if (status === "Delivered") activeLine.style.width = "100%";
    else activeLine.style.width = "0%";
  });

// Admin order save button////////////////////////////
document.addEventListener("DOMContentLoaded", function () {

  // Save Status Button Handler
  document.querySelectorAll('.save-status-btn').forEach(button => { 
    button.addEventListener('click', function () { 
      const orderId = this.dataset.orderId;
      const select = document.querySelector(`select[data-order-id="${orderId}"]`);
      const status = select.value;

      if (status === "Shipped") {
        console.log("Opening modal for order ID:", orderId);
        document.getElementById('modal_order_id').value = orderId;
        const modal = new bootstrap.Modal(document.getElementById('shippingModal'));
        modal.show();
      } else {
        fetch(`/admin/update_order_status/${orderId}`, {
          method: "POST",
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        }).then(res => window.location.reload());
      }
    });
  });

  // Modal Shipping Form Submit
  const shippingForm = document.getElementById('shippingForm'); 
  if (shippingForm) {
    
    shippingForm.addEventListener('submit', function (e) { 
      e.preventDefault();
      const data = Object.fromEntries(new FormData(this));
      data.status = "Shipped"; 

      fetch(`/admin/update_order_status/${data.order_id}`, {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }).then(res => window.location.reload());
    });
  }
});

////////////////Sub category add/remove button ////////////////
function toggleSubForm(id, show = true) {
  document.querySelectorAll('[id^="sub-form-"]').forEach(el => {
    el.classList.add('d-none');
  });

  if (show) {
    const target = document.getElementById(`sub-form-${id}`);
    if (target) target.classList.remove('d-none');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.toggle-sub-form').forEach(btn => {
    btn.addEventListener('click', function () {
      const currentId = this.dataset.id;

      // Hide all subcategory sections
      document.querySelectorAll('[id^="sub-form-"]').forEach(section => {
        if (!section.classList.contains('d-none')) {
          section.classList.add('d-none');
        }
      });

      // Show the clicked one (toggle only if it was hidden)
      const target = document.getElementById(`sub-form-${currentId}`);
      if (target.classList.contains('d-none')) {
        target.classList.remove('d-none');
      }
    });
  });
});

/////////////////////////////////////////////

document.getElementById('category_id').addEventListener('change', function () {
  const categoryId = this.value;
  const subSelect = document.getElementById('sub_category_id');

  if (!categoryId) {
    subSelect.innerHTML = '<option value="">-- Select Subcategory --</option>';
    subSelect.disabled = true;
    subSelect.removeAttribute('required');
    return;
  }

  fetch(`/admin/get_subcategories/${categoryId}`)
    .then(res => res.json())
    .then(data => {
      if (data.subcategories.length > 0) {
        subSelect.innerHTML = '<option value="">-- Select Subcategory --</option>';
        data.subcategories.forEach(sub => {
          const opt = document.createElement('option');
          opt.value = sub.id;
          opt.textContent = sub.name;
          subSelect.appendChild(opt);
        });
        subSelect.disabled = false;
        subSelect.setAttribute('required', 'required');
      } else {
        subSelect.innerHTML = '<option value="">No subcategories</option>';
        subSelect.disabled = true;
        subSelect.removeAttribute('required');
      }
    })
    .catch(err => {
      console.error("Failed to load subcategories", err);
      subSelect.disabled = true;
      subSelect.removeAttribute('required');
    });
});

//////////////////////////////////////////////////////////////


