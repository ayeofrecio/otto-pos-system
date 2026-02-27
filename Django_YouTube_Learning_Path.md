# Django YouTube Learning Path
### Curated for Clarion/Clipper Programmers — Python Known, Django New

---

## Your Viewing Strategy

You already know Python and think like a programmer. These resources are ordered specifically for your situation — no web dev background, building a real POS, 2–3 week deadline. **Don't binge-watch — code along in a practice project as you watch.**

---

## 🥇 STEP 1 — Start Here First

### Corey Schafer — Django Tutorials (Full Series)

**Playlist:**
```
youtube.com/playlist?list=PL-osiE80TeTtoQCKZ03TU5fNfx2UY6U4p
```

Universally considered the best Django series for someone who already knows Python. He builds a full blog app covering:

- Models and database setup
- Views and URL routing
- Templates and template inheritance
- Django Admin
- User authentication and sessions
- Login, logout, and registration

His style is clean, no fluff, very programmer-oriented — explains the **why** behind every concept, not just the how. As a Clarion programmer who already thinks in data structures and procedures, his logical teaching style will click fast.

**Watch Plan:**

| Parts | Topics | Your POS Benefit |
|---|---|---|
| Parts 1–4 | Setup, Models, Admin | Phase 1 foundation |
| Parts 5–6 | Views, Templates | Phase 4 cashier screen |
| Parts 7–10 | Auth, Login, Sessions | Phase 2 user sessions |
| Parts 11+ | Deployment, extras | Phase 9 deployment |

> **Recommendation:** Watch Parts 1–8 before writing any POS view code. The rest watch as you need them.

---

## 🥈 STEP 2 — Practical POS-Like Skills

### Dennis Ivy — Django E-Commerce Tutorial

**Playlist:**
```
youtube.com/watch?v=_ELCMngbM0E&list=PL-51WBLyFTg0omnamUjL1TCVov7yDTRng
```

Dennis builds a full e-commerce site with Django — the closest thing on YouTube to what your POS needs. Covers:

- Product models and variants
- Cart using sessions
- Order/transaction saving
- Checkout flow
- User management

**Why directly relevant to your POS:**

| E-Commerce Concept | Your POS Equivalent |
|---|---|
| Product catalog | Shoe inventory (SKU + size + color) |
| Add to cart | Scan item → add to cart |
| Cart session | POS cart between scans |
| Checkout / place order | Finalize sale → payment screen |
| Order history | Transaction list / receipt lookup |

> **Watch this after Corey Schafer Parts 1–6.** You'll recognize all the patterns and see how they apply directly to your cashier flow.

---

## 🥉 STEP 3 — Reports and ORM Deep Dive

### Very Academy — Django ORM Mastery

**Search on YouTube:**
```
Very Academy Django ORM
```

One of the best deep-dive series on Django's QuerySet and ORM — which you'll use heavily for your X/Z readings and daily sales reports. Covers:

- Complex filtering and lookups
- Aggregates (Sum, Count, Avg) — for sales totals
- Annotations — for per-product sales breakdown
- Related table queries — for transaction + line item reports
- Optimizing queries (avoiding slow report generation)

> **Watch this during Phase 7 (Reports).** Don't watch it too early — get comfortable with basic ORM first through Corey's series.

---

## 🎯 BONUS — Quick Reference When Stuck

### Tech With Tim — Django Topics

**Search on YouTube:**
```
Tech With Tim Django
```

Short, focused videos on specific Django topics. Great when you're stuck on one concept and don't want to scrub through a long tutorial. Think of it as your **"look up a specific procedure"** resource — the YouTube equivalent of searching the Clarion manual for one function.

Good videos to find from his channel:
- Django Forms explained
- Django Sessions explained
- Django REST basics
- Django with MySQL setup

---

## Viewing Schedule Mapped to Your POS Phases

| Week | POS Phase | Watch |
|---|---|---|
| **Week 1, Days 1–2** | Phase 1 — Models & Setup | Corey Schafer Parts 1–4 |
| **Week 1, Days 2–3** | Phase 2 — Auth & Sessions | Corey Schafer Parts 7–10 |
| **Week 1, Days 3–5** | Phase 3 — Central DB Sync | Corey Schafer Parts 5–6 |
| **Week 1 Day 5 – Week 2 Day 2** | Phase 4 — Cashier Frontend | Dennis Ivy E-commerce Series |
| **Week 2, Days 3–4** | Phase 6 — Void & Returns | Tech With Tim (specific topics) |
| **Week 2, Days 4–5** | Phase 7 — Reports | Very Academy ORM Series |
| **As needed** | Any blocker | Tech With Tim |

---

## The Golden Rule

> Don't just watch — **code along in a separate practice project** alongside your POS.
>
> The moment you try to apply what you watched to real POS code is when it actually sticks. Corey Schafer's blog project and your POS share more in common than you'd think — users, sessions, forms, database records. The patterns are identical, only the domain is different.

---

## Quick Channel Summary

| Channel | Style | Best For |
|---|---|---|
| **Corey Schafer** | Thorough, logical, Python-focused | Complete Django foundation |
| **Dennis Ivy** | Project-based, practical | Cart, products, orders (POS-like) |
| **Very Academy** | Deep dives, reference-style | ORM, queries, reports |
| **Tech With Tim** | Short and focused | Quick answers when stuck |

---

*Reference guide for POS Django Migration Project*
*Pair this with: Django Training Guide for Clarion Programmers.md*
