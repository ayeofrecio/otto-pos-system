# Django Training Guide for Clarion/Clipper Programmers
### Fast-Track Learning Path — Python You Know, Django You Will

---

## How to Use This Guide

This guide is written **specifically for you** — someone who already thinks like a programmer (Clarion/Clipper), knows Python, understands basic HTML, but has never built a web app. Every concept is explained by **comparing it to what you already know in Clarion/Clipper.**

Work through each section in order. Each section ends with a **"Do This Now"** exercise tied directly to your POS project.

---

## The Mental Model Shift: Clarion → Django

Before touching any code, understand this fundamental shift:

| Concept | Clarion/Clipper | Django |
|---|---|---|
| **Data file** | `.DAT` / `.DBF` file | Database table (MySQL) |
| **Dictionary** | App Dictionary (.DCT) | `models.py` |
| **Field definition** | `FIELD` in DCT | Class attribute in Model |
| **Browse** | BROWSE control | ListView / QuerySet |
| **Form** | FORM procedure | Django Form / Template |
| **Report** | REPORT procedure | View + Template or PDF |
| **Global variables** | MODULE-level variables | Django Session / Settings |
| **Procedure** | PROCEDURE | View (function or class) |
| **Menu** | MENU structure | URL routing (`urls.py`) |
| **INI/Config file** | `.INI` file | `settings.py` |
| **APP startup** | `CODE` section of APP | `manage.py runserver` |
| **Screen layout** | Window Designer | HTML Template |

> **Key insight:** In Clarion, you define a window and embed data. In Django, you define data (models) and then build pages (templates) that display it. The flow is: **URL → View → Model → Template → Browser.**

---

## SECTION 1 — Django Project Structure
### (Your New "Application Dictionary")

### What Gets Created When You Start a Project

```bash
django-admin startproject pos_project
cd pos_project
python manage.py startapp sales
```

This creates:

```
pos_project/              ← Your project root (like your APP file)
├── manage.py             ← The command-line tool (like running your APP)
├── pos_project/
│   ├── settings.py       ← Global config (like your INI file + APP properties)
│   ├── urls.py           ← Master menu/routing (like your APP menu structure)
│   └── wsgi.py           ← Web server entry point (ignore for now)
└── sales/                ← A Django "app" (like a module in Clarion)
    ├── models.py         ← Your data dictionary (DCT equivalent)
    ├── views.py          ← Your procedures/forms
    ├── urls.py           ← Module-level routing
    ├── admin.py          ← Back office auto-UI
    └── templates/        ← Your screen layouts (HTML)
```

### The Key Concept: Django "Apps" vs Your Project

In Clarion, everything is in one APP file. In Django, you break features into **apps** (sub-modules). Think of each app as a separate Clarion module (.CLW file).

For your POS, you'll have:

```
pos_project/
├── users/      ← Login, roles, sessions (like your security module)
├── inventory/  ← Products, variants (reads from central DB)
├── sales/      ← Transactions, cart, receipts
├── reports/    ← X/Z readings, daily reports
└── settings_app/ ← Store config, printer, FTP
```

### Do This Now
```bash
django-admin startproject pos_project .
python manage.py startapp users
python manage.py startapp sales
python manage.py startapp inventory
python manage.py startapp reports
```

---

## SECTION 2 — Models (Your Data Dictionary)
### (This is Your `.DCT` File — But In Python)

In Clarion, you open the Dictionary editor and define files and fields visually. In Django, you write Python classes. Django then **generates the SQL and creates the tables for you.**

### Clarion Dictionary → Django Model

**In Clarion:**
```
FILE,DRIVER('TOPSPEED'),PRE(PRD)
RECORD
  ProductID   LONG
  ProductName STRING(50)
  Price       DECIMAL(10,2)
  IsActive    BYTE
END
```

**In Django (`inventory/models.py`):**
```python
from django.db import models

class Product(models.Model):
    product_name = models.CharField(max_length=50)   # STRING(50)
    price        = models.DecimalField(max_digits=10, decimal_places=2)  # DECIMAL(10,2)
    is_active    = models.BooleanField(default=True)  # BYTE (0/1)

    class Meta:
        db_table = 'product'   # actual MySQL table name

    def __str__(self):
        return self.product_name   # what shows in Django admin lists
```

### Field Type Cheat Sheet

