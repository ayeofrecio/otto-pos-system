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

## Size Lookup — `SizeTable()`

`SizeTable()` always runs **right after** `ColorTable()` — it works in parallel to build the size picker for the same item.

```clipper
Static Function SizeTable(cIcode)

   POSSIZE->(DelPosSize())          // clear the temp size table

   ITMDTL->(DBSetOrder(1))
   If ITMDTL->(DBSeek(cIcode))     // find item in detail table
      POSSIZE->(DBSetOrder(2))

      While !ITMDTL->(Eof())
         If !(padl(Alltrim(ITMDTL->icode),15) == padl(Alltrim(cIcode),15))
            Exit                   // stop when item code changes
         EndIf
         If POSSIZE->(DBSeek(ITMDTL->size))
            ITMDTL->(DBSkip())
            Loop                   // skip if size already in POSSIZE
         EndIf
         POSSIZE->(NetAppBlank(0))
         POSSIZE->code := ITMDTL->size
         POSSIZE->desc := GetSizeDesc(ITMDTL->size)
         ITMDTL->(DBSkip())
      EndDo
      POSSIZE->(DBCommit())
   Else
      // item not in ITMDTL? load ALL sizes from the SIZE master table
      SIZE->(DBGotop())
      While !SIZE->(Eof())
         POSSIZE->(NetAppBlank(0))
         POSSIZE->code := SIZE->code
         POSSIZE->desc := SIZE->size
         SIZE->(DBSkip())
      EndDo
      POSSIZE->(DBCommit())
   EndIf

   aDtlFld[pISize] := ""
   If POSSIZE->(RECCOUNT()) > 0
      aDtlFld[pISize] := POSSIZE->(GetSize())   // show size picker popup
   EndIf
```

### How it differs from `ColorTable()`

| Aspect | `ColorTable()` | `SizeTable()` |
|---|---|---|
| Temp table populated | `POSCOLOR` | `POSSIZE` |
| Description helper | `GetColorDesc()` | `GetSizeDesc()` |
| Multi override (90–99) | Yes — uses `ITMDTL->MULTI` | No — straightforward size name lookup |
| Fallback when not in ITMDTL | Loads all from `COLORS` | Loads all from `SIZE` |
| Picker function | `GetColor()` | `GetSize()` |

### `GetSizeDesc()` — straightforward lookup

Unlike `GetColorDesc()`, there is **no 90–99 special range** in the size lookup. It simply seeks the `SIZE` master table by code and returns the size name:

```clipper
Function GetSizeDesc(cSizeCode)
   SIZE->(DBSetOrder(1))
   If SIZE->(DBSeek(cSizeCode))
      cRetVal := SIZE->size
   Else
      cRetVal := ""
   EndIf
Return cRetVal
```

### `GetSize()` — the size picker popup

Just like `GetColor()`, this is a mandatory popup — the cashier **cannot ESC out**. It loops until a valid size is selected:

```clipper
Static Function GetSize()
   DO WHILE .T.
      McSearch(aCoord, aHeader, aOrd, cColor, 'Search Size')
      If LastKey() = K_ESC
         ALERT("Size Required!")
         LOOP
      Else
         EXIT
      EndIf
   ENDDO
Return code
```

---

## Combined Flow: Color + Size for a Multi-color Item

```
Cashier scans barcode  (short / alpha-ending 12-char)
        │
        ▼
  ColorTable(cIcode)
  ├── Seek ITMDTL by item code
  ├── For each variant row:
  │     color code last 2 digits >= 90?
  │       YES → label = ITMDTL->MULTI
  │        NO → label = COLORS->color
  ├── Populate POSCOLOR temp table
  └── Show color picker popup (mandatory)
        │
        ▼
  aDtlFld[pIColor] saved
        │
        ▼
  SizeTable(cIcode)
  ├── Seek ITMDTL by item code
  ├── For each variant row:
  │     GetSizeDesc(ITMDTL->size) → SIZE master lookup
  ├── Populate POSSIZE temp table
  └── Show size picker popup (mandatory)
        │
        ▼
  aDtlFld[pISize] saved
        │
        ▼
  GetColorDesc called with lFindItmDtl = 1
  → seeks ITMDTL Order 3: ItemCode + Color + Size
  → if color is 90–99, returns ITMDTL->MULTI
    as the final variant description
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
| Size master | `SIZE` | Standard size code-to-name lookup |
| POS color temp | `POSCOLOR` | Temp table populated per transaction for the color picker popup |
| POS size temp | `POSSIZE` | Temp table populated per transaction for the size picker popup |

---

## Summary

- Color codes **90–99** signal a **multi-color or mixed-color variant**.
- The `COLORS` master table description is **ignored** for these codes; `ITMDTL->MULTI` is used instead.
- The `MULTI` field in `ITMDTL` provides the actual label, which can be variant-specific (e.g., `"RED/BLUE STRIPE"`) or generic (e.g., `"MULTICOLOR"`).
- `SizeTable()` always runs right after `ColorTable()` — it builds the `POSSIZE` temp table from `ITMDTL->size` records for the same item and shows a mandatory size picker.
- Size lookup has **no 90–99 special range** — `GetSizeDesc()` is a plain seek against the `SIZE` master table.
- Both color and size pickers are **mandatory** — pressing ESC just loops back with an alert until a valid selection is made.
- When a full `ItemCode + Color + Size` key is available, the system does a precise seek on `ITMDTL` Order 3 to retrieve the exact multi-variant label.
