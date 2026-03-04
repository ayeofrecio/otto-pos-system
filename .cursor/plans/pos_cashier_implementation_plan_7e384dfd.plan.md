---
name: POS Cashier Implementation Plan
overview: Implementation plan for the POS cashier frontend. Backend views and URLs exist; remaining work is templates, HTMX partials, static JS, and database seeding.
todos: []
isProject: false
---

# POS Cashier Frontend — Implementation Plan

## Current State

**Already implemented:**

- [sales/views.py](d:\MyApps\POS\pos_project\sales\views.py): `pos_login`, `pos_logout`, `cashier_view`, `cart_add`, `cart_remove`, `cart_new`, `pay_view`
- [sales/urls.py](d:\MyApps\POS\pos_project\sales\urls.py): `/pos/login/`, `/pos/`, `/pos/cart/add/`, `/pos/cart/remove/`, `/pos/cart/new/`, `/pos/pay/`
- [config/urls.py](d:\MyApps\POS\pos_project\config\urls.py): Includes sales app at `/pos/`

**Missing:**

- `templates/` and `static/` directories are empty
- No `login.html`, `cashier.html`, or HTMX partials
- No `cashier.js` for barcode handling
- `POSTransCounter` table may be empty (transaction numbering will fail)

---

## Implementation Order

### 1. Create template directories

```
pos_project/
├── templates/
│   └── sales/
│       └── partials/
└── static/
    └── sales/
```

### 2. Login template — [templates/sales/login.html](d:\MyApps\POS\pos_project\templates\sales\login.html)

- Simple form: username, password, submit
- POST to `sales:pos_login`
- Show `{{ error }}` when present
- Link or redirect to `/pos/` after success
- Minimal styling (centered form, basic inputs)

### 3. Cashier template — [templates/sales/cashier.html](d:\MyApps\POS\pos_project\templates\sales\cashier.html)

Layout per plan:


| Zone             | Content                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| **Header**       | `{{ date }}` (left), `{{ time }}` (right), Receipt #`{{ receipt_no }}`, Cashier: `{{ cashier }}` |
| **Barcode area** | Large `<input id="barcode-input">` with placeholder "Scan or enter barcode here", `autofocus`    |
| **Right column** | `TOTAL: ₱{{ total }}`, `{{ item_count }} items`, scrollable list of cart lines                   |
| **Center**       | Item detail panel: `{{ last_item }}` (description, barcode/code, size, color, price)             |
| **Bottom**       | Buttons: Pay, Void, Hold, Qty (or New Transaction)                                               |


- Barcode form: POST to `sales:cart_add`, include `{% csrf_token %}`, target HTMX swap or use vanilla JS fetch
- Cart list: each line shows `item_description`, `item_qty x item_price`, `item_price_ext`; remove button with `rec_ctr`
- Optional: JS `setInterval` to refresh time every second
- Add HTMX: `hx-post`, `hx-target`, `hx-swap` for add/remove without full reload

### 4. HTMX partials

**[templates/sales/partials/cart_added.html](d:\MyApps\POS\pos_project\templates\sales\partials\cart_added.html)** (returned by `cart_add` and `cart_remove` when `HX-Request`):

- Update cart list + total + item count + item detail in one response
- Use `hx-swap-oob` or return a wrapper that replaces `#cart-summary` and `#item-detail`

**Option A — Single partial with multiple OOB swaps:**

```html
<div id="cart-summary" hx-swap-oob="true">
  <!-- total, item count, cart lines -->
</div>
<div id="item-detail" hx-swap-oob="true">
  <!-- last_item detail -->
</div>
```

**Option B — Full-page fragment:** Return a fragment that the parent swaps into a container; parent template has `#cart-container` that gets replaced.

**[templates/sales/partials/cart_error.html](d:\MyApps\POS\pos_project\templates\sales\partials\cart_error.html)**:

- Simple `{{ error }}` message (e.g. "Item not found")
- Swap into a toast/alert area

### 5. Static JS — [static/sales/cashier.js](d:\MyApps\POS\pos_project\static\sales\cashier.js)

- On `keydown` Enter in barcode input: prevent default, submit form (or trigger HTMX/fetch)
- Keep barcode input focused after add
- Optional: live time tick
- Optional: HTMX `hx-trigger="keydown[keyCode==13] from:#barcode-input"` to avoid custom JS

### 6. POSTransCounter seeding

- Ensure at least one row exists for transaction numbering
- Options:
  - Data migration: `POSTransCounter.objects.get_or_create(defaults={"transaction_no": "00000001"})`
  - Or Django admin: create one row manually
  - Or add a `post_migrate` signal / management command

### 7. Django user for login

- Create a cashier user via `python manage.py createsuperuser` or Django admin
- Login at `/pos/login/` with that user

---

## File Checklist


| File                                       | Purpose                                                 |
| ------------------------------------------ | ------------------------------------------------------- |
| `templates/sales/login.html`               | Login form                                              |
| `templates/sales/cashier.html`             | Main POS layout                                         |
| `templates/sales/partials/cart_added.html` | HTMX response: cart + total + detail                    |
| `templates/sales/partials/cart_error.html` | HTMX response: error message                            |
| `static/sales/cashier.js`                  | Barcode Enter handling, focus                           |
| Migration or fixture                       | Seed `POSTransCounter` with `transaction_no='00000001'` |


---

## HTMX vs Vanilla JS

**HTMX approach:**

- Add `<script src="https://unpkg.com/htmx.org@1.9.10"></script>` to cashier base
- Form: `hx-post="{% url 'sales:cart_add' %}"`, `hx-target="#cart-container"`, `hx-swap="innerHTML"`
- Barcode input: `hx-trigger="keydown[keyCode==13] from:#barcode-input"`
- Remove buttons: `hx-post`, `hx-include="[name=rec_ctr]"`

**Vanilla JS approach:**

- Form submit via JS on Enter
- `fetch()` to `cart_add`, parse HTML or JSON, update DOM manually
- Simpler dependency, more code

**Recommendation:** Use HTMX for faster implementation and less custom JS.

---

## Design Reference

- Mockup: [assets/pos-cashier-design-mockup.png](d:\MyApps\POS\assets\pos-cashier-design-mockup.png)
- Layout: Header (date/time) → Barcode area → Center (item detail) + Right (cart/total) → Action buttons