| Clarion Type | Django Field |
|---|---|
| `STRING(n)` | `CharField(max_length=n)` |
| `LONG` | `IntegerField()` |
| `DECIMAL(x,y)` | `DecimalField(max_digits=x, decimal_places=y)` |
| `BYTE` (0/1) | `BooleanField()` |
| `DATE` | `DateField()` |
| `TIME` | `TimeField()` |
| `MEMO` | `TextField()` |
| Auto-increment key | `AutoField()` — Django adds this automatically as `id` |

### Linking Tables (Relationships)

In Clarion, you link files in a browse using KEY fields. In Django, you define relationships directly in the model.

**One-to-Many (like Clarion FILE link):**
```python
# A sale has many line items
class SalesTransaction(models.Model):
    cashier      = models.ForeignKey('users.User', on_delete=models.PROTECT)
    business_date = models.DateField()
    total        = models.DecimalField(max_digits=10, decimal_places=2)

class SalesTransactionLine(models.Model):
    transaction = models.ForeignKey(SalesTransaction, on_delete=models.CASCADE)
    # CASCADE = if transaction deleted, lines deleted too (like Clarion RECLAIM)
    variant     = models.ForeignKey('inventory.ProductVariant', on_delete=models.PROTECT)
    qty         = models.IntegerField()
    unit_price  = models.DecimalField(max_digits=10, decimal_places=2)
```

### The Critical Shoe Variant Model

This is the most important model in your POS. Think of it as:
- `Product` = the shoe style (e.g., "Nike Air Max")
- `ProductVariant` = specific buyable item (Nike Air Max, Size 9, Black)

```python
# inventory/models.py

class Color(models.Model):
    name = models.CharField(max_length=30)   # "Black", "White", "Red"

    def __str__(self):
        return self.name

class Size(models.Model):
    name = models.CharField(max_length=10)   # "7", "8", "9", "10", "11"

    def __str__(self):
        return self.name

class Product(models.Model):
    central_id   = models.IntegerField(unique=True)  # ID from central system
    sku          = models.CharField(max_length=50, unique=True)
    product_name = models.CharField(max_length=100)
    base_price   = models.DecimalField(max_digits=10, decimal_places=2)
    is_active    = models.BooleanField(default=True)
    last_synced  = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.sku} - {self.product_name}"

class ProductVariant(models.Model):
    product     = models.ForeignKey(Product, on_delete=models.CASCADE)
    color       = models.ForeignKey(Color, on_delete=models.PROTECT)
    size        = models.ForeignKey(Size, on_delete=models.PROTECT)
    barcode     = models.CharField(max_length=50, unique=True, null=True, blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    stock_qty   = models.IntegerField(default=0)
    is_active   = models.BooleanField(default=True)

    class Meta:
        unique_together = ('product', 'color', 'size')  # No duplicate combos
        # Like a compound KEY in Clarion

    def __str__(self):
        return f"{self.product.sku} | {self.color} | Size {self.size}"
```

### Creating the Tables (Running Migrations)

In Clarion, you press "Convert Files" to create/update tables. In Django:

```bash
# Step 1: Generate the migration file (like generating SQL DDL)
python manage.py makemigrations

# Step 2: Apply it to MySQL (actually creates/alters the tables)
python manage.py migrate
```

**Do this every time you change a model.** Think of `makemigrations` as writing the conversion script, and `migrate` as running it.

### Do This Now
Create all your core models in their respective `models.py` files, run migrations, then verify in MySQL Workbench that the tables were created correctly.

---

## SECTION 3 — Django Admin (Free Back Office — Use It Early)
### (Your Instant Browse/Form for Any Table)

Django gives you a free admin interface that works like a Clarion browse+form combo — for free, automatically. **Use this heavily during development** to enter test data without writing any views yet.

```python
# inventory/admin.py
from django.contrib import admin
from .models import Product, ProductVariant, Color, Size

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ('sku', 'product_name', 'base_price', 'is_active')  # Browse columns
    search_fields = ('sku', 'product_name')                              # Search bar
    list_filter   = ('is_active',)                                       # Filter panel

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display  = ('product', 'color', 'size', 'barcode', 'price', 'stock_qty')
    search_fields = ('barcode', 'product__sku')
    list_filter   = ('color', 'size', 'is_active')

admin.site.register(Color)
admin.site.register(Size)
```

```bash
# Create your admin login
python manage.py createsuperuser

# Start the server and go to: http://127.0.0.1:8000/admin
python manage.py runserver
```

