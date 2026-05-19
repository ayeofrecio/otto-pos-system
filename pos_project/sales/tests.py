import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import POSSession
from .models import Item, Payment, Tender, TempTransaction, TransactionHeader


class ItemEntryTenderFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="cashier1",
            password="testpass123",
            role="cashier",
            is_active=True,
        )
        self.client.force_login(self.user)

        self.session = POSSession.objects.create(
            cashier=self.user,
            terminal_id="001",
            store_id="001",
            business_date=date.today(),
            opening_cash=Decimal("1000.00"),
            status=POSSession.STATUS_OPEN,
        )

        self.item = Item.objects.create(
            icode="ITEM001",
            short_desc="Test Item",
            price=Decimal("100.00"),
        )

        self.cash_tender = Tender.objects.create(
            pcode="P01",
            description="Cash",
            pallow="Y",
            pchange="Y",
        )
        self.debit_tender = Tender.objects.create(
            pcode="P02",
            description="Debit",
            pallow="Y",
            pchange="N",
        )

    def _add_item_to_cart(self):
        response = self.client.post(
            reverse("sales:cart_add"),
            {
                "barcode": self.item.icode,
                "qty": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TempTransaction.objects.exists())

    def _complete_payment(self, entries):
        return self.client.post(
            reverse("sales:payment_complete"),
            {"tender_entries": json.dumps(entries)},
        )

    def test_item_entry_with_cash_tender(self):
        self._add_item_to_cart()

        response = self._complete_payment([
            {"pcode": self.cash_tender.pcode, "amount": "100.00"},
        ])

        self.assertRedirects(response, reverse("sales:receipt"))

        header = TransactionHeader.objects.get()
        payment = Payment.objects.get(header=header)

        self.assertEqual(header.amount_total, Decimal("100.00"))
        self.assertEqual(header.amount_tendered, Decimal("100.00"))
        self.assertEqual(header.change_amount, Decimal("0"))

        self.assertEqual(payment.pcode, self.cash_tender.pcode)
        self.assertEqual(payment.tender_desc, "Cash")
        self.assertEqual(payment.amount, Decimal("100.00"))

        self.assertFalse(TempTransaction.objects.exists())

    def test_item_entry_with_debit_tender(self):
        self._add_item_to_cart()

        response = self._complete_payment([
            {
                "pcode": self.debit_tender.pcode,
                "amount": "100.00",
                "payment_reference": "DBT-0001",
            },
        ])

        self.assertRedirects(response, reverse("sales:receipt"))

        header = TransactionHeader.objects.get()
        payment = Payment.objects.get(header=header)

        self.assertEqual(header.amount_total, Decimal("100.00"))
        self.assertEqual(header.amount_tendered, Decimal("100.00"))
        self.assertEqual(header.change_amount, Decimal("0"))

        self.assertEqual(payment.pcode, self.debit_tender.pcode)
        self.assertEqual(payment.tender_desc, "Debit")
        self.assertEqual(payment.payment_reference, "DBT-0001")
        self.assertEqual(payment.amount, Decimal("100.00"))

        self.assertFalse(TempTransaction.objects.exists())

    def test_item_entry_with_multiple_tenders(self):
        self._add_item_to_cart()

        response = self._complete_payment([
            {"pcode": self.cash_tender.pcode, "amount": "40.00"},
            {
                "pcode": self.debit_tender.pcode,
                "amount": "60.00",
                "payment_reference": "DBT-0002",
            },
        ])

        self.assertRedirects(response, reverse("sales:receipt"))

        header = TransactionHeader.objects.get()
        payments = Payment.objects.filter(header=header).order_by("pcode")

        self.assertEqual(header.amount_total, Decimal("100.00"))
        self.assertEqual(header.amount_tendered, Decimal("100.00"))
        self.assertEqual(header.change_amount, Decimal("0"))

        self.assertEqual(payments.count(), 2)

        self.assertEqual(payments[0].pcode, self.cash_tender.pcode)
        self.assertEqual(payments[0].amount, Decimal("40.00"))
        self.assertEqual(payments[0].tender_desc, "Cash")

        self.assertEqual(payments[1].pcode, self.debit_tender.pcode)
        self.assertEqual(payments[1].amount, Decimal("60.00"))
        self.assertEqual(payments[1].tender_desc, "Debit")
        self.assertEqual(payments[1].payment_reference, "DBT-0002")

        self.assertFalse(TempTransaction.objects.exists())
