"""POS transaction and record code constants.

These constants centralize Clarion-style one-character codes used across
transactions, returns, discounts, void actions, and audit tagging.
"""

# Sign on/off labels and transaction markers
SIGN_ON_LABEL_PREFIX = "Sign On I.D. :"
SIGN_OFF_LABEL_PREFIX = "Sign Off I.D. :"

TRTYPE_SIGN = "S"
TRTYPE_ENTRY = "1"

RCODE_SIGN_ON = "A"
RCODE_SIGN_OFF = "B"

# Core record codes
RCODE_ITEM_ENTRY = "1"
RCODE_ITEM_DISCOUNT = "2"
RCODE_SUBTOTAL_DISCOUNT = "8"
RCODE_PAYMENT = "9"
RCODE_CASH_WITHDRAWAL = "3"
RCODE_ITEM_VOID = "V"

RCODE_X_READING = "X"
RCODE_Z_READING = "Z"

# Tags and void markers
TAG_ITEM_DISC_PERCENT = "IDC"
TAG_ITEM_DISC_AMOUNT = "ADC"
TAG_VOID_PREVIOUS = "P"
TAG_INVENTORY_PROCESS = "P"
TAG_PRICE_OVERRIDE = "POV"
TAG_ITEM_RETURN = "R"
TAG_ITEM_VOID = "V"
TAG_VOID_TRANS = "X"
TAG_CASH_LOAN = "L"
TAG_CASH_WITHDRAWAL = "W"

# Transaction type markers for void classification
# New canonical values for this codebase:
#   X = full void transaction
#   P = void previous transaction
#   V = item void
TRTYPE_VOID_TRANS = "X"
TRTYPE_VOID_PREVIOUS = "P"
TRTYPE_VOID_ITEM = "V"

# Legacy transaction type values that may already exist in prior data.
TRTYPE_VOID_TRANS_LEGACY = "V"
TRTYPE_VOID_ITEM_LEGACY = "L"

VOID_TRANSACTION_TYPES_ALL = [
    TRTYPE_VOID_TRANS,
    TRTYPE_VOID_TRANS_LEGACY,
    TRTYPE_VOID_PREVIOUS,
    TRTYPE_VOID_ITEM,
    TRTYPE_VOID_ITEM_LEGACY,
]