> **Pro tip:** For the first week of your project, do ALL your data testing through Django admin. Don't write views yet — just get your models right first.

---

## SECTION 4 — URLs and Views
### (Your Menu Structure and Procedures)

### How Routing Works

In Clarion, a MENU item calls a PROCEDURE. In Django, a URL pattern calls a VIEW function.

```
User types URL → urls.py matches it → calls a view function → view returns HTML page
```

**Clarion:**
```clarion
MENU('Sales')
  ITEM('New Sale'),USE(?NewSale),DO NewSaleProc
  ITEM('View Transactions'),USE(?ViewTrans),DO TransactionList
END
```

**Django (`sales/urls.py`):**
```python
from django.urls import path
from . import views

urlpatterns = [
    path('sale/new/',          views.new_sale,         name='new_sale'),
    path('sale/list/',         views.transaction_list,  name='transaction_list'),
    path('sale/<int:id>/',     views.transaction_detail, name='transaction_detail'),
]
```

The `<int:id>` part captures a number from the URL — like passing a parameter to a Clarion procedure.

**Master URL file (`pos_project/urls.py`):**
```python
from django.urls import path, include

urlpatterns = [
    path('admin/',     admin.site.urls),
    path('sales/',     include('sales.urls')),      # All sales URLs under /sales/
    path('inventory/', include('inventory.urls')),
    path('users/',     include('users.urls')),
    path('reports/',   include('reports.urls')),
]
```

### Writing Views

A **view** is just a Python function that receives a request and returns a page. Think of it as your Clarion PROCEDURE.

**Simple view (like a Clarion browse procedure):**
```python
# sales/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import SalesTransaction

@login_required   # Like checking IF ~User.IsLoggedIn before proceeding
def transaction_list(request):
    # This is like doing a SET + NEXT loop in Clarion
    transactions = SalesTransaction.objects.filter(
        session__cashier=request.user
    ).order_by('-created_at')[:50]   # Last 50 transactions

    # Pass data to the template (like populating a Clarion QUEUE)
    return render(request, 'sales/transaction_list.html', {
        'transactions': transactions
    })
```

**View that handles both display AND save (like a Clarion FORM procedure):**
```python
from django.shortcuts import render, redirect
from .forms import PaymentForm
from .models import SalesTransaction

@login_required
def process_payment(request, transaction_id):
    transaction = get_object_or_404(SalesTransaction, id=transaction_id)

    if request.method == 'POST':          # Form was submitted (like Accepted() in Clarion)
        form = PaymentForm(request.POST)
        if form.is_valid():               # Like validation checks passing
            transaction.amount_tendered = form.cleaned_data['amount_tendered']
            transaction.change = transaction.amount_tendered - transaction.total
            transaction.status = 'COMPLETED'
            transaction.save()            # Like POST to the file in Clarion
            return redirect('receipt', transaction_id=transaction.id)
    else:
        form = PaymentForm()              # First time opening the form

    return render(request, 'sales/payment.html', {
        'transaction': transaction,
        'form': form
    })
```

---

## SECTION 5 — QuerySets (Your SET/NEXT/PREV Replacement)
### (How Django Reads Data — The Clarion Loop Equivalent)

In Clarion, you navigate files with `SET`, `NEXT`, `PREV`, and loops. In Django, you use **QuerySets** — which are like smart, lazy file selectors.

### Clarion File Access → Django QuerySet

**Clarion (loop through all products):**
```clarion
SET(PRD:ByName)
LOOP
  NEXT(Products)
  IF ERRORCODE() THEN BREAK.
  ! process each record
END
```

**Django equivalent:**
```python
products = Product.objects.all()   # Gets all products (like SET with no filter)
for product in products:
    print(product.product_name)
```

**Clarion (find one record by key):**
```clarion
PRD:ProductID = 42
GET(Products, PRD:ProductID)
IF ~ERRORCODE() THEN ! record found
```

**Django equivalent:**
```python
product = Product.objects.get(id=42)          # Raises error if not found
product = Product.objects.filter(id=42).first() # Returns None if not found
```

**Clarion (filtered browse with range):**
```clarion
SET(PRD:ByActive, PRD:ByActive)
! only processes active records
```

