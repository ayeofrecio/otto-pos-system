# Multi-Color (90–99) System — SALES.PRG / MAIN.PRG

## Overview

The **90–99 color code range** is a special convention in the POS system that flags an item as a **multi-color variant**. Instead of resolving to a plain color name from the `COLORS` master table, items with a color code in this range display a custom label stored in the `MULTI` field of the `ITMDTL` (item detail) table.

---

## How It Is Detected

Inside `GetColorDesc()` in `SALES.PRG`:

```clipper
If VAL(SUBSTR(cColorcode,-2,2)) >= 90 .AND. VAL(SUBSTR(cColorcode,-2,2)) <= 99
```

The last 2 digits of the color code are extracted and checked. If the value falls between **90 and 99 inclusive**, the normal color description is **overridden** with the `MULTI` field from `ITMDTL`.

---

## Full Logic of `GetColorDesc()`

```clipper
Function GetColorDesc(cColorcode, lFindItmDtl)

   // Step 1: Normal color lookup
   If COLORS->(DBSeek(cColorCode))
      cRetVal := COLORS->color        // e.g., "RED", "BLUE"
   Else
      cRetVal := ""
   EndIf

   // Step 2: Multi-color override
   If VAL(SUBSTR(cColorcode,-2,2)) >= 90 .AND. VAL(SUBSTR(cColorcode,-2,2)) <= 99
      If lFindItmDtl = 1 .AND. !Empty(adtlFld[3])
         ITMDTL->(DBSetOrder(3))
         If ITMDTL->(DBSeek(adtlFld[3] + aDtlFld[12] + aDtlFld[11]))
            cRetVal := ITMDTL->MULTI   // precise variant label
         EndIf
      Else
         cRetVal := ITMDTL->MULTI      // current record's MULTI field
      EndIf
   EndIf

Return cRetVal
```

---

## Two Sub-cases for the Multi Override

### Sub-case A — `lFindItmDtl = 1` (precise lookup)

Used when the cashier has already selected **both color and size**, and the system needs the exact label for that combination.

| Key component | Array field | Meaning |
|---|---|---|
| `adtlFld[3]` | `pItemCode` | The base item code |
| `aDtlFld[12]` | `pIColor` | The selected color code (90–99) |
| `aDtlFld[11]` | `pISize` | The selected size code |

`ITMDTL` is seeked on **Order 3** using the composite key `ItemCode + Color + Size`. If found, `ITMDTL->MULTI` becomes the description (e.g., `"RED/BLUE STRIPE"` or `"MULTICOLOR"`).

### Sub-case B — `lFindItmDtl = 0` (list building)

Used when `ColorTable()` is iterating through all color records for an item and populating the `POSCOLOR` temp table. For each row, `GetColorDesc(ITMDTL->color, 0)` is called. When it encounters a 90–99 code, it reads `MULTI` directly from the currently positioned `ITMDTL` record — no extra seek needed.

---

## Where `GetColorDesc` Is Called

| Call site | `lFindItmDtl` value | Purpose |
|---|---|---|
| `ColorTable()` — building POSCOLOR list | `0` | Labeling each color row during population |
| Elsewhere (display/print) | `1` | Precise lookup by `ItemCode + Color + Size` |

---

## Flow: Multi-color Item End to End

```
Cashier scans item barcode
        │
        ▼
  ColorTable() builds POSCOLOR list
  from ITMDTL records for this item
        │
        ├── For each ITMDTL row:
        │       GetColorDesc(ITMDTL->color, 0)
        │               │
        │       Last 2 digits of color code >= 90?
        │               │
        │          YES  →  use ITMDTL->MULTI as label
        │           NO  →  use COLORS->color as label
        │
        ▼
  Cashier picks from color popup
  (selecting a 90–99 code = multi-color)
        │
        ▼
  aDtlFld[pIColor] = the 90–99 code
        │
        ▼
  GetColorDesc called again with lFindItmDtl = 1
  → seeks ITMDTL by ItemCode + Color + Size (Order 3)
  → returns ITMDTL->MULTI as final description
```

---

## Where This Fits in `GetItem()` (SALES.PRG)

`ColorTable()` is called from `GetItem()` under two conditions:

1. **Short barcode (≤ 11 chars) and `POSITM->IColor == "1"`** — item master flags this item as color/size-tracked but the barcode does not encode color+size; the cashier must pick manually.
2. **12-char barcode where the last character IS a letter** — same fallback to manual selection.

In both cases, `ColorTable()` calls `GetColorDesc()` for every color row it builds, which is where the 90–99 detection fires.

---

## Key Tables Referenced

| Table | Alias | Role |
|---|---|---|
| Item detail variants | `ITMDTL` | Stores per-variant records including `color`, `size`, and `MULTI` fields |
| Color master | `COLORS` | Standard color code-to-name lookup |
| POS color temp | `POSCOLOR` | Temp table populated per transaction for the color picker popup |

---

## Summary

- Color codes **90–99** signal a **multi-color or mixed-color variant**.
- The `COLORS` master table description is **ignored** for these codes.
- The `MULTI` field in `ITMDTL` provides the actual label, which can be variant-specific (e.g., `"RED/BLUE STRIPE"`) or generic (e.g., `"MULTICOLOR"`).
- When a full `ItemCode + Color + Size` key is available, the system does a precise seek on `ITMDTL` Order 3 to retrieve the exact variant label.
- When just building the color list, the system reads `MULTI` from the currently positioned `ITMDTL` record.
