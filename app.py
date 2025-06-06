from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from xhtml2pdf import pisa
from io import BytesIO
from werkzeug.utils import secure_filename
from datetime import datetime
from zoneinfo import ZoneInfo
from logging.handlers import TimedRotatingFileHandler
from cryptography.fernet import Fernet 
from dotenv import load_dotenv

from models import db, SiteSetting, RazorpayConfig, RazorpayTransaction, Category, SubCategory, Product, Customer, Admin, Order, OrderItem, Address, MailConfig
from utils import send_custom_email, send_email_password_reset, convert_to_webp, send_order_email, send_contact_email, send_order_sms

import razorpay
import os
import re 
import random
import hmac
import hashlib
import logging
import secrets
import threading

app = Flask(__name__)
load_dotenv()  # Load .env file
app.jinja_env.globals['APP_VERSION'] = os.getenv('APP_VERSION', 'v1.0.0')
app.jinja_env.globals['APP_NAME'] = os.getenv('APP_NAME')
app.secret_key = os.getenv("SECRET_KEY")
app.config['FERNET_KEY'] = os.getenv('FERNET_KEY').encode()
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

ist_time = datetime.now(ZoneInfo("Asia/Kolkata"))

@app.context_processor
def inject_categories():
    categories = Category.query.order_by(Category.name).all()
    return dict(categories=categories)

def get_razorpay_client():
    config = RazorpayConfig.query.first()
    if not config:
        raise Exception("Razorpay keys not configured.")

    # Decrypt the stored key_secret
    fernet = Fernet(current_app.config['FERNET_KEY'])  # Ensure this is loaded securely in config
    decrypted_secret = fernet.decrypt(config.key_secret_encrypted).decode()

    return razorpay.Client(auth=(config.key_id, decrypted_secret))
 
# -----------------------
# Routes
# ----------------------- 

@app.route('/')
def home():
    # If admin already logged in, redirect to admin dashboard
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    sub_category_id = request.args.get('sub_category_id', type=int)
    search_query = request.args.get('q', '').strip()

    # Start with all products in stock
    products_query = Product.query.filter(Product.stock > 0)

    # Apply filters
    if sub_category_id:
        products_query = products_query.filter(Product.sub_category_id == sub_category_id)
    elif category_id:
        products_query = products_query.filter(Product.category_id == category_id)

    if search_query:
        products_query = products_query.filter(Product.name.ilike(f"%{search_query}%"))

    # Apply ordering and pagination
    products_query = products_query.order_by(Product.name.asc())
    pagination = products_query.paginate(page=page, per_page=12)
    products = pagination.items

    # Categories for header
    categories = Category.query.all()

    if 'customer_id' in session:
        return render_template('customer/customer.html', products=products, categories=categories, pagination=pagination)
    else:
        return render_template('home.html', products=products, categories=categories, pagination=pagination)