**Django equivalent:**
```python
# Filter (WHERE clause)
active_products = Product.objects.filter(is_active=True)

# Multiple filters (AND)
results = Product.objects.filter(is_active=True, color__name='Black')

# OR filter
from django.db.models import Q
results = Product.objects.filter(Q(sku='NK001') | Q(barcode='12345'))

# Sorting (like ORDER BY)
products = Product.objects.order_by('product_name')          # ASC
products = Product.objects.order_by('-product_name')         # DESC (note the minus)

# Limit (like TOP n)
products = Product.objects.all()[:10]   # First 10 only
```

### Lookups You'll Use Every Day

```python
# Exact match
Product.objects.filter(sku='NK001')

# Contains (like INSTRING in Clarion)
Product.objects.filter(product_name__icontains='nike')   # case-insensitive

# Starts with
Product.objects.filter(sku__startswith='NK')

# Range (like BETWEEN)
SalesTransaction.objects.filter(business_date__range=['2025-01-01', '2025-01-31'])

# Related table lookup (like a linked file in Clarion browse)
# Get all variants of a specific product
ProductVariant.objects.filter(product__sku='NK001')
# Note the double underscore __ to traverse relationships
```

### Aggregates (Totals — Like Clarion REPORT totals)

```python
from django.db.models import Sum, Count, Avg

# Total sales for the day
daily_total = SalesTransaction.objects.filter(
    business_date='2025-01-15',
    status='COMPLETED'
).aggregate(total=Sum('total'))

print(daily_total['total'])   # e.g., 15250.00

# Count of transactions
count = SalesTransaction.objects.filter(business_date='2025-01-15').count()

# Sales per product
from django.db.models import Sum
top_products = SalesTransactionLine.objects.values(
    'variant__product__product_name'
).annotate(
    total_sold=Sum('qty')
).order_by('-total_sold')[:10]
```

---

## SECTION 6 — Templates (Your Window/Screen Designer)
### (HTML with Django Tags = Clarion Window + Controls)

Templates are HTML files with special Django tags that insert data. Your basic HTML knowledge is enough — you just need to learn the Django template tags.

### The Template Folder Structure

```
sales/
└── templates/
    └── sales/
        ├── base.html              ← Master layout (like Clarion MDI window)
        ├── transaction_list.html  ← Browse screen
        └── payment.html           ← Form screen
```

