from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from models.models import Order, PrintModel
from users.models import User

from .api import (
    issue_api_client,
    revoke_api_client,
    rotate_api_client_key,
)
from .contracts import ENGINEERING_READ, ENGINEERING_WRITE, EXPORT_READ
from .models import ApiClient, IntegrationOrderFacts, IntegrationStatusEvent


class IntegrationAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="client-user",
            email="client@example.com",
            password="Strong-pass-123",
            role=User.Role.CLIENT,
        )
        self.model = PrintModel.objects.create(
            owner=self.owner,
            file=SimpleUploadedFile("bracket.stl", b"solid bracket\nendsolid bracket\n"),
            original_name="bracket.stl",
            format=PrintModel.Format.STL,
            size=31,
            status=PrintModel.Status.VALIDATED,
            width_mm=60.0,
            height_mm=40.0,
            depth_mm=20.0,
        )
        self.engineering_client = issue_api_client(
            "Engineering Module",
            (ENGINEERING_READ, ENGINEERING_WRITE),
        )
        self.readonly_eng_client = issue_api_client(
            "Engineering Reader",
            (ENGINEERING_READ,),
        )
        self.reporting_client = issue_api_client(
            "Reporting Module",
            (EXPORT_READ,),
        )

    def tearDown(self):
        for model in PrintModel.objects.all():
            if model.file:
                model.file.delete(save=False)
        super().tearDown()

    def _create_order(
        self,
        *,
        order_status: str = "DISTRIBUTED",
        post_processing: str = "none",
        printer_name: str = "",
    ) -> Order:
        order = Order.objects.create(
            owner=self.owner,
            model=self.model,
            status=order_status,
            configuration={
                "technology": "FDM",
                "material": "pla",
                "postProcessing": post_processing,
                "quantity": 2,
            },
            price={
                "total": 1628,
                "leadTimeDays": 4,
                "estimatedWeight": 34.7,
                "printHours": 1.87,
            },
        )
        if printer_name:
            IntegrationOrderFacts.objects.create(order=order, printer_name=printer_name)
        return order

    def test_api_key_is_stored_hashed_and_supports_rotation_and_revocation(self):
        stored = ApiClient.objects.get(pk=self.engineering_client.client_id)
        self.assertNotEqual(stored.api_key_hash, self.engineering_client.raw_api_key)
        self.assertTrue(self.engineering_client.raw_api_key.startswith("3dp_"))

        url = reverse("integration-order-list")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get(url, HTTP_X_API_KEY="invalid-key").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(url, HTTP_X_API_KEY=self.engineering_client.raw_api_key).status_code,
            status.HTTP_200_OK,
        )

        rotated = rotate_api_client_key(self.engineering_client.client_id)
        self.assertEqual(
            self.client.get(url, HTTP_X_API_KEY=self.engineering_client.raw_api_key).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(url, HTTP_X_API_KEY=rotated.raw_api_key).status_code,
            status.HTTP_200_OK,
        )

        revoke_api_client(self.engineering_client.client_id)
        self.assertEqual(
            self.client.get(url, HTTP_X_API_KEY=rotated.raw_api_key).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_scopes_restrict_endpoints(self):
        order = self._create_order(order_status="DISTRIBUTED")
        orders_url = reverse("integration-order-list")
        status_url = reverse("integration-order-status", args=[order.pk])
        export_url = reverse("integration-export-orders")

        self.assertEqual(
            self.client.get(orders_url, HTTP_X_API_KEY=self.reporting_client.raw_api_key).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                status_url,
                {"status": "PRINTING"},
                format="json",
                HTTP_X_API_KEY=self.readonly_eng_client.raw_api_key,
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get(
                export_url,
                HTTP_X_API_KEY=self.engineering_client.raw_api_key,
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_engineering_orders_returns_paid_to_ready_and_model_download(self):
        visible_paid = self._create_order(order_status="PAID")
        visible_printing = self._create_order(order_status="In Production")
        hidden_new = self._create_order(order_status="NEW")
        hidden_pending = self._create_order(order_status="Pending")

        response = self.client.get(
            reverse("integration-order-list"),
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(returned_ids, {visible_paid.pk, visible_printing.pk})
        self.assertNotIn(hidden_new.pk, returned_ids)
        self.assertNotIn(hidden_pending.pk, returned_ids)

        download_ok = self.client.get(
            reverse("integration-order-model", args=[visible_paid.pk]),
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(download_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(download_ok.streaming_content), b"solid bracket\nendsolid bracket\n")
        download_ok.close()

        download_hidden = self.client.get(
            reverse("integration-order-model", args=[hidden_new.pk]),
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(download_hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_engineering_status_transitions_and_facts_recording(self):
        order_with_post = self._create_order(order_status="DISTRIBUTED", post_processing="sanding")
        status_url = reverse("integration-order-status", args=[order_with_post.pk])

        # DISTRIBUTED -> PRINTING + factual metrics
        resp_print = self.client.post(
            status_url,
            {
                "status": "PRINTING",
                "printer_name": "FDM-01",
                "actual_material_name": "PLA White",
                "actual_material_g": "35.500",
                "actual_print_hours": "1.950",
                "reason": "Запущено задание на печать",
            },
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_print.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_print.data["status"], "PRINTING")
        self.assertEqual(resp_print.data["actual_data"]["printer_name"], "FDM-01")
        self.assertEqual(resp_print.data["actual_data"]["actual_material_g"], 35.5)

        # Cannot skip POST_PROCESSING when postProcessing is selected
        resp_skip = self.client.post(
            status_url,
            {"status": "READY"},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_skip.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp_skip.data["code"], "INVALID_STATUS_TRANSITION")

        # PRINTING -> POST_PROCESSING succeeds
        resp_post = self.client.post(
            status_url,
            {"status": "POST_PROCESSING"},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_post.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_post.data["status"], "POST_PROCESSING")

        # Order without post-processing goes PRINTING -> READY directly
        order_no_post = self._create_order(order_status="PRINTING", post_processing="none")
        resp_ready = self.client.post(
            f"/api/integration/orders/{order_no_post.pk}/status",
            {"status": "READY", "actual_print_hours": "2.100"},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_ready.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_ready.data["status"], "READY")

        facts = IntegrationOrderFacts.objects.get(order=order_with_post)
        self.assertEqual(facts.actual_material_g, Decimal("35.500"))
        self.assertEqual(IntegrationStatusEvent.objects.filter(order=order_with_post).count(), 2)

    def test_invalid_transition_from_paid_to_ready_is_rejected(self):
        order = self._create_order(order_status="PAID")
        response = self.client.post(
            reverse("integration-order-status", args=[order.pk]),
            {"status": "READY"},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "INVALID_STATUS_TRANSITION")

    def test_export_orders_events_and_load_in_json_and_csv(self):
        order = self._create_order(order_status="DISTRIBUTED", post_processing="none")
        self.client.post(
            reverse("integration-order-status", args=[order.pk]),
            {
                "status": "PRINTING",
                "printer_name": "=CMD|calc",
                "actual_material_g": "12.5",
                "actual_print_hours": "1.2",
            },
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )

        # JSON exports
        orders_json = self.client.get(
            reverse("integration-export-orders"),
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(orders_json.status_code, status.HTTP_200_OK)
        self.assertEqual(orders_json.data["count"], 1)

        events_json = self.client.get(
            reverse("integration-export-events"),
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(events_json.status_code, status.HTTP_200_OK)
        self.assertEqual(events_json.data["count"], 1)

        load_json = self.client.get(
            reverse("integration-export-load"),
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(load_json.status_code, status.HTTP_200_OK)
        self.assertEqual(load_json.data["count"], 1)
        self.assertEqual(load_json.data["results"][0]["actual_print_hours"], 1.2)

        # CSV export + formula sanitization
        orders_csv = self.client.get(
            reverse("integration-export-orders") + "?format=csv",
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(orders_csv.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", orders_csv["Content-Type"])
        csv_text = orders_csv.content.decode("utf-8")
        self.assertIn("'=CMD|calc", csv_text)

        events_csv = self.client.get(
            reverse("integration-export-events") + "?format=csv",
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(events_csv.status_code, status.HTTP_200_OK)
        self.assertIn("STATUS_CHANGED", events_csv.content.decode("utf-8"))

        load_csv = self.client.get(
            reverse("integration-export-load") + "?format=csv",
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(load_csv.status_code, status.HTTP_200_OK)
        self.assertIn("load_percent", load_csv.content.decode("utf-8"))