@app.route('/login', methods=['GET', 'POST'])
def login():

     # If customer is already logged in, redirect to home
    if session.get('customer_id'):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        data = request.form
        customer = Customer.query.filter_by(email=data['email']).first()
        if customer and check_password_hash(customer.password, data['password']):
            session['customer_id'] = customer.id
            session['customer_name'] = customer.name

            # ✅ Update last login
            customer.last_login = datetime.now(ZoneInfo("Asia/Kolkata"))
            db.session.commit()
            
            #flash("Login successful", "success")
            return redirect(url_for('home'))
        flash("Invalid credentials", "danger")
        return redirect(url_for('login'))

    # Clear flash only if user did not just come from POST (like from logout or menu)
    if request.referrer and '/login' not in request.referrer:
        session.pop('_flashes', None)

    return render_template('customer/login.html', title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form

        existing_email = Customer.query.filter_by(email=data['email']).first()
        if existing_email:
            flash("Email ID already registered. Please use a different one.", "danger")
            return redirect(url_for('register'))

        existing_phone = Customer.query.filter_by(phone=data['phone']).first()
        if existing_phone:
            flash("Phone number already registered. Please use a different one.", "danger")
            return redirect(url_for('register'))

        customer = Customer(
            name=data['name'],
            email=data['email'],
            phone=data['phone'],
            password=generate_password_hash(data['password'])
        )
        db.session.add(customer)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    if request.referrer and '/register' not in request.referrer:
        session.pop('_flashes', None)

    return render_template('customer/register.html', title="Register")

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        new_password = secrets.token_hex(4)  # Generate once

        # Try customer
        customer = Customer.query.filter_by(email=email).first()
        if customer:
            customer.password = generate_password_hash(new_password)
            try:
                settings = SiteSetting.query.first()
                if settings and settings.email_notify:
                    send_email_password_reset(email, new_password)
                db.session.commit()
                flash('A new password has been sent to your email.', 'success')
            except Exception as e:
                app.logger.error("Customer email error: %s", str(e))
                flash('Failed to send email. Please try again later.', 'danger')
            #return redirect(url_for('forgot_password'))
            return render_template('forgot_password.html', title='Forgot Password', is_admin=False, message='Password sent to your email.', category='success')

        # Try admin
        admin = Admin.query.filter_by(email=email).first()
        if admin:
            admin.password = generate_password_hash(new_password)
            try:
                if settings.email_notify:
                    send_email_password_reset(email, new_password)
                db.session.commit()
                flash('A new password has been sent to your admin email.', 'success')
            except Exception as e:
                app.logger.error("Admin email error: %s", str(e))
                flash('Failed to send email. Please try again later.', 'danger')
            #return redirect(url_for('forgot_password'))
            return render_template('forgot_password.html', title='Forgot Password', is_admin=True, message='Password sent to your email.', category='success')

        # No match
        flash('No account found with that email.', 'danger')
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html', title='Forgot Password')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    customer = None
    orders = []

    # Get logged-in customer and their orders
    if 'customer_id' in session:
        customer = Customer.query.get(session['customer_id'])
        orders = customer.orders if customer else []

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        order_id = request.form.get('order_id', '').strip() or "N/A"
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        # Validate required fields
        if not name or not email or not subject or not message:
            flash("All fields are required.", "danger")
            return redirect(url_for('contact'))

        # ✅ Optional: send email
        try:
            full_message = f"Subject: {subject}\n\nOrder Ref: {order_id}\n\nMessage:\n{message}"
            # Uncomment below if you want to send email
            settings = SiteSetting.query.first()
            if settings and settings.email_notify:
                send_contact_email(name, email, full_message)
            flash("Message submitted successfully!", "success")
        except Exception as e:
            flash("Message sending failed. Try again later.", "danger")

        return redirect(url_for('contact'))

    # ❌ Avoid flash leak from other pages like logout/login
    if request.method == 'GET' and request.referrer and '/contact' not in request.referrer:
        session.pop('_flashes', None)

    if customer:
        return render_template('customer/customer_contact.html', customer=customer, orders=orders, title="Contact Us")
    else:
        return render_template('contact.html', title="Contact Us")

@app.route('/api/categories')
def get_categories():
    cats = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in cats])

@app.route('/api/products')
def get_products():
    prods = Product.query.all()
    return jsonify([
        {
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'image': p.image,
            'stock': p.stock,  
            "shipping_charge": p.shipping_charge,
            "description": p.description
        }
        for p in prods
    ])

@app.route('/logout')
def logout():
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    session.pop('admin', None)
    session.pop('is_admin', None)  # Ensure admin session is cleared
    #flash("Logged out", "info")
    return redirect(url_for('home'))

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    settings = SiteSetting.query.first()
    admin_profile = Admin.query.first() 

    if request.method == 'POST':
        if not settings:
            settings = SiteSetting()
            db.session.add(settings)

        settings.site_title = request.form['site_title']
        settings.tagline = request.form.get('tagline')
        settings.support_phone = request.form['support_phone']
        settings.support_email = request.form['support_email']
        settings.email_notify = bool(request.form.get('email_notify'))
        settings.sms_notify = bool(request.form.get('sms_notify'))
        settings.footer_note = request.form['footer_note']

        # Update admin email if available
        new_email = request.form.get('admin_email')
        if admin_profile and new_email:
            admin_profile.email = new_email

        db.session.commit()
        flash("Settings updated successfully", "success")
        return redirect(url_for('admin_settings'))

    return render_template('admin/admin_settings.html', settings=settings, admin_profile=admin_profile)

