"""
Transaction Logging Service for Django POS
Integrates Clipper-style transaction logging into Django views

Place this file in: sales/services/transaction_service.py
"""

from decimal import Decimal
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from django.db import transaction as db_transaction
from django.conf import settings

# Import your Django models
# from sales.models import TempTransaction, TransactionLog


class RecordCode:
    """Record codes matching Clipper SALES.PRG"""
    ITEM_ENTRY = 'I'
    ITEM_DISCOUNT = 'D'
    SUBTOTAL_DISCOUNT = 'S'
    PAYMENT = 'P'
    ITEM_RETURN = 'R'
    ITEM_VOID = 'V'
    VOID_TRANS = 'X'


class TransactionType:
    """Transaction types"""
    ENTRY = 'E'
    SIGN = 'S'
    SALE = 'S'


class TransactionService:
    """
    Service class for handling POS transaction logging
    Equivalent to Clipper SALES.PRG SaveToLog() function (lines 1808-1842)
    
    Usage in Django views:
        service = TransactionService()
        service.save_to_transaction_log(
            cart_lines=cart_lines,
            transaction_no=trans_no,
            user_id=user_id,
            salesman_code=salesman_code,
            ...
        )
    """
    
    def __init__(self):
        self.store_id = "001"
        self.terminal_id = "001"
    
    @db_transaction.atomic
    def save_to_transaction_log(
        self,
        cart_lines,  # QuerySet of TempTransaction
        transaction_no: str,
        transaction_date: date,
        transaction_time: str,
        user_id: str,
        salesman_code: str = "",
        tender_entries: List[tuple] = None,  # List of (pcode, amount, desc, is_cash)
        subtotal_discount_pct: Decimal = Decimal("0"),
        subtotal_discount_label: str = "",
        si_number: str = "",
        void_tag: str = ""
    ):
        """
        Save transaction from TEMPTRANS (TempTransaction) to TLOG (TransactionLog)
        This is the main function equivalent to Clipper's SaveToLog() - lines 1808-1842
        
        Args:
            cart_lines: QuerySet of TempTransaction items
            transaction_no: Transaction number
            transaction_date: Business date
            transaction_time: Transaction time (HH:MM format)
            user_id: Cashier ID
            salesman_code: Salesman/user_id2
            tender_entries: List of payment tenders [(pcode, amount, desc, is_cash), ...]
            subtotal_discount_pct: Transaction-level discount percentage
            subtotal_discount_label: Discount label
            si_number: Sales invoice number
            void_tag: Void transaction tag ('X' for voided)
            
        Returns:
            int: Number of records saved to TLOG
        """
        from sales.models import TransactionLog
        
        records_saved = 0
        
        # Process each cart line
        for temp_line in cart_lines:
            # Apply business logic from Clipper SaveToLog (lines 1818-1842)
            item_price_ext = temp_line.item_price_ext or Decimal("0")
            disc_code = temp_line.discount_code or ""
            item_disc = temp_line.item_discount or Decimal("0")
            tag1 = temp_line.tag1 or ""
            tag2 = temp_line.tag2 or ""
            tag3 = temp_line.tag3 or ""
            tag4 = temp_line.tag4 or ""
            
            # Get return_code from temp line (should be set during cart operations)
            return_code = getattr(temp_line, 'return_code', RecordCode.ITEM_ENTRY)
            
            # Line 1818-1819: Negate discount amounts
            # In Clipper: If RCODE in (D, S) then negate IPRICEE
            if return_code in [RecordCode.ITEM_DISCOUNT, RecordCode.SUBTOTAL_DISCOUNT]:
                item_price_ext = item_price_ext * -1
            
            # Line 1820-1821: Handle price override
            # In Clipper: If RCODE not in (P, S) and TAG != 'D' then use PRICEOVER
            if (return_code not in [RecordCode.PAYMENT, RecordCode.SUBTOTAL_DISCOUNT] 
                and temp_line.tag != 'D'):
                disc_code = temp_line.price_override or disc_code
            
            # Line 1822-1823: Clear item discount for non-subtotal discounts
            # In Clipper: If RCODE != S and IDISC exists and TAG != 'D' then IDISC = 0
            if (return_code != RecordCode.SUBTOTAL_DISCOUNT 
                and item_disc and temp_line.tag != 'D'):
                item_disc = Decimal("0")
            
            # Line 1824-1825: Handle item return tag
            # In Clipper: If ITAG1 == pItmReturn then preserve it
            if temp_line.tag1 == RecordCode.ITEM_RETURN:
                tag1 = temp_line.tag1
            
            # Line 1826-1827: Handle item void tag
            # In Clipper: If ITAG1 == pItmVoid then set ITAG2
            if temp_line.tag1 == RecordCode.ITEM_VOID:
                tag2 = temp_line.tag1
            
            # Line 1828-1829: Handle void transaction tag
            # In Clipper: If cTag4 == pVoidTrans then set ITAG4
            if void_tag == RecordCode.VOID_TRANS:
                tag4 = void_tag
            
            # Create TransactionLog record
            TransactionLog.objects.create(
                user_id=user_id,
                user_id2=salesman_code,
                terminal_id=self.terminal_id,
                store_id=self.store_id,
                transaction_no=transaction_no,
                transaction_date=transaction_date,
                transaction_time=transaction_time,
                transaction_type=TransactionType.SALE,
                return_code=return_code,
                item_ref=si_number,
                # Item details
                item_code=temp_line.item_code or "",
                item_description=temp_line.item_description or "",
                item_qty=temp_line.item_qty or Decimal("0"),
                item_uom=getattr(temp_line, 'item_uom', ""),
                item_supplier=getattr(temp_line, 'item_supplier', ""),
                item_department=getattr(temp_line, 'item_department', ""),
                item_class=getattr(temp_line, 'item_class', ""),
                item_size=temp_line.item_size or "",
                item_color=temp_line.item_color or "",
                item_type=getattr(temp_line, 'item_type', ""),
                # Pricing (with transformations applied)
                item_cost=getattr(temp_line, 'item_cost', Decimal("0")),
                item_price=temp_line.item_price or Decimal("0"),
                item_discount=item_disc,
                discount_code=disc_code,
                item_price_ext=item_price_ext,
                # Tags
                tag1=tag1,
                tag2=tag2,
                tag3=tag3,
                tag4=tag4,
                promo_tag=getattr(temp_line, 'promo_tag', ""),
                # Additional fields
                table_id=getattr(temp_line, 'table_id', ""),
                served_by="",
                customer_count="",
            )
            records_saved += 1
        
        # Add subtotal discount record if applicable
        if subtotal_discount_pct > 0:
            subtotal = sum(line.item_price_ext or Decimal("0") for line in cart_lines)
            discount_amount = round((subtotal * subtotal_discount_pct / 100), 4)
            
            TransactionLog.objects.create(
                user_id=user_id,
                user_id2=salesman_code,
                terminal_id=self.terminal_id,
                store_id=self.store_id,
                transaction_no=transaction_no,
                transaction_date=transaction_date,
                transaction_time=transaction_time,
                transaction_type=TransactionType.SALE,
                return_code=RecordCode.SUBTOTAL_DISCOUNT,
                item_ref=si_number,
                item_description=subtotal_discount_label or f"{subtotal_discount_pct}% Total Discount",
                item_price=subtotal,
                item_discount=subtotal_discount_pct,
                discount_code='%',
                item_price_ext=discount_amount * -1,  # Negated per line 1818-1819
            )
            records_saved += 1
        
        # Add payment records if tender_entries provided
        if tender_entries:
            for pcode, amount, desc, is_cash in tender_entries:
                TransactionLog.objects.create(
                    user_id=user_id,
                    user_id2=salesman_code,
                    terminal_id=self.terminal_id,
                    store_id=self.store_id,
                    transaction_no=transaction_no,
                    transaction_date=transaction_date,
                    transaction_time=transaction_time,
                    transaction_type=TransactionType.SALE,
                    return_code=RecordCode.PAYMENT,
                    item_ref=si_number,
                    discount_code=pcode,
                    item_price=amount,
                    item_price_ext=amount,
                    item_description=desc,
                )
                records_saved += 1
        
        return records_saved
    
    def add_item_to_temp(
        self,
        user_id: str,
        transaction_no: str,
        item_code: str,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        **kwargs
    ):
        """
        Add item to TempTransaction table
        Equivalent to SaveToTmp() in Clipper
        
        Args:
            user_id: Cashier ID
            transaction_no: Transaction number
            item_code: Item barcode/code
            description: Item description
            quantity: Quantity
            unit_price: Unit price
            **kwargs: Additional fields (size, color, department, etc.)
        
        Returns:
            TempTransaction object
        """
        from sales.models import TempTransaction
        
        extended_price = quantity * unit_price
        current_time = datetime.now().strftime('%H:%M')
        
        temp_item = TempTransaction.objects.create(
            user_id=user_id,
            terminal_id=self.terminal_id,
            store_id=self.store_id,
            transaction_no=transaction_no,
            transaction_date=date.today(),
            transaction_time=current_time,
            transaction_type=TransactionType.ENTRY,
            return_code=RecordCode.ITEM_ENTRY,
            item_code=item_code,
            item_description=description,
            item_qty=quantity,
            item_price=unit_price,
            item_price_ext=extended_price,
            item_size=kwargs.get('size', ''),
            item_color=kwargs.get('color', ''),
            item_department=kwargs.get('department', ''),
            item_class=kwargs.get('class_code', ''),
            item_uom=kwargs.get('uom', ''),
            item_supplier=kwargs.get('supplier', ''),
            item_type=kwargs.get('item_type', ''),
            item_tax_code=kwargs.get('tax_code', '0'),
        )
        
        return temp_item
    
    def clear_temp_table(self, user_id: str, transaction_no: str):
        """
        Clear TempTransaction table for the given transaction
        Called after successful save to TransactionLog
        
        This mimics Clipper's approach of dropping TEMP.DBF after transfer
        """
        from sales.models import TempTransaction
        
        deleted_count, _ = TempTransaction.objects.filter(
            user_id=user_id,
            terminal_id=self.terminal_id,
            store_id=self.store_id,
            transaction_no=transaction_no,
        ).delete()
        
        return deleted_count
    
    def get_transaction_log(self, transaction_no: str) -> List[Dict[str, Any]]:
        """
        Retrieve all TransactionLog records for a transaction number
        
        Args:
            transaction_no: Transaction number
            
        Returns:
            List of transaction log records as dictionaries
        """
        from sales.models import TransactionLog
        
        logs = TransactionLog.objects.filter(
            transaction_no=transaction_no
        ).order_by('id')
        
        return list(logs.values())
    
    def get_transaction_summary(self, transaction_no: str) -> Dict[str, Any]:
        """
        Get transaction summary (totals, counts, etc.)
        
        Args:
            transaction_no: Transaction number
            
        Returns:
            Dictionary with transaction summary
        """
        from sales.models import TransactionLog
        
        logs = TransactionLog.objects.filter(transaction_no=transaction_no)
        
        items_total = sum(
            log.item_price_ext for log in logs 
            if log.return_code == RecordCode.ITEM_ENTRY
        ) or Decimal("0")
        
        discount_total = sum(
            log.item_price_ext for log in logs 
            if log.return_code == RecordCode.SUBTOTAL_DISCOUNT
        ) or Decimal("0")
        
        payment_total = sum(
            log.item_price_ext for log in logs 
            if log.return_code == RecordCode.PAYMENT
        ) or Decimal("0")
        
        return {
            "transaction_no": transaction_no,
            "items_total": items_total,
            "discount_total": discount_total,
            "grand_total": items_total + discount_total,
            "payment_total": payment_total,
            "item_count": logs.filter(return_code=RecordCode.ITEM_ENTRY).count(),
        }
