import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import POSSession
from .models import (
    Item,
    Payment,
    POSTransNumber,
    SuspendedTransaction,
    Tender,
    TempTransaction,
    TransactionHeader,
    TransactionItem,
)


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


class SuspendRetrieveFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cashier1 = user_model.objects.create_user(
            username="cashier_a",
            password="pass12345",
            role="cashier",
            is_active=True,
        )
        self.cashier2 = user_model.objects.create_user(
            username="cashier_b",
            password="pass12345",
            role="cashier",
            is_active=True,
        )
        self.manager = user_model.objects.create_user(
            username="manager1",
            password="2468",
            role="manager",
            is_active=True,
        )

        POSSession.objects.create(
            cashier=self.cashier1,
            terminal_id="001",
            store_id="001",
            business_date=date.today(),
            opening_cash=Decimal("1000.00"),
            status=POSSession.STATUS_OPEN,
        )
        POSSession.objects.create(
            cashier=self.cashier2,
            terminal_id="001",
            store_id="001",
            business_date=date.today(),
            opening_cash=Decimal("1000.00"),
            status=POSSession.STATUS_OPEN,
        )

        self.item = Item.objects.create(
            icode="ITEM100",
            short_desc="Suspend Test Item",
            price=Decimal("100.00"),
        )
        self.item2 = Item.objects.create(
            icode="ITEM200",
            short_desc="Suspend Test Item 2",
            price=Decimal("50.00"),
        )
        self.cash_tender = Tender.objects.create(
            pcode="P01",
            description="Cash",
            pallow="Y",
            pchange="Y",
        )

    def _login(self, user):
        self.client.force_login(user)

    def _add_item(self, icode, qty="1"):
        return self.client.post(reverse("sales:cart_add"), {"barcode": icode, "qty": qty})

    def _suspend(self):
        return self.client.post(reverse("sales:cart_suspend"))

    def _complete_cash_payment(self, amount):
        return self.client.post(
            reverse("sales:payment_complete"),
            {"tender_entries": json.dumps([{"pcode": self.cash_tender.pcode, "amount": str(amount)}])},
        )

    def test_suspend_unpaid_cart_moves_to_lookup(self):
        self._login(self.cashier1)
        self._add_item(self.item.icode)
        trans_no = self.client.session.get("pos_trans_no")

        response = self._suspend()
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "ok": True,
            "transaction_no": trans_no,
            "item_count": 1,
            "message": f"Transaction {trans_no} suspended",
        })

        self.assertFalse(TempTransaction.objects.filter(transaction_no=trans_no).exists())
        self.assertTrue(SuspendedTransaction.objects.filter(transaction_no=trans_no).exists())

        lookup = self.client.get(reverse("sales:cart_suspended_list"))
        self.assertEqual(lookup.status_code, 200)
        payload = lookup.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(any(row["transaction_no"] == trans_no for row in payload["suspended"]))
        self.assertEqual(payload.get("suspended_count"), 1)

        cashier_page = self.client.get(reverse("sales:pos_cashier"))
        self.assertEqual(cashier_page.status_code, 200)
        self.assertContains(cashier_page, 'id="suspended-count-badge"')
        self.assertContains(cashier_page, '>1<')
    def test_retrieve_from_another_cashier_same_terminal(self):
        self._login(self.cashier1)
        self._add_item(self.item.icode)
        trans_no = self.client.session.get("pos_trans_no")
        self._suspend()

        self.client.logout()
        self._login(self.cashier2)

        response = self.client.post(
            reverse("sales:cart_suspended_retrieve"),
            {"transaction_no": trans_no},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        restored = TempTransaction.objects.filter(user_id=self.cashier2.username[:10], transaction_no=trans_no)
        self.assertEqual(restored.count(), 1)
        self.assertEqual(restored.first().item_code, self.item.icode)
        self.assertFalse(SuspendedTransaction.objects.filter(transaction_no=trans_no).exists())

    def test_reserved_trans_no_restored_and_posnbr_advances_monotonic(self):
        POSTransNumber.objects.create(transaction_no="00000020")

        self._login(self.cashier1)
        self._add_item(self.item.icode)
        suspended_no = self.client.session.get("pos_trans_no")
        self.assertEqual(suspended_no, "00000021")
        self._suspend()

        self._add_item(self.item2.icode)
        newer_no = self.client.session.get("pos_trans_no")
        self.assertEqual(newer_no, "00000022")
        pay_newer = self._complete_cash_payment("50.00")
        self.assertEqual(pay_newer.status_code, 302)

        self.client.logout()
        self._login(self.cashier2)
        restore = self.client.post(reverse("sales:cart_suspended_retrieve"), {"transaction_no": suspended_no})
        self.assertEqual(restore.status_code, 200)
        pay_restored = self._complete_cash_payment("100.00")
        self.assertEqual(pay_restored.status_code, 302)

        restored_header = TransactionHeader.objects.filter(transaction_no=suspended_no, transaction_type="S").first()
        self.assertIsNotNone(restored_header)

        current_posnbr = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(current_posnbr.transaction_no, "00000022")

    def test_suspend_empty_cart_validation_error(self):
        self._login(self.cashier1)
        self.client.get(reverse("sales:pos_cashier"))
        response = self._suspend()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "Cart is empty")

    def test_retrieve_blocked_when_active_cart_exists(self):
        self._login(self.cashier1)
        self._add_item(self.item.icode)
        trans_no = self.client.session.get("pos_trans_no")
        self._suspend()

        self.client.logout()
        self._login(self.cashier2)
        self._add_item(self.item2.icode)

        response = self.client.post(
            reverse("sales:cart_suspended_retrieve"),
            {"transaction_no": trans_no},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("not empty", response.json().get("error", ""))

    def test_repeated_suspend_retrieve_does_not_increment_posnbr_without_new_sale(self):
        POSTransNumber.objects.create(transaction_no="00000010")

        self._login(self.cashier1)
        self._add_item(self.item.icode)
        trans_no = self.client.session.get("pos_trans_no")
        self.assertEqual(trans_no, "00000011")

        first_suspend = self._suspend()
        self.assertEqual(first_suspend.status_code, 200)

        posnbr_after_first = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(posnbr_after_first.transaction_no, "00000011")

        self.client.post(reverse("sales:cart_suspended_retrieve"), {"transaction_no": trans_no})
        second_suspend = self._suspend()
        self.assertEqual(second_suspend.status_code, 200)

        posnbr_after_second = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(posnbr_after_second.transaction_no, "00000011")

    def test_retrieve_older_suspended_trans_does_not_increment_current_posnbr(self):
        POSTransNumber.objects.create(transaction_no="00000022")

        SuspendedTransaction.objects.create(
            user_id=self.cashier1.username[:10],
            terminal_id="001",
            store_id="001",
            transaction_no="00000016",
            transaction_date=date.today(),
            transaction_time="10:00",
            transaction_type="S",
            item_code=self.item.icode,
            item_description="Suspend Test Item",
            item_qty=Decimal("1"),
            item_price=Decimal("100.00"),
            item_price_ext=Decimal("100.00"),
            rec_ctr=Decimal("1"),
        )

        self._login(self.cashier1)
        retrieve = self.client.post(
            reverse("sales:cart_suspended_retrieve"),
            {"transaction_no": "00000016"},
        )
        self.assertEqual(retrieve.status_code, 200)
        self.assertTrue(retrieve.json().get("ok"))

        current_posnbr = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(current_posnbr.transaction_no, "00000022")

        cashier_page = self.client.get(reverse("sales:pos_cashier"))
        self.assertEqual(cashier_page.status_code, 200)
        current_posnbr_after_page = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(current_posnbr_after_page.transaction_no, "00000022")

    def test_two_suspended_retrieve_and_pay_out_of_order_keeps_expected_next_number(self):
        POSTransNumber.objects.create(transaction_no="00000026")

        self._login(self.cashier1)
        self._add_item(self.item.icode)
        t27 = self.client.session.get("pos_trans_no")
        self.assertEqual(t27, "00000027")
        self._suspend()

        self._add_item(self.item2.icode)
        t28 = self.client.session.get("pos_trans_no")
        self.assertEqual(t28, "00000028")
        self._suspend()

        self.client.post(reverse("sales:cart_suspended_retrieve"), {"transaction_no": t27})
        pay_27 = self._complete_cash_payment("100.00")
        self.assertEqual(pay_27.status_code, 302)

        posnbr_after_27 = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(posnbr_after_27.transaction_no, "00000028")

        self.client.post(reverse("sales:cart_suspended_retrieve"), {"transaction_no": t28})
        pay_28 = self._complete_cash_payment("50.00")
        self.assertEqual(pay_28.status_code, 302)

        posnbr_after_28 = POSTransNumber.objects.order_by("id").first()
        self.assertEqual(posnbr_after_28.transaction_no, "00000028")

        self._add_item(self.item.icode)
        next_trans = self.client.session.get("pos_trans_no")
        self.assertEqual(next_trans, "00000029")

    def test_regression_add_remove_line_discount_voids_and_payment_modal(self):
        self._login(self.cashier1)

        add1 = self._add_item(self.item.icode)
        self.assertEqual(add1.status_code, 200)

        line = TempTransaction.objects.get(item_code=self.item.icode)
        disc = self.client.post(
            reverse("sales:cart_line_disc"),
            {"rec_ctr": int(line.rec_ctr), "disc_pct": "10", "disc_type": "REG"},
        )
        self.assertEqual(disc.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.item_discount, Decimal("10.0000"))

        add2 = self._add_item(self.item2.icode)
        self.assertEqual(add2.status_code, 200)
        second = TempTransaction.objects.filter(item_code=self.item2.icode).first()
        remove = self.client.post(reverse("sales:cart_remove"), {"rec_ctr": int(second.rec_ctr)})
        self.assertEqual(remove.status_code, 200)
        self.assertFalse(TempTransaction.objects.filter(item_code=self.item2.icode).exists())

        pay_modal = self.client.get(reverse("sales:pay"))
        self.assertEqual(pay_modal.status_code, 200)

        void_item = self.client.post(reverse("sales:cart_void_item"), {"rec_ctr": int(line.rec_ctr)})
        self.assertEqual(void_item.status_code, 200)
        self.assertTrue(void_item.json().get("ok"))

        self._add_item(self.item.icode)
        paid = self._complete_cash_payment("100.00")
        self.assertEqual(paid.status_code, 302)
        paid_header = TransactionHeader.objects.filter(transaction_type="S").order_by("id").last()
        self.assertIsNotNone(paid_header)

        void_prev = self.client.post(
            reverse("sales:cart_void_previous"),
            {"receipt_no": paid_header.transaction_no, "manager_pin": "2468"},
        )
        self.assertEqual(void_prev.status_code, 200)
        self.assertTrue(void_prev.json().get("ok"))


class TransactionJournalApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="journal_cashier",
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
            opening_cash=Decimal("500.00"),
            status=POSSession.STATUS_OPEN,
        )

        self.today_header = TransactionHeader.objects.create(
            session=self.session,
            user_id=self.user.username[:10],
            terminal_id="001",
            store_id="001",
            transaction_no="00000011",
            transaction_date=date.today(),
            transaction_time="10:15",
            transaction_type="S",
            subtotal=Decimal("100.00"),
            amount_total=Decimal("90.00"),
            amount_tendered=Decimal("100.00"),
            change_amount=Decimal("10.00"),
            trans_disc_label="Promo",
            trans_disc_pct=Decimal("10.00"),
            trans_disc_amount=Decimal("10.00"),
        )
        TransactionItem.objects.create(
            header=self.today_header,
            item_code="SKU-A",
            item_description="Item A",
            item_qty=Decimal("1"),
            item_price=Decimal("100.00"),
            item_price_ext=Decimal("100.00"),
        )
        Payment.objects.create(
            header=self.today_header,
            pcode="P01",
            tender_desc="Cash",
            amount=Decimal("100.00"),
        )

        self.prev_header = TransactionHeader.objects.create(
            session=self.session,
            user_id=self.user.username[:10],
            terminal_id="001",
            store_id="001",
            transaction_no="00000010",
            transaction_date=date.today() - timedelta(days=1),
            transaction_time="09:00",
            transaction_type="S",
            subtotal=Decimal("50.00"),
            amount_total=Decimal("50.00"),
            amount_tendered=Decimal("50.00"),
            change_amount=Decimal("0.00"),
        )
        TransactionItem.objects.create(
            header=self.prev_header,
            item_code="SKU-B",
            item_description="Item B",
            item_qty=Decimal("1"),
            item_price=Decimal("50.00"),
            item_price_ext=Decimal("50.00"),
        )
        Payment.objects.create(
            header=self.prev_header,
            pcode="P01",
            tender_desc="Cash",
            amount=Decimal("50.00"),
        )

    def test_transaction_journal_invalid_date_returns_400(self):
        response = self.client.get(reverse("sales:transaction_journal"), {"from_date": "2026-99-99"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get("ok", True))

    def test_transaction_journal_pagination_and_nested_data(self):
        response = self.client.get(
            reverse("sales:transaction_journal"),
            {
                "from_date": (date.today() - timedelta(days=1)).isoformat(),
                "to_date": date.today().isoformat(),
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(len(payload.get("transactions", [])), 1)
        self.assertTrue(payload.get("has_more"))
        self.assertIsNotNone(payload.get("next_cursor"))

        first = payload["transactions"][0]
        self.assertIn("items", first)
        self.assertIn("payments", first)
        self.assertGreaterEqual(len(first["items"]), 1)
        self.assertGreaterEqual(len(first["payments"]), 1)

        response_page_2 = self.client.get(
            reverse("sales:transaction_journal"),
            {
                "from_date": (date.today() - timedelta(days=1)).isoformat(),
                "to_date": date.today().isoformat(),
                "page_size": 1,
                "cursor": payload["next_cursor"],
            },
        )
        self.assertEqual(response_page_2.status_code, 200)
        payload_page_2 = response_page_2.json()
        self.assertTrue(payload_page_2.get("ok"))
        self.assertEqual(len(payload_page_2.get("transactions", [])), 1)