@app.context_processor
def inject_settings():
    return {'site_settings': SiteSetting.query.first()}

@app.route('/admin/razorpay', methods=['GET', 'POST'])
def razorpay_settings():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    config = RazorpayConfig.query.first()

    if request.method == 'POST':
        key_id = request.form['key_id'].strip()
        key_secret = request.form['key_secret'].strip()

        if not key_id or not key_secret:
            flash("Both Key ID and Secret are required", "danger")
            return redirect(url_for('razorpay_settings'))

        fernet = Fernet(current_app.config['FERNET_KEY'])
        encrypted_secret = fernet.encrypt(key_secret.encode())

        if config:
            config.key_id = key_id
            config.key_secret_encrypted = encrypted_secret
        else:
            config = RazorpayConfig(key_id=key_id, key_secret_encrypted=encrypted_secret)
            db.session.add(config)

        db.session.commit()
        flash("Razorpay configuration updated", "success")
        return redirect(url_for('razorpay_settings'))

    return render_template('admin/razorpay_settings.html', config=config)

# app.py
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/admin/mail_settings', methods=['GET', 'POST'])
def admin_mail_settings():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    config = MailConfig.query.first()
    #fernet = Fernet(app.config['FERNET_KEY'])

    if request.method == 'POST':
        if not config:
            config = MailConfig()

        config.mail_server = request.form['mail_server']
        config.mail_port = int(request.form['mail_port'])
        config.mail_use_tls = 'mail_use_tls' in request.form
        config.mail_username = request.form['mail_username']

        new_password = request.form['mail_password']
        if new_password:
            config.set_password(new_password, app.config['FERNET_KEY'])

        db.session.add(config)
        db.session.commit()
        flash("Mail settings updated successfully.", "success")
        return redirect(url_for('admin_mail_settings'))

    return render_template('admin/mail_settings.html', config=config)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    
    # If admin already logged in, redirect to admin dashboard
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin'] = True
            session["is_admin"] = True
            #flash("Logged in successfully", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")

    if request.referrer and '/admin' not in request.referrer:
        session.pop('_flashes', None)

    return render_template("admin/admin_login.html")


@app.route('/admin/change-password', methods=['GET', 'POST'])
def change_admin_password():
    if not session.get('is_admin'):
        flash("Admin login required", "danger")
        return redirect(url_for('admin_login'))

    admin = Admin.query.filter_by(username='admin').first()

     # Clear flash only if user did not just come from POST (like from logout or menu)
    if request.referrer and '/admin/change-password' not in request.referrer:
        session.pop('_flashes', None)

    if request.method == 'POST':
        current = request.form['current_password']
        new_pass = request.form['new_password']
        confirm = request.form['confirm_password']

        # Password validation regex
        regex = r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|]).{8,}$'

        if not admin.check_password(current):
            flash("Current password is incorrect", "danger")
        elif new_pass != confirm:
            flash("New passwords do not match", "warning")
        elif not re.match(regex, new_pass):
            flash("New password must be at least 8 characters and include an uppercase letter, number, and special character.", "warning")
        else:
            admin.set_password(new_pass)
            db.session.commit()
            flash("Password updated successfully", "success")
        return redirect(url_for('change_admin_password'))

    return render_template('admin/admin_change_password.html')


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    return render_template("admin/admin.html", title="Admin Dashboard")
    
@app.route('/admin/users')
def admin_users():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    page = request.args.get('page', 1, type=int)
    pagination = Customer.query.order_by(Customer.created_at.desc()).paginate(page=page, per_page=10)
    #users = pagination.items

    users = Customer.query.all()
    return render_template('admin/admin_users.html', users=users, pagination=pagination)

@app.route('/admin/categories')
def admin_categories():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/admin_categories.html', categories=categories)