### Base Template (Your Master Window)

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>POS System - {% block title %}{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/pos.css">
</head>
<body>
    <nav>
        <span>Cashier: {{ request.user.username }}</span>
        <a href="{% url 'new_sale' %}">New Sale</a>
        <a href="{% url 'transaction_list' %}">Transactions</a>
    </nav>

    <main>
        {% block content %}
        <!-- Child templates fill this in -->
        {% endblock %}
    </main>
</body>
</html>
```

### List Template (Your Browse Screen)

```html
<!-- sales/templates/sales/transaction_list.html -->
{% extends 'base.html' %}    <!-- Like inheriting from a parent window -->

{% block title %}Transactions{% endblock %}

{% block content %}
<h2>Today's Transactions</h2>

<table>
    <thead>
        <tr>
            <th>Receipt No</th>
            <th>Time</th>
            <th>Total</th>
            <th>Status</th>
            <th>Action</th>
        </tr>
    </thead>
    <tbody>
        {% for trans in transactions %}   <!-- Like Clarion LOOP with NEXT -->
        <tr>
            <td>{{ trans.receipt_no }}</td>
            <td>{{ trans.created_at|time:"H:i" }}</td>   <!-- |time is a filter/formatter -->
            <td>{{ trans.total|floatformat:2 }}</td>
            <td>{{ trans.status }}</td>
            <td>
                <a href="{% url 'transaction_detail' trans.id %}">View</a>
            </td>
        </tr>
        {% empty %}   <!-- Like Clarion IF ERRORCODE() right after SET -->
        <tr><td colspan="5">No transactions today.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### Django Template Tags Cheat Sheet

| Clarion | Django Template | Purpose |
|---|---|---|
| `IF x = y` | `{% if x == y %}` | Condition |
| `ELSE` | `{% else %}` | Else |
| `END` (of IF) | `{% endif %}` | End condition |
| `LOOP / END` | `{% for x in list %} {% endfor %}` | Loop |
| `!Comment` | `{# comment #}` | Comment |
| Print variable | `{{ variable }}` | Output value |
| `FORMAT(x, @N$10.2)` | `{{ x\|floatformat:2 }}` | Format number |
| `FORMAT(d, @D10/)` | `{{ d\|date:"m/d/Y" }}` | Format date |
| Link to procedure | `{% url 'view_name' %}` | Generate URL |

---

## SECTION 7 — Forms (Input Validation)
### (Your INPUT Controls + Validation)

Django Forms handle user input — they validate data before it hits the database, just like your Clarion field validation rules.

```python
# sales/forms.py
from django import forms
from .models import SalesTransaction

class PaymentForm(forms.Form):
    amount_tendered = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'payment-input',
            'autofocus': True,     # Auto-focus like Clarion USE(?Field)
            'placeholder': '0.00'
        })
    )

    def clean_amount_tendered(self):
        """Custom validation — like Clarion IF Field < 0 THEN MESSAGE()"""
        amount = self.cleaned_data['amount_tendered']
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount
```

**In your template:**
```html
<form method="post">
    {% csrf_token %}   <!-- Security token — always required, always include it -->
    {{ form.amount_tendered.label }}: {{ form.amount_tendered }}
    {% if form.amount_tendered.errors %}
        <span class="error">{{ form.amount_tendered.errors }}</span>
    {% endif %}
    <button type="submit">Process Payment</button>
</form>
```

---

## SECTION 8 — Sessions and Authentication
### (Your Global User Variables and Security)

### Login/Logout (Built Into Django)

```python
# users/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)           # Sets the session (like Clarion GLOBAL user vars)
            return redirect('pos_home')
        else:
            return render(request, 'users/login.html', {'error': 'Invalid credentials'})
    return render(request, 'users/login.html')

def user_logout(request):
    logout(request)
    return redirect('login')
```

### Protecting Views (Like Clarion Access Level Checks)

```python
# Simple protection — must be logged in
@login_required
def new_sale(request):
    ...

# Role-based protection — custom decorator
from functools import wraps
from django.http import HttpResponseForbidden

def manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.profile.role != 'MANAGER':
            return HttpResponseForbidden("Manager access required.")
        return view_func(request, *args, **kwargs)
    return wrapper

@manager_required
def void_transaction(request, transaction_id):
    ...
```

### Storing Data in Session (Like Clarion GLOBAL Variables)

```python
# Store something in session (survives across page requests)
request.session['current_pos_session_id'] = pos_session.id
request.session['cart'] = []

# Read from session
session_id = request.session.get('current_pos_session_id')
cart = request.session.get('cart', [])   # Default to empty list

# Clear session data
del request.session['cart']
```

---

## SECTION 9 — The POS Cart (Putting It All Together)
### (Your Most Important View — Session-Based Cart)

The cart is the core of your cashier screen. It lives in the session between page loads.

```python
# sales/views.py  — simplified POS cart

@login_required
def pos_screen(request):
    """Main cashier screen"""
    cart = request.session.get('cart', [])
    cart_total = sum(item['line_total'] for item in cart)

    return render(request, 'sales/pos_screen.html', {
        'cart': cart,
        'cart_total': cart_total
    })

@login_required
def scan_item(request):
    """Called when barcode is scanned or item searched"""
    if request.method == 'POST':
        barcode = request.POST.get('barcode', '').strip()

        try:
            variant = ProductVariant.objects.get(barcode=barcode, is_active=True)
        except ProductVariant.DoesNotExist:
            # Item not found — return error message
            return redirect('pos_screen')   # Or pass error in session

        # Check if item already in cart
        cart = request.session.get('cart', [])
        for item in cart:
            if item['variant_id'] == variant.id:
                item['qty'] += 1
                item['line_total'] = item['qty'] * item['unit_price']
                request.session.modified = True   # Tell Django session was changed
                return redirect('pos_screen')

        # Add new item to cart
        cart.append({
            'variant_id':   variant.id,
            'sku':          variant.product.sku,
            'product_name': variant.product.product_name,
            'color':        variant.color.name,
            'size':         variant.size.name,
            'qty':          1,
            'unit_price':   float(variant.price),
            'line_total':   float(variant.price),
        })
        request.session['cart'] = cart
        return redirect('pos_screen')

@login_required
def finalize_sale(request):
    """Convert cart to a saved transaction"""
    if request.method == 'POST':
        cart = request.session.get('cart', [])
        if not cart:
            return redirect('pos_screen')

        # Get or create the open POS session
        pos_session = POSSession.objects.get(
            cashier=request.user,
            status='OPEN'
        )

        # Create the transaction header
        total = sum(item['line_total'] for item in cart)
        transaction = SalesTransaction.objects.create(
            session=pos_session,
            cashier=request.user,
            business_date=pos_session.business_date,
            total=total,
            status='PENDING'
        )

        # Create transaction lines
        for item in cart:
            variant = ProductVariant.objects.get(id=item['variant_id'])
            SalesTransactionLine.objects.create(
                transaction=transaction,
                variant=variant,
                qty=item['qty'],
                unit_price=item['unit_price'],
                line_total=item['line_total']
            )

        # Clear the cart
        request.session['cart'] = []

        # Go to payment screen
        return redirect('process_payment', transaction_id=transaction.id)
```

---

## SECTION 10 — settings.py Deep Dive
### (Your INI File — But Much More Powerful)

```python
# pos_project/settings.py  — key settings you must know

# Database — your MySQL connection
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME':   'pos_db',          # Database name
        'USER':   'pos_user',        # MySQL username
        'PASSWORD': 'your_password', # Keep this in .env, not here!
        'HOST':   '127.0.0.1',
        'PORT':   '3306',
    }
}

# Installed apps — register every app you create
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',      # Session support
    # Your apps:
    'users',
    'inventory',
    'sales',
    'reports',
    'settings_app',
]

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Store sessions in DB
SESSION_COOKIE_AGE = 86400   # Session expires in 24 hours (in seconds)

# Login settings
LOGIN_URL = '/users/login/'         # Where to redirect if not logged in
LOGIN_REDIRECT_URL = '/sales/pos/'  # Where to go after login

# Static files (CSS, JS)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
```

### Using .env for Secrets (Never Hardcode Passwords)

```bash
pip install python-dotenv
```

```python
# .env file (never commit this to git!)
DB_NAME=pos_db
DB_USER=pos_user
DB_PASSWORD=secret123
FTP_HOST=ftp.yourserver.com
FTP_USER=ftpuser
FTP_PASS=ftppassword
SECRET_KEY=your-long-random-secret-key
```

```python
# settings.py
import os
from dotenv import load_dotenv
load_dotenv()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME':     os.getenv('DB_NAME'),
        'USER':     os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST':     '127.0.0.1',
        'PORT':     '3306',
    }
}
SECRET_KEY = os.getenv('SECRET_KEY')
```

---

## SECTION 11 — Common Django Commands
### (Your Daily Terminal Commands)

```bash
# Start development server (run this every time you work)
python manage.py runserver

# After changing any models.py:
python manage.py makemigrations
python manage.py migrate

# Create a superuser for admin access
python manage.py createsuperuser

# Open Django shell (like a Python REPL with your models loaded)
python manage.py shell

# In the shell, you can test queries interactively:
# >>> from inventory.models import Product
# >>> Product.objects.all()
# >>> Product.objects.filter(is_active=True).count()

# Check for errors without running
python manage.py check

# See what SQL a migration will run (useful for understanding)
python manage.py sqlmigrate inventory 0001
```

---

## SECTION 12 — Printing to Dot Matrix
### (The Non-Web Part of Django)

This is a Python task, not a Django task. Call it from your view after a successful sale.

```python
# utils/printer.py
import win32print   # Windows
import win32api

def print_receipt(transaction):
    """Print to dot matrix using raw text"""

    store_name    = "YOUR STORE NAME"
    printer_name  = "LPT1:"   # or your printer name from Windows

    # Build receipt text (40 columns for dot matrix)
    lines = []
    lines.append(store_name.center(40))
    lines.append("=" * 40)
    lines.append(f"Receipt #: {transaction.receipt_no}")
    lines.append(f"Date: {transaction.business_date}")
    lines.append(f"Cashier: {transaction.cashier.get_full_name()}")
    lines.append("-" * 40)

    for line in transaction.lines.all():
        item_line = f"{line.variant.product.product_name[:20]:<20}"
        item_line += f"{line.qty:>3} x {line.unit_price:>7.2f}"
        lines.append(item_line)
        lines.append(f"  Size: {line.variant.size} | Color: {line.variant.color}")
        lines.append(f"{'':>30}{line.line_total:>9.2f}")

    lines.append("-" * 40)
    lines.append(f"{'TOTAL':>30}{transaction.total:>9.2f}")
    lines.append(f"{'TENDERED':>30}{transaction.amount_tendered:>9.2f}")
    lines.append(f"{'CHANGE':>30}{transaction.change:>9.2f}")
    lines.append("=" * 40)
    lines.append("Thank you!".center(40))
    lines.append("\n\n\n")   # Paper feed

    receipt_text = "\n".join(lines)

    # Send to printer
    hPrinter = win32print.OpenPrinter(printer_name)
    try:
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, receipt_text.encode('ascii'))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)
```

---

## SECTION 13 — Barcode Scanner Handling
### (Keyboard Wedge — Simpler Than You Think)

Most barcode scanners work as **keyboard emulators** — they type the barcode and press Enter. Your HTML just needs a focused input field.

```html
<!-- In your POS cashier template -->
<form method="post" action="{% url 'scan_item' %}">
    {% csrf_token %}
    <input type="text"
           id="barcode_input"
           name="barcode"
           autocomplete="off"
           autofocus
           placeholder="Scan barcode or type SKU">
</form>

<script>
// Auto-clear and re-focus after scan
document.getElementById('barcode_input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        this.form.submit();
    }
});

// Keep focus on the barcode field always
// (so cashier doesn't have to click it after each scan)
document.addEventListener('click', function() {
    document.getElementById('barcode_input').focus();
});
window.onload = function() {
    document.getElementById('barcode_input').focus();
}
</script>
```

---

## Learning Sequence — Day by Day

Follow this order to match your POS project timeline:

| Day | Focus | POS Task |
|---|---|---|
| **1** | Sections 1–2: Project setup + Models | Create all models, run migrations |
| **2** | Section 3: Django Admin | Register all models, test data entry |
| **3** | Sections 4–5: URLs + Views + QuerySets | Build transaction list view |
| **4** | Section 6: Templates | Build the browse/list screens |
| **5** | Sections 7–8: Forms + Auth | Login, session open/close |
| **6** | Section 9: Cart logic | Full scan → cart → finalize flow |
| **7** | Section 10: Settings + .env | Production settings, secrets |
| **8** | Sections 12–13: Printing + Scanner | Receipt printing, scanner input |
| **9+** | Sections 11 + practice | Reports, FTP sync, polish |

---

## Quick Reference Card

### The 5 Files You Edit Every Day

| File | What It Does | Clarion Equivalent |
|---|---|---|
| `models.py` | Define data structure | Dictionary (.DCT) |
| `views.py` | Business logic + data fetching | PROCEDURE code |
| `urls.py` | Map URLs to views | MENU structure |
| `templates/*.html` | Screen layout | Window designer |
| `admin.py` | Register models for admin UI | Auto-browse |

### The Django Request Cycle (Memorize This)

```
Browser/Scanner
     ↓
  urls.py         ← "Which view handles /sales/scan/ ?"
     ↓
  views.py        ← "Get data, process logic"
     ↓
  models.py       ← "Read/write MySQL"
     ↓
  template.html   ← "Format the page"
     ↓
Browser/Cashier Screen
```

### Most Common Mistakes for Clarion Programmers

| Mistake | Why It Happens | Fix |
|---|---|---|
| Forgetting `{% csrf_token %}` in forms | No equivalent in Clarion | Always add it inside every `<form>` |
| Not running `makemigrations` after model change | Clarion auto-converts | Always run both commands after model edits |
| Trying to use `print()` to display on screen | Clarion `MESSAGE()` habit | Use template variables `{{ }}` instead |
| Forgetting `request.session.modified = True` | No Clarion equivalent | Required when modifying session dict in-place |
| Using Python `=` in template | Clarion habits | Use `{% if x == y %}` with double equals in templates |
| Not registering app in `INSTALLED_APPS` | No Clarion equivalent | Every new app must be added to settings.py |

---

## Recommended Tools

| Tool | Purpose | Download |
|---|---|---|
| **VS Code** | Code editor with Django support | code.visualstudio.com |
| **MySQL Workbench** | View/edit MySQL tables (like Clarion Data Viewer) | mysql.com |
| **Django Debug Toolbar** | See queries, session data, timing | `pip install django-debug-toolbar` |
| **Git + GitHub Desktop** | Version control | desktop.github.com |
| **Postman** | Test your URLs/views | postman.com |

```bash
# Essential pip installs for your POS
pip install django
pip install mysqlclient
pip install python-dotenv
pip install django-debug-toolbar   # Very helpful during development
pip install pywin32                # For dot matrix printing on Windows
```

---

*Guide Version 1.0 — Built for POS Django Migration Project*
*Stack: Python + Django + MySQL | Hardware: Dot Matrix Printer + Barcode Scanner*
