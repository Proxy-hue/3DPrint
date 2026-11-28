from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Material, QualityProfile, Technology
from models_app.models import ModelVersion, PrintModel
from orders.models import Order, OrderEvent, OrderPostProcessing, Status
from catalog.models import PostProcessing
from pricing.models import Quote
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
        call_command("loaddata", "initial_catalog", verbosity=0)
        self.owner = User.objects.create_user(
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
            volume_cm3=18.0,
        )
        self.tech = Technology.objects.get(code="FDM")
        self.material = Material.objects.get(name="PLA")
        self.quality = QualityProfile.objects.get(technology=self.tech, name="Стандартное")
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
        self._order_seq = 0

    def tearDown(self):
        for model in PrintModel.objects.all():
            if model.file:
                model.file.delete(save=False)
        super().tearDown()

    def _create_order(
        self,
        *,
        order_status: str = Status.DISTRIBUTED,
        with_post_processing: bool = False,
        attach_model: bool = True,
    ) -> Order:
        self._order_seq += 1
        order = Order.objects.create(
            number=f"3DP-TEST-{self._order_seq:04d}",
            client=self.owner,
            status=order_status,
            technology=self.tech,
            material=self.material,
            quality_profile=self.quality,
            quantity=2,
        )
        if with_post_processing:
            pp = PostProcessing.objects.first()
            if pp is not None:
                OrderPostProcessing.objects.create(order=order, post_processing=pp)
        if attach_model:
            print_model = PrintModel.objects.create(
                owner=self.owner,
                file=SimpleUploadedFile(
                    f"bracket_{self._order_seq}.stl",
                    b"solid bracket\nendsolid bracket\n",
                ),
                original_name="bracket.stl",
                format=PrintModel.Format.STL,
                size=31,
                status=PrintModel.Status.VALIDATED,
                width_mm=60.0,
                height_mm=40.0,
                depth_mm=20.0,
                volume_cm3=18.0,
            )
            ModelVersion.objects.create(
                print_model=print_model,
                order=order,
                version=1,
                file=print_model.file.name,
                file_name=print_model.original_name,
                format=print_model.format,
                size_bytes=print_model.size,
                storage_key=print_model.file.name,
                bbox_x=60.0,
                bbox_y=40.0,
                bbox_z=20.0,
                volume_cm3=18.0,
                is_current=True,
            )
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
        order = self._create_order(order_status=Status.DISTRIBUTED)
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
                {"status": Status.PRINTING},
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
        visible_paid = self._create_order(order_status=Status.PAID)
        visible_printing = self._create_order(order_status=Status.PRINTING)
        hidden_new = self._create_order(order_status=Status.NEW)

        response = self.client.get(
            reverse("integration-order-list"),
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(returned_ids, {str(visible_paid.pk), str(visible_printing.pk)})
        self.assertNotIn(str(hidden_new.pk), returned_ids)

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
        order_with_post = self._create_order(
            order_status=Status.DISTRIBUTED,
            with_post_processing=True,
        )
        status_url = reverse("integration-order-status", args=[order_with_post.pk])

        resp_print = self.client.post(
            status_url,
            {
                "status": Status.PRINTING,
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
        self.assertEqual(resp_print.data["status"], Status.PRINTING)
        self.assertEqual(resp_print.data["actual_data"]["printer_name"], "FDM-01")

        resp_skip = self.client.post(
            status_url,
            {"status": Status.READY},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_skip.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp_skip.data["code"], "INVALID_STATUS_TRANSITION")

        resp_post = self.client.post(
            status_url,
            {"status": Status.POST_PROCESSING},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_post.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_post.data["status"], Status.POST_PROCESSING)

        order_no_post = self._create_order(
            order_status=Status.PRINTING,
            with_post_processing=False,
        )
        resp_ready = self.client.post(
            f"/api/integration/orders/{order_no_post.pk}/status",
            {"status": Status.READY, "actual_print_hours": "2.100"},
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )
        self.assertEqual(resp_ready.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_ready.data["status"], Status.READY)

        facts = IntegrationOrderFacts.objects.get(order=order_with_post)
        self.assertEqual(facts.actual_material_g, Decimal("35.500"))
        self.assertEqual(IntegrationStatusEvent.objects.filter(order=order_with_post).count(), 2)
        self.assertEqual(OrderEvent.objects.filter(order=order_with_post).count(), 2)

    def test_export_orders_events_and_load_in_json_and_csv(self):
        order = self._create_order(order_status=Status.DISTRIBUTED, with_post_processing=False)
        self.client.post(
            reverse("integration-order-status", args=[order.pk]),
            {
                "status": Status.PRINTING,
                "printer_name": "=CMD|calc",
                "actual_material_g": "12.5",
                "actual_print_hours": "1.2",
            },
            format="json",
            HTTP_X_API_KEY=self.engineering_client.raw_api_key,
        )

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

        orders_csv = self.client.get(
            reverse("integration-export-orders") + "?format=csv",
            HTTP_X_API_KEY=self.reporting_client.raw_api_key,
        )
        self.assertEqual(orders_csv.status_code, status.HTTP_200_OK)
        self.assertIn("'=CMD|calc", orders_csv.content.decode("utf-8"))