@app.route('/admin/add_category', methods=['POST'])
def add_category():
    name = request.form['category_name'].strip()
    if name:
        existing = Category.query.filter_by(name=name).first()
        if not existing:
            db.session.add(Category(name=name))
            db.session.commit()
            flash('Category added!', 'success')
        else:
            flash('Category already exists.', 'warning')
    else:
        flash('Invalid category name.', 'danger')
    return redirect(url_for('admin_categories'))

@app.route('/admin/delete_category/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
     
    if not session.get('is_admin'):
       return redirect(url_for('admin_login'))
    
    category = Category.query.get_or_404(cat_id)
     
    # Check if this category has subcategories
    if category.subcategories:
        flash("Cannot delete. Please delete all sub-categories under this category first.\n" \
        "Assign these products to different sub-category to proceed delete", "danger")
        return redirect(url_for('admin_categories'))

    # Check if any product directly using this category (with no subcategory)
    products = Product.query.filter_by(category_id=cat_id, sub_category_id=None).all()
    if products:
        product_names = [p.name for p in products]
        flash(f"Cannot delete. Products assigned to this category:[ {', '.join(product_names)} ] \n" \
        "Assign these products to different category to proceed delete", "danger")
        return redirect(url_for('admin_categories'))
     
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted.', 'info')
    return redirect(url_for('admin_categories'))

@app.route('/admin/add_subcategory', methods=['POST'])
def add_subcategory():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    name = request.form['subcategory_name']
    category_id = request.form['category_id']
    db.session.add(SubCategory(name=name, category_id=category_id))
    db.session.commit()
    flash("Sub-category added", "success")
    return redirect(url_for('admin_categories'))

@app.route('/admin/delete_subcategory/<int:id>', methods=['POST'])
def delete_subcategory(id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    sub = SubCategory.query.get_or_404(id)

     # Check if products are using this subcategory
    associated_products = Product.query.filter_by(sub_category_id=sub.id).all()

    if associated_products:
       product_names = [p.name for p in associated_products]
       flash(f"Cannot delete. Products assigned to this sub-category: [{', '.join(product_names)}]."
             "Change sub-category for these products to proceed delete", "danger")
       return redirect(url_for('admin_categories'))

    db.session.delete(sub)
    db.session.commit()
    flash("Sub-category deleted", "success")
    return redirect(url_for('admin_categories'))


@app.route('/admin/products')
def admin_products():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('q', '').strip()
    stock_filter = request.args.get('stock')

    products_query = Product.query

    if category_id:
        products_query = products_query.filter(Product.category_id == category_id)

    if stock_filter == 'zero':
        products_query = products_query.filter(Product.stock == 0)
    elif stock_filter == 'lt5':
        products_query = products_query.filter(Product.stock < 5)
    elif stock_filter == 'lt10':
        products_query = products_query.filter(Product.stock < 10)    

    if search_query:
        products_query = products_query.filter(Product.name.ilike(f"%{search_query}%"))

    
    products_query = products_query.order_by(Product.id.desc())
    pagination = products_query.paginate(page=page, per_page=10)
    products = pagination.items
    categories = Category.query.order_by(Category.name).all() 
 
    return render_template('admin/admin_products.html', products=products,
                           pagination=pagination, categories=categories, selected_category=category_id,
                           search_query=search_query, selected_stock=stock_filter)
    
@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    category_id = int(request.form['category_id'])
    subcategory_val = request.form.get('sub_category_id')
    sub_category_id = int(subcategory_val) if subcategory_val else None  
    description = request.form['description']
    shipping_charge = float(request.form['shipping_charge'])
    image_file = request.files.get('image')

    if not image_file or image_file.filename == '':
        flash("Image is required", "danger")
        return redirect(url_for('admin_products'))

    # Prepare WebP filename
    original_name = secure_filename(image_file.filename.rsplit('.', 1)[0])
    webp_filename = f"{original_name}.webp"
    #image_path = os.path.join(app.root_path, 'static/images', webp_filename)

    webp_filename = convert_to_webp(image_file, app.root_path, app.logger)
    
    if not webp_filename:
        flash("Image conversion failed. Please try another image.", "danger")
        return redirect(url_for('admin_products'))

    # Save product to DB
    product = Product(
        name=name,
        price=price,
        stock=stock,
        category_id=category_id,
        sub_category_id=sub_category_id,
        image=webp_filename,
        description=description,
        shipping_charge=shipping_charge
    )

    db.session.add(product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/get_subcategories/<int:category_id>')
def get_subcategories(category_id):
    subs = SubCategory.query.filter_by(category_id=category_id).all()
    sub_data = [{'id': s.id, 'name': s.name} for s in subs]
    return jsonify({'subcategories': sub_data})


@app.route('/admin/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(id)

    # Delete the image file if it exists
    if product.image:
        image_path = os.path.join(current_app.root_path, 'static/images', product.image)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                flash(f"Image could not be deleted: {e}", "warning")

    db.session.delete(product)
    db.session.commit()
    #flash('Product deleted.', 'info')
    return redirect(url_for('admin_products'))

@app.route('/admin/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    product = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])
        product.category_id = int(request.form['category_id'])
        subcategory_val = request.form.get('sub_category_id')
        product.sub_category_id = int(subcategory_val) if subcategory_val else None
        product.description = request.form['description']
        product.shipping_charge = float(request.form['shipping_charge'])


        image_file = request.files['image']
        
        if image_file and image_file.filename != "":

            # Delete old image from disk if exists
            if product.image:
                old_path = os.path.join(app.root_path, 'static/images', product.image)
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Convert and save new image
            webp_filename = convert_to_webp(image_file, app.root_path, app.logger)
            if not webp_filename:
                flash("Image conversion failed. Please try another image.", "danger")
                return redirect(url_for('admin_products'))
            product.image = webp_filename

        db.session.commit()

        flash("Product updated successfully", "success")
        return redirect(url_for('admin_products'))

    return render_template('admin/admin_products.html', product=product, categories=categories)

@app.route('/admin/orders')
def admin_orders():
    if not session.get("is_admin"):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    search_query = request.args.get('q', '').strip()

    query = Order.query.order_by(Order.id.desc())

    if status_filter:
        query = query.filter(Order.status == status_filter)

    if search_query:
        query = query.filter(Order.order_id.ilike(f"%{search_query}%"))    
 
    pagination = query.paginate(page=page, per_page=8)
    orders = pagination.items
    
    return render_template('order/admin_orders.html', orders=orders, pagination=pagination)

@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
def admin_update_order_status(order_id):
    if not session.get("is_admin"):
        return redirect(url_for('admin_login'))

    order = Order.query.get_or_404(order_id)
  
    try:
        data = request.get_json()  # Expecting JSON from JS
        status = data.get("status")
        order.status = status 

        if status == "Shipped":
            order.courier_service = data.get("courier_service")
            order.tracking_number = data.get("tracking_number") 
            delivery_str = data.get("estimated_delivery")
            order.estimated_delivery = datetime.strptime(delivery_str, "%Y-%m-%d").date()
            order.shipment_date = datetime.utcnow().date()

        elif status == "Delivered": 
            order.delivered_date = datetime.utcnow().date()    

        db.session.commit()

          # ✅ Send email if enabled
        settings = SiteSetting.query.first()
        if settings and settings.email_notify:
            customer = Customer.query.get(order.customer_id)
            if customer:
                subject = f"Your Order {order.order_id} is now {status}"
                body = f"Hi {customer.name},\n\nYour order status has been updated to **{status}**."

                # Add shipment details if status is Shipped
                if status == "Shipped":
                    body += (
                    f"\n\nShipment Info:\n"
                    f"Courier: {order.courier_service or '—'}\n"
                    f"Tracking #: {order.tracking_number or '—'}\n"
                    f"ETA: {order.estimated_delivery.strftime('%d %b %Y') if order.estimated_delivery else '—'}"
                    )

                body += "\n\nThank you for shopping with us!"
                send_custom_email(customer.email, subject, body)

        return jsonify({'success': True})
    except Exception as e:
        print("Order update failed:", e)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    flash("Order status updated", "success")
    return redirect(url_for('admin_orders'))


@app.route('/admin/order/<int:order_id>')
def admin_order_detail(order_id):
    if not session.get("is_admin"):
        return redirect(url_for('admin_login'))
    
    order = Order.query.get_or_404(order_id)
    return render_template("admin/admin_order_detail.html", order=order)

@app.route('/admin/customer/<int:customer_id>')
def admin_customer_profile(customer_id):
    if not session.get("is_admin"):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(customer_id=customer_id).order_by(Order.created_at.desc()).paginate(page=page, per_page=6)
    
    customer = Customer.query.get_or_404(customer_id)

    return render_template('admin/admin_customer_profile.html', 
                           customer=customer, orders=pagination.items, pagination=pagination)

@app.route("/admin/customer/delete/<int:user_id>", methods=["POST"])
def delete_customer(user_id):
    customer = Customer.query.get_or_404(user_id)

    db.session.delete(customer)
    db.session.commit()
    flash("Customer deleted successfully.", "success")
    return redirect("/admin/customers")


@app.route('/cart')
def cart():
    return render_template('order/cart.html', title='Your Cart')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'customer_id' not in session:
        return redirect(url_for('login'))

    customer = Customer.query.get(session['customer_id'])

    if request.method == 'POST':
        phone = request.form['phone']
        customer.phone = phone
        db.session.commit()
        flash("Phone number updated successfully", "success")
        return redirect(url_for('profile'))

    return render_template('customer/customer_profile.html', customer=customer)

#Customer portal - Change password
@app.route('/change-password', methods=['GET', 'POST'])
def customer_change_password():
    if 'customer_id' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    customer = Customer.query.get(session['customer_id'])

    if request.method == 'POST':
        current = request.form['current_password']
        new_pass = request.form['new_password']
        confirm = request.form['confirm_password']

        if not check_password_hash(customer.password, current):
            flash("Current password is incorrect", "danger")
        elif new_pass != confirm:
            flash("New passwords do not match", "warning")
        elif not validate_password_strength(new_pass):
            flash("Password must be 8+ chars with 1 uppercase, 1 number, 1 special character.", "warning")
        else:
            customer.password = generate_password_hash(new_pass)
            db.session.commit()
            flash("Password changed successfully", "success")
            return render_template('customer/change_password.html')  

    return render_template('customer/change_password.html')


def validate_password_strength(password):
    return (
        len(password) >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[0-9]', password) and
        re.search(r'[!@#$%^&*()_+{}\[\]:;"\'<>,.?\\/~`|=-]', password)
    )

@app.route("/addresses", methods=["GET", "POST"])
def addresses():
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    edit_id = request.args.get('edit_id', type=int)
    show_form = request.args.get('show_form', '0') == '1'  # Read as boolean

    edit_address = None

    if request.method == 'POST':
        form_type = request.form.get("form_type")

        # Form fields
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        line1 = request.form.get('line1', '').strip()
        line2 = request.form.get('line2', '').strip()
        landmark = request.form.get('landmark', '').strip()
        pincode = request.form.get('pincode', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()

        if form_type == "add":
            # Add new address
            new_address = Address(
                customer_id=customer_id,
                name=name,
                phone=phone,
                line1=line1,
                line2=line2,
                landmark=landmark,
                pincode=pincode,
                city=city,
                state=state
            )
            db.session.add(new_address)
            db.session.commit()
            flash("Address added successfully", "success")
            return redirect('/addresses')

        elif form_type == "edit":
            address_id = request.form.get('address_id', type=int)
            address = Address.query.filter_by(id=address_id, customer_id=customer_id).first()
            if address:
                address.name = name
                address.phone = phone
                address.line1 = line1
                address.line2 = line2
                address.landmark = landmark
                address.pincode = pincode
                address.city = city
                address.state = state
                db.session.commit()
                flash("Address updated successfully", "success")
            else:
                flash("Address not found or unauthorized access", "danger")
            return redirect('/addresses')

    address_list = Address.query.filter_by(customer_id=customer_id).all()
    if edit_id:
        edit_address = Address.query.filter_by(id=edit_id, customer_id=customer_id).first()

    return render_template("customer/addresses.html",
                           addresses=address_list,
                           edit_address=edit_address,
                           show_form=show_form)

@app.route("/delete_address/<int:id>", methods=["POST"])
def delete_address(id):
    if 'customer_id' not in session:
        return redirect('/login')

    address = Address.query.filter_by(id=id, customer_id=session['customer_id']).first()
    if address:
        db.session.delete(address)
        db.session.commit()
        flash("Address deleted successfully", "success")

    return redirect('/addresses')

@app.route('/checkout')
def checkout():
    if 'customer_id' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))

    customer_id = session['customer_id']
    addresses = Address.query.filter_by(customer_id=customer_id).all()

     # ✅ Get key from database
    config = RazorpayConfig.query.first()
    if not config:
        flash("Razorpay is not configured yet.", "danger")
        return redirect(url_for('home'))

    return render_template('order/checkout.html', 
                           addresses=addresses, 
                           customer_id=customer_id,
                           razorpay_key=config.key_id)

def generate_order_id():
    return "ORD-" + str(random.randint(100000, 999999))

def generate_invoice_number():
    prefix = "INVBS"
    suffix = random.randint(100000, 999999)
    return f"{prefix}-{suffix}"

def send_notifications(email, phone, order_id):
    try:
        settings = SiteSetting.query.first()
        if settings and settings.email_notify:
            send_order_email(email, order_id)
        #send_order_sms(phone, order_id)
    except Exception as e:
        app.logger.error(f"Email Notification failed: ", e)

@app.route('/checkout/confirm', methods=['POST'])
def confirm_checkout():
    if 'customer_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401

    data = request.get_json()
    app.logger.info("Confirm Checkout Payload:", data)

    try:
        order_id = data['razorpay_order_id']
        payment_id = data['razorpay_payment_id']
        signature = data['razorpay_signature']
        address_id = data['address_id']
        cart = data['cart']
    except KeyError as e:
        return jsonify({'success': False, 'message': f'Missing key: {e}'}), 400

    # ✅ Get Razorpay key/secret from DB
    config = RazorpayConfig.query.first()
    if not config:
        return jsonify({'success': False, 'message': 'Razorpay config not found'}), 500
    
    fernet = Fernet(current_app.config['FERNET_KEY'])
    decrypted_key_secret = fernet.decrypt(config.key_secret_encrypted).decode()

    # ✅ Verify Razorpay signature
    key_secret = decrypted_key_secret.encode()
    msg = f"{order_id}|{payment_id}".encode()
    expected_signature = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()

    if expected_signature != signature:
        return jsonify({'success': False, 'message': 'Payment signature mismatch'}), 400

    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    subtotal = 0
    shipping_total = 0
    total_amount = 0
    order_items = []

    for item in cart:
        product = Product.query.get(item['id'])
        if not product:
            return jsonify({'success': False, 'message': f"Product {item['id']} not found"}), 400
        if product.stock < item['qty']:
            return jsonify({'success': False, 'message': f"Insufficient stock for {product.name}"}), 400

        qty = item["qty"]
        subtotal += product.price * qty
        shipping_total += product.shipping_charge * qty
        total_amount = subtotal + shipping_total
        order_items.append((product, qty))

    address = Address.query.filter_by(id=address_id, customer_id=session['customer_id']).first()
    if not address:
        return jsonify({'success': False, 'message': 'Invalid address'}), 400

    order_id_str = generate_order_id()
    invoice_number = generate_invoice_number()

    try:
        # ✅ Create order
        order = Order(
            order_id=order_id_str,
            invoice_number=invoice_number,
            customer_id=session['customer_id'],
            address=f"{address.name}, {address.line1}, {address.city}, {address.state} - {address.pincode}",
            shipping_total=shipping_total,
            total_amount=total_amount
        )
        db.session.add(order)
        db.session.flush()

        # ✅ Create order items
        for product, qty in order_items:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                price=product.price
            ))
            product.stock -= qty

        # ✅ Fetch payment details from Razorpay
        razorpay_client = razorpay.Client(auth=(config.key_id, decrypted_key_secret))
        payment_info = razorpay_client.payment.fetch(payment_id)

        payment_method = payment_info.get("method")
        payment_status = payment_info.get("status")

        # ✅ Save Razorpay transaction
        txn = RazorpayTransaction(
            order_id=order.id,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
            status=payment_status,
            payment_method=payment_method
        )
        db.session.add(txn)
        db.session.commit()

        # Send email and sms ----------------------------------------
        customer = Customer.query.get(session['customer_id'])

        threading.Thread(
            target=send_notifications,
            args=(customer.email, customer.phone, order.order_id)
        ).start()        
        # --------------------------------------------------------------    

        return jsonify({'success': True, 'order_id': order.order_id})
    except Exception as e:
        db.session.rollback()
        print("DB Commit Error:", e)
        return jsonify({'success': False, 'message': 'Order failed to save in DB'}), 500

# Add route to generate Razorpay order ID before payment
@app.route('/create_razorpay_order', methods=['POST'])
def create_razorpay_order():
    if 'customer_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401

    data = request.get_json()
    cart = data.get('cart', [])

    subtotal = 0
    shipping_total = 0

    amount = 0
    for item in cart:
        product = Product.query.get(item['id'])
        if not product or product.stock < item['qty']:
            return jsonify({'success': False, 'message': f"Stock unavailable for {item['id']}"})
        qty = item["qty"]
        subtotal += product.price * qty
        shipping_total += product.shipping_charge * qty  

    total_amount = subtotal + shipping_total 

    # Convert to paise
    total_in_paise = int(total_amount * 100)

   # razorpay_order = razorpay_client.order.create({
    razorpay_order = get_razorpay_client().order.create({
        'amount': total_in_paise,
        'currency': 'INR',
        'payment_capture': 1
    })

    return jsonify({
        'success': True,
        'razorpay_order_id': razorpay_order['id'],
        'amount': total_in_paise 
    })


@app.route('/order-success')
def order_success():
    order_id = request.args.get("order_id")
    return render_template("order/order_success.html", order_id=order_id)

@app.route('/orders')
def customer_orders():
    if 'customer_id' not in session:
        flash("Login required", "danger")
        return redirect(url_for('login'))
    
    customer_id = session['customer_id']
    page = request.args.get('page', 1, type=int)
    per_page = 6
    search_query = request.args.get('q', '').strip()

    query = Order.query.filter_by(customer_id=customer_id)

    if search_query:
        query = query.join(OrderItem).join(Product).filter(Product.name.ilike(f"%{search_query}%"))


    orders = query.order_by(Order.created_at.desc())\
                  .paginate(page=page, per_page=per_page)
   
    return render_template('order/customer_orders.html', orders=orders, search_query=search_query)

@app.route('/track_order/<order_id>')
def track_order(order_id):
    order = Order.query.filter_by(order_id=order_id, customer_id=session.get('customer_id')).first_or_404()
    return render_template('order/track_order.html', order=order)

@app.route('/invoice/<int:order_id>')
def generate_invoice(order_id):
    order = Order.query.get_or_404(order_id)
    html = render_template("order/invoice_template.html", order=order)

    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)

    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Invoice_{order.order_id}.pdf'
    return response

def logger():
    # Create /log directory if not exists
    log_dir = os.path.join(os.path.dirname(__file__), 'log')
    os.makedirs(log_dir, exist_ok=True)

    # === Error Logger (error.log) ===
    error_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'error.log'), when='midnight', interval=1, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))

    # === Info Logger (app.log) ===
    info_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'app.log'), when='midnight', interval=1, backupCount=5
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))

    # === Attach both to app.logger ===
    app.logger.setLevel(logging.DEBUG)  # So it accepts all levels
    app.logger.addHandler(error_handler)
    app.logger.addHandler(info_handler)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

# Check if default admin exists, if not create one
        if not Admin.query.filter_by(username="admin").first():
            admin = Admin(username="admin")
            admin.set_password("admin")  # default password
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created (username: admin, password: admin)")

        #### Logging ///////////////////////////
        logger()
        #///////////////////////////////////////
        # Make MailConfig importable from outside
        __all__ = ['MailConfig']

        app.logger.info("BuySell Application")

    app.run(debug=True)

