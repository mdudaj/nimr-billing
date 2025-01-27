import functools
import logging
import ssl

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_weasyprint.views import WeasyTemplateView

from .forms import (
    BillCancellationForm,
    BillForm,
    BillItemInlineFormSet,
    CustomerForm,
    PaymentReconciliationForm,
    RevenueSourceForm,
    RevenueSourceItemInlineFormSet,
    ServiceProviderBillingDepartmentInlineFormSet,
    ServiceProviderForm,
    SystemInfoForm,
)
from .models import (
    Bill,
    BillingDepartment,
    BillItem,
    CancelledBill,
    Currency,
    Customer,
    ExchangeRate,
    Payment,
    PaymentGatewayLog,
    PaymentReconciliation,
    RevenueSource,
    RevenueSourceItem,
    RevenueSourceItemPriceHistory,
    ServiceProvider,
    SystemInfo,
)
from .tasks import (
    process_bill_control_number_response,
    process_bill_payment_response,
    process_bill_reconciliation_response,
    send_bill_control_number_request,
    send_bill_reconciliation_request,
)
from .utils import (
    compose_acknowledgement_response_payload,
    compose_bill_cancellation_payload,
    compose_bill_cancellation_response_acknowledgement_payload,
    compose_bill_reconciliation_response_acknowledgement_payload,
    compose_payment_response_acknowledgement_payload,
    custom_url_fetcher,
    generate_pdf,
    generate_qr_code,
    generate_request_id,
    load_private_key,
    parse_bill_cancellation_response,
    parse_bill_control_number_response,
    parse_bill_reconciliation_response,
    parse_payment_response,
    xml_to_dict,
)

logger = logging.getLogger(__name__)


class BillingIndexView(LoginRequiredMixin, TemplateView):
    template_name = "billing/index.html"


class CurrencyListView(LoginRequiredMixin, ListView):
    model = Currency
    template_name = "billing/currency/currency_list.html"


class CurrencyDetailView(LoginRequiredMixin, DetailView):
    model = Currency
    template_name = "billing/currency/currency_detail.html"


class CurrencyCreateView(LoginRequiredMixin, CreateView):
    model = Currency
    fields = ["code", "name"]
    template_name = "billing/currency/currency_form.html"
    success_url = reverse_lazy("billing:currency-list")


class CurrencyUpdateView(LoginRequiredMixin, UpdateView):
    model = Currency
    fields = ["code", "name"]
    template_name = "billing/currency/currency_form.html"
    success_url = reverse_lazy("billing:currency-list")


class ExchangeRateListView(LoginRequiredMixin, ListView):
    model = ExchangeRate
    template_name = "billing/exchange_rate/exchange_rate_list.html"


class ExchangeRateCreateView(LoginRequiredMixin, CreateView):
    model = ExchangeRate
    fields = ["currency", "trx_date", "buying", "selling"]
    template_name = "billing/exchange_rate/exchange_rate_form.html"
    success_url = reverse_lazy("billing:exchange-rate-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context


class ExchangeRateUpdateView(LoginRequiredMixin, UpdateView):
    model = ExchangeRate
    fields = ["currency", "trx_date", "buying", "selling"]
    template_name = "billing/exchange_rate/exchange_rate_form.html"
    success_url = reverse_lazy("billing:exchange-rate-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context


class SystemInfoListView(LoginRequiredMixin, ListView):
    model = SystemInfo
    template_name = "billing/system_info/system_info_list.html"


class SystemInfoDetailView(LoginRequiredMixin, DetailView):
    model = SystemInfo
    template_name = "billing/system_info/system_info_detail.html"


class SystemInfoCreateView(LoginRequiredMixin, CreateView):
    model = SystemInfo
    form_class = SystemInfoForm
    template_name = "billing/system_info/system_info_form.html"
    success_url = reverse_lazy("billing:system-info-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


class SystemInfoUpdateView(LoginRequiredMixin, UpdateView):
    model = SystemInfo
    form_class = SystemInfoForm
    template_name = "billing/system_info/system_info_form.html"
    success_url = reverse_lazy("billing:system-info-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


class SystemInfoDeleteView(LoginRequiredMixin, UpdateView):
    model = SystemInfo
    template_name = "billing/system_info/system_info_confirm_delete.html"
    success_url = reverse_lazy("billing:system-info-list")
    fields = ["is_active"]

    def form_valid(self, form):
        form.instance.is_active = False
        return super().form_valid(form)


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = "billing/customer/customer_list.html"


class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = "billing/customer/customer_detail.html"


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer/customer_form.html"
    success_url = reverse_lazy("billing:customer-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer/customer_form.html"
    success_url = reverse_lazy("billing:customer-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


class CustomerDeleteView(LoginRequiredMixin, DeleteView):
    model = Customer
    template_name = "billing/customer/customer_confirm_delete.html"
    success_url = reverse_lazy("billing:customer-list")


class ServiceProviderListView(LoginRequiredMixin, ListView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_list.html"


class ServiceProviderDetailView(LoginRequiredMixin, DetailView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_detail.html"


class ServiceProviderCreateView(LoginRequiredMixin, CreateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = "billing/service_provider/sp_with_departments_form.html"
    success_url = reverse_lazy("billing:sp-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        if self.request.POST:
            context["billing_departments"] = (
                ServiceProviderBillingDepartmentInlineFormSet(self.request.POST)
            )
        else:
            context["billing_departments"] = (
                ServiceProviderBillingDepartmentInlineFormSet()
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        billingdepartment = context["billing_departments"]
        with transaction.atomic():
            self.object = form.save()
            if billingdepartment.is_valid():
                billingdepartment.instance = self.object
                billingdepartment.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["billing_departments"] = context["billing_departments"]
        return self.render_to_response(self.get_context_data(form=form))


class ServiceProviderUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceProvider
    form_class = ServiceProviderForm
    template_name = "billing/service_provider/sp_with_departments_form.html"
    success_url = reverse_lazy("billing:sp-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        if self.request.POST:
            context["billing_departments"] = (
                ServiceProviderBillingDepartmentInlineFormSet(
                    self.request.POST, instance=self.object
                )
            )
        else:
            context["billing_departments"] = (
                ServiceProviderBillingDepartmentInlineFormSet(instance=self.object)
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        billingdepartment = context["billing_departments"]
        with transaction.atomic():
            self.object = form.save()
            if billingdepartment.is_valid():
                billingdepartment.instance = self.object
                billingdepartment.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["billing_departments"] = context["billing_departments"]
        return self.render_to_response(self.get_context_data(form=form))


class ServiceProviderDeleteView(LoginRequiredMixin, DeleteView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_confirm_delete.html"
    success_url = reverse_lazy("billing:sp-list")


class RevenueSourceListView(LoginRequiredMixin, ListView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_list.html"


class RevenueSourceDetailView(LoginRequiredMixin, DetailView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_detail.html"


class RevenueSourceCreateView(LoginRequiredMixin, CreateView):
    model = RevenueSource
    form_class = RevenueSourceForm
    template_name = "billing/revenue_source/rs_with_items_form.html"
    success_url = reverse_lazy("billing:rs-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        if self.request.POST:
            context["revenue_source_items"] = RevenueSourceItemInlineFormSet(
                self.request.POST
            )
        else:
            context["revenue_source_items"] = RevenueSourceItemInlineFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        revenue_source_items = context["revenue_source_items"]
        with transaction.atomic():
            self.object = form.save()
            if revenue_source_items.is_valid():
                revenue_source_items.instance = self.object
                revenue_source_items.save()
                # Create initial price history for each revenue source items
                for item in revenue_source_items:
                    RevenueSourceItemPriceHistory.objects.create(
                        rev_src_itm=item,
                        amt=item.amt,
                        effective_date=timezone.now(),
                    )
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["revenue_source_items"] = context["revenue_source_items"]
        return self.render_to_response(self.get_context_data(form=form))


class RevenueSourceUpdateView(LoginRequiredMixin, UpdateView):
    model = RevenueSource
    form_class = RevenueSourceForm
    template_name = "billing/revenue_source/rs_with_items_form.html"
    success_url = reverse_lazy("billing:rs-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        if self.request.POST:
            context["revenue_source_items"] = RevenueSourceItemInlineFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["revenue_source_items"] = RevenueSourceItemInlineFormSet(
                instance=self.object
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        revenue_source_items = context["revenue_source_items"]
        with transaction.atomic():
            self.object = form.save()
            if revenue_source_items.is_valid():
                revenue_source_items.instance = self.object
                for item_form in revenue_source_items:
                    if item_form.instance.pk:  # Check if the item exists
                        # Check if the amount has changed
                        if item_form.instance.amt != item_form.cleaned_data.get("amt"):
                            # Create a new price history record
                            RevenueSourceItemPriceHistory.objects.create(
                                rev_src_itm=item_form.instance,
                                amt=item_form.cleaned_data.get("amt"),
                                effective_date=timezone.now(),
                            )
                    else:
                        # Create initial price history for new item
                        RevenueSourceItemPriceHistory.objects.create(
                            rev_src_itm=item_form.instance,
                            amt=item_form.cleaned_data.get("amt"),
                            effective_date=timezone.now(),
                        )
                # Save the revenue source items
                revenue_source_items.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["revenue_source_items"] = context["revenue_source_items"]
        return self.render_to_response(self.get_context_data(form=form))


class RevenueSourceDeleteView(LoginRequiredMixin, DeleteView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_confirm_delete.html"
    success_url = reverse_lazy("billing:rs-list")


class BillListView(LoginRequiredMixin, ListView):
    model = Bill
    template_name = "billing/bill/bill_list.html"

    def get_queryset(self):
        # Get all bills first
        queryset = super().get_queryset()

        # Filter the queryset using the is_cancelled() method
        # queryset = queryset.filter(
        #     id__in=[bill.id for bill in queryset if not bill.is_cancelled()]
        # )
        return queryset


class BillDetailView(LoginRequiredMixin, DetailView):
    model = Bill
    template_name = "billing/bill/bill_detail_gepg.html"


class BillCreateView(LoginRequiredMixin, CreateView):
    model = Bill
    form_class = BillForm
    template_name = "billing/bill/bill_with_items_form.html"
    success_url = reverse_lazy("billing:bill-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        if self.request.POST:
            context["bill_items"] = BillItemInlineFormSet(self.request.POST)
        else:
            context["bill_items"] = BillItemInlineFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        bill_items = context["bill_items"]

        # Check if there is at least one valid bill item
        if not bill_items.is_valid() or not any(item.is_valid() for item in bill_items):
            form.add_error(None, "At least one bill item is required.")
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            if bill_items.is_valid():
                bill_items.instance = self.object
                bill_items.save()

                self.object.amt = sum(
                    item.amt for item in self.object.billitem_set.all()
                )
                self.object.eqv_amt = self.object.amt
                self.object.min_amt = self.object.amt
                self.object.max_amt = self.object.amt

                # Save the bill object
                self.object.save()

                # Generate a unique request ID
                req_id = generate_request_id()

                # Send the bill control number request to the GEPG API
                send_bill_control_number_request.delay(req_id, self.object.bill_id)

                # Notify the user that the bill has been successfully created
                messages.success(
                    self.request,
                    (
                        f"Bill {self.object.bill_id} has been successfully created. "
                        f"Please wait for the control number to be generated. "
                        f"Refresh the page to check the status."
                    ),
                )

        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["bill_items"] = context["bill_items"]
        return self.render_to_response(self.get_context_data(form=form))


class BillUpdateView(LoginRequiredMixin, UpdateView):
    model = Bill
    form_class = BillForm
    template_name = "billing/bill/bill_with_items_form.html"
    success_url = reverse_lazy("billing:bill-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        if self.request.POST:
            context["bill_items"] = BillItemInlineFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["bill_items"] = BillItemInlineFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        bill_items = context["bill_items"]

        # Check if there is at least one valid bill item
        if not bill_items.is_valid() or not any(item.is_valid() for item in bill_items):
            form.add_error(None, "At least one bill item is required.")
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            if bill_items.is_valid():
                bill_items.instance = self.object
                bill_items.save()

                self.object.amt = sum(
                    item.amt for item in self.object.billitem_set.all()
                )
                self.object.eqv_amt = self.object.amt
                self.object.min_amt = self.object.amt
                self.object.max_amt = self.object.amt

                # Save the bill object
                self.object.save()

                # Check if cancelled bill exists
                if CancelledBill.objects.filter(bill=self.object).exists():
                    # Update the status of the cancelled bill to recreated
                    CancelledBill.objects.filter(bill=self.object).update(
                        status="RECREATED"
                    )

                # Generate a unique request ID
                req_id = generate_request_id()

                # Send the bill control number request to the GEPG API
                send_bill_control_number_request.delay(req_id, self.object.bill_id)

                # Notify the user that the bill has been successfully updated
                messages.success(
                    self.request,
                    f"Bill {self.object.bill_id} has been successfully updated. New request {req_id} sent.",
                )

        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["bill_items"] = context["bill_items"]
        return self.render_to_response(self.get_context_data(form=form))


class BillDeleteView(LoginRequiredMixin, DeleteView):
    model = Bill
    template_name = "billing/bill/bill_confirm_delete.html"
    success_url = reverse_lazy("billing:bill-list")


class BillCancellationView(LoginRequiredMixin, View):
    template_name = "billing/bill/bill_cancellation_form.html"

    def get(self, request, pk):
        obj = get_object_or_404(Bill, pk=pk)
        form = BillCancellationForm(initial={"bill": obj})
        return render(request, self.template_name, {"form": form, "object": obj})

    def post(self, request, pk):
        obj = get_object_or_404(Bill, pk=pk)
        form = BillCancellationForm(request.POST)
        if form.is_valid():
            cancl_bill_obj = form.save(commit=False)
            cancl_bill_obj.bill = obj
            cancl_bill_obj.cust_cntr_num = obj.cntr_num
            cancl_bill_obj.gen_by = request.user
            cancl_bill_obj.appr_by = request.user
            cancl_bill_obj.save()

            # Generate a unique request ID
            req_id = generate_request_id()

            url = settings.BILL_CANCELATION_URL

            headers = {
                "Content-Type": "application/xml",
                "Gepg-Com": settings.GEPG_COM,
                "Gepg-Code": settings.GEPG_CODE,
                "Gepg-Alg": settings.GEPG_ALG,
            }

            # Try to load the private key and handle potential errors
            try:
                private_key = load_private_key(
                    settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
                )
            except Exception as e:
                logger.error(f"Failed to load private key: {e}")
                messages.error(request, "Internal error occurred. Please try again.")
                return redirect("billing:bill-list")

            # Compose the bill cancellation payload
            payload = compose_bill_cancellation_payload(
                req_id,
                cancl_bill_obj,
                settings.SP_GRP_CODE,
                settings.SP_SYS_ID,
                private_key,
            )

            # Log the bill cancellation request
            pg_log = PaymentGatewayLog.objects.create(
                bill=cancl_bill_obj.bill,
                req_id=req_id,
                req_type="7",
                req_data=payload,
            )

            # Send the bill cancellation request to the GEPG API and handle potential errors
            try:
                response = requests.post(url, data=payload, headers=headers)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                pg_log.status = "ERROR"
                pg_log.status_desc = f"Failed to send bill cancellation request: {e}"
                pg_log.save()
                logger.error(f"Failed to send bill cancellation request: {e}")
                messages.error(request, "Internal error occurred. Please try again.")
                return redirect("billing:bill-list")

            # Parse the response data and handle potential errors
            try:
                res_id, req_id, bill_id, res_sts_code, res_sts_desc = (
                    parse_bill_cancellation_response(response.text)
                )
            except Exception as e:
                pg_log.status = "ERROR"
                pg_log.status_desc = f"Failed to parse bill cancellation response: {e}"
                pg_log.save()

                logger.error(f"Failed to parse bill cancellation response: {e}")
                messages.error(request, "Internal error occurred. Please try again.")
                return redirect("billing:bill-list")


class PaymentReconciliationListView(LoginRequiredMixin, ListView):
    model = PaymentReconciliation
    template_name = "billing/payment_reconciliation/payment_reconciliation_list.html"


class PaymentReconciliationDetailView(LoginRequiredMixin, DetailView):
    model = PaymentReconciliation
    template_name = "billing/payment_reconciliation/payment_reconciliation_detail.html"


class PaymentReconciliationCreateView(LoginRequiredMixin, CreateView):
    model = PaymentReconciliation
    form_class = PaymentReconciliationForm
    template_name = "billing/payment_reconciliation/payment_reconciliation_form.html"
    success_url = reverse_lazy("billing:payment-reconciliation-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        trx_date = form.cleaned_data.get("trx_date").strftime("%Y-%m-%d")

        # Generate a unique request ID
        req_id = generate_request_id()

        # Send the bill reconciliation request to the GEPG API asynchronously
        send_bill_reconciliation_request.delay(
            req_id, settings.SP_GRP_CODE, settings.SP_SYS_ID, trx_date
        )

        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


@method_decorator(csrf_exempt, name="dispatch")
class BillControlNumberResponseCallbackView(View):
    def dispatch(self, *args, **kwargs):
        logger.info("CSRF exempt applied to controll number response callback request")
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Log the incoming request
        # Process the bill control number response received from the GEPG API
        # Extract the response data and call the process_final_response task
        # Return an HTTP response based on the processing outcome

        try:
            # Extract the response data
            response_data = request.body.decode("utf-8")

            # Log the incoming request
            logger.info(f"Received callback request with data: {response_data}")

            # Parse the response data
            (
                res_id,
                req_id,
                bill_id,
                cust_cntr_num,
                res_sts_code,
                res_sts_desc,
                bill_sts_code,
                bill_sts_desc,
            ) = parse_bill_control_number_response(response_data)

            # Update the payment gateway log with the response data
            pg_log = PaymentGatewayLog.objects.get(req_id=req_id)
            pg_log.res_data = xml_to_dict(response_data)

            # Compose an acknowledgement response payload
            private_key = load_private_key(
                settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
            )
            ack_payload = compose_acknowledgement_response_payload(
                ack_id=req_id,
                res_id=res_id,
                ack_sts_code=res_sts_code,
                private_key=private_key,
            )

            # Process the final response data asynchronously
            logger.info(f"Schedule processing of response data: {response_data}")
            process_bill_control_number_response.delay(
                res_id,
                req_id,
                bill_id,
                cust_cntr_num,
                res_sts_code,
                res_sts_desc,
                bill_sts_code,
                bill_sts_desc,
            )

            # Log the acknowledgement payload
            logger.info(f"Acknowledgement payload: {ack_payload}")

            # Update the payment gateway log with the acknowledgement payload
            pg_log.res_ack = xml_to_dict(ack_payload)

            # Return an HTTP response with the acknowledgement payload
            return HttpResponse(ack_payload, content_type="text/xml", status=200)
        except Exception as e:
            # Log the error
            logger.error(f"An error occurred: {str(e)}")

            # Return an HTTP response
            return HttpResponseRedirect("ERROR", status=500)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class BillControlNumberPaymentCallbackView(View):
    def dispatch(self, *args, **kwargs):
        logger.info(
            "CSRF exempt applied to bill control number payment response callback request"
        )
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        pg_log = None  # Initialize pg_log as None

        try:
            # Extract and log the bill payment information
            response_data = request.body.decode("utf-8")
            logger.info(f"Received payment callback request with data: {response_data}")

            # Parse the bill payment information
            try:
                parsed_response = parse_payment_response(response_data)
            except Exception as e:
                logger.error(f"Failed to parse payment response: {e}")
                return HttpResponse(
                    "Invalid payment response", content_type="text/plain", status=400
                )

            (
                req_id,
                bill_id,
                cntr_num,
                psp_code,
                psp_name,
                trx_id,
                payref_id,
                bill_amt,
                paid_amt,
                paid_ccy,
                coll_acc_num,
                trx_date,
                pay_channel,
                trdpty_trx_id,
                pyr_cell_num,
                pyr_email,
                pyr_name,
            ) = parsed_response

            # Get Bill and create Payment Gateway Log
            try:
                bill = Bill.objects.get(bill_id=bill_id)
            except Bill.DoesNotExist:
                logger.error(f"Bill with bill_id {bill_id} does not exist.")
                return HttpResponse(
                    "Bill not found", content_type="text/plain", status=404
                )
            except Bill.MultipleObjectsReturned:
                logger.error(f"Multiple bills found for bill_id {bill_id}.")
                return HttpResponse(
                    "Multiple bills found", content_type="text/plain", status=400
                )

            pg_log, created = PaymentGatewayLog.objects.get_or_create(
                sys_info=bill.sys_info,
                bill=bill,
                req_id=req_id,
                req_type="5",
                status="PENDING",
                status_desc="Payment response received. Processing...",
                defaults={"req_data": xml_to_dict(response_data)},
            )

            if not created:
                logger.info(
                    f"PaymentGatewayLog entry for req_id {req_id} already exists."
                )

            # Generate and log the acknowledgement payload
            try:
                ack_id = generate_request_id()
                private_key = load_private_key(
                    settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
                )
                ack_payload = compose_payment_response_acknowledgement_payload(
                    ack_id=ack_id,
                    req_id=req_id,
                    ack_sts_code="7101",
                    private_key=private_key,
                )
            except Exception as e:
                logger.error(f"Failed to generate acknowledgement payload: {e}")
                return HttpResponse(
                    "Error generating acknowledgement",
                    content_type="text/plain",
                    status=500,
                )

            # Process the bill payment asynchronously
            logger.info(
                f"Scheduling request {req_id} - {bill_id} for payment processing"
            )
            process_bill_payment_response.delay(
                req_id,
                bill_id,
                cntr_num,
                psp_code,
                psp_name,
                trx_id,
                payref_id,
                bill_amt,
                paid_amt,
                paid_ccy,
                coll_acc_num,
                trx_date,
                pay_channel,
                trdpty_trx_id,
                pyr_cell_num,
                pyr_email,
                pyr_name,
            )

            # Log and update the payment gateway log with acknowledgement payload
            logger.info(f"Sending acknowledgement payload: {ack_payload}")
            pg_log.req_ack = xml_to_dict(ack_payload)
            pg_log.save()

            # Return an HTTP response with the acknowledgement payload
            return HttpResponse(ack_payload, content_type="text/xml", status=200)

        except Exception as e:
            logger.error(f"An error occurred while processing payment callback: {e}")

            if pg_log:
                pg_log.status = "ERROR"
                pg_log.status_desc = f"Failed to process payment response: {e}"
                pg_log.save()

            # Return a 500 error response
            return HttpResponse("ERROR", content_type="text/plain", status=500)


@method_decorator(csrf_exempt, name="dispatch")
class BillControlNumberReconciliationCallbackView(View):
    def dispatch(self, *args, **kwargs):
        logger.info(
            "CSRF exempt applied to bill controll number reconciliation response callback request"
        )
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Process the bill reconciliation information received from the GEPG API

        try:
            # Extract the bill reconciliation information from the response data
            response_data = request.body.decode("utf-8")

            print(response_data)

            # Log the incoming request data
            logger.info(
                f"Received reconciliation callback request with data: {response_data}"
            )

            # Parse the bill reconciliation information
            (
                res_id,
                req_id,
                pay_sts_code,
                pay_sts_desc,
                pmt_trx_dtls,
            ) = parse_bill_reconciliation_response(response_data)

            # Update the payment gateway log with the response data
            pg_log = PaymentGatewayLog.objects.get(req_id=req_id)
            pg_log.res_data = xml_to_dict(response_data)

            # Process the bill reconciliation information asynchronously
            logger.info(
                f"Schedule processing of reconciliation response data: {response_data}"
            )
            process_bill_reconciliation_response.delay(
                res_id,
                req_id,
                pay_sts_code,
                pay_sts_desc,
                pmt_trx_dtls,
            )

            # Compose an acknowledgement response payload
            private_key = load_private_key(
                settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
            )
            ack_payload = compose_bill_reconciliation_response_acknowledgement_payload(
                ack_id=req_id,
                res_id=res_id,
                ack_sts_code=7101,
                private_key=private_key,
            )

            # Log the acknowledgement payload
            logger.info(f"Acknowledgement payload: {ack_payload}")

            # Update the payment gateway log with the acknowledgement payload
            pg_log.res_ack = xml_to_dict(ack_payload)

            # Return an HTTP response with the acknowledgement payload
            return HttpResponse(ack_payload, content_type="text/xml", status=200)
        except Exception as e:
            # Log the error
            logger.error(f"An error occurred: {str(e)}")

            # Return an HTTP response
            return HttpResponseRedirect(f"ERROR {str(e)}", status=500)


class BillCancellationCreateView(LoginRequiredMixin, CreateView):
    model = CancelledBill
    fields = ["bill", "reason"]
    template_name = "billing/bill_cancellation/bill_cancellation_form.html"
    success_url = reverse_lazy("billing:bill-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context

    @transaction.atomic
    def form_valid(self, form):
        print(
            f"User: {self.request.user} | Authenticated: {self.request.user.is_authenticated}"
        )

        context = self.get_context_data()
        cancl_bill_obj = form.save(commit=False)
        cancl_bill_obj.cust_cntr_num = cancl_bill_obj.bill.cntr_num
        cancl_bill_obj.gen_by = self.request.user
        cancl_bill_obj.appr_by = self.request.user
        cancl_bill_obj.save()

        # Generate a unique request ID
        req_id = generate_request_id()

        url = settings.BILL_CANCELATION_URL

        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Try to load the private key and handle potential errors
        try:
            private_key = load_private_key(
                settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
            )
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        # Compose the bill cancellation payload
        payload = compose_bill_cancellation_payload(
            req_id,
            cancl_bill_obj,
            settings.SP_GRP_CODE,
            settings.SP_SYS_ID,
            private_key,
        )

        # Log the bill cancellation request
        pg_log = PaymentGatewayLog.objects.create(
            bill=cancl_bill_obj.bill,
            req_id=req_id,
            req_type="7",
            req_data=payload,
        )

        # Send the bill cancellation request to the GEPG API and handle potential errors
        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            pg_log.status = "ERROR"
            pg_log.status_desc = f"Failed to send bill cancellation request: {e}"
            pg_log.save()
            logger.error(f"Failed to send bill cancellation request: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        # Parse the response data and handle potential errors
        try:
            res_id, req_id, bill_id, res_sts_code, res_sts_desc = (
                parse_bill_cancellation_response(response.text)
            )
        except Exception as e:
            pg_log.status = "ERROR"
            pg_log.status_desc = f"Failed to parse bill cancellation response: {e}"
            pg_log.save()
            logger.error(f"Failed to parse bill cancellation response: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        if res_sts_code == "7283":
            # Update the status of the bill to cancelled, and clear the control number
            cancl_bill_obj.status = "CANCELLED"
            cancl_bill_obj.save()

            Bill.objects.filter(bill_id=cancl_bill_obj.bill.bill_id).update(
                cntr_num=None
            )

            # Update the status of the payment gateway log
            pg_log.status = "SUCCESS"
            pg_log.status_desc = res_sts_desc
            pg_log.res_data = xml_to_dict(response.text)
            pg_log.save()
            messages.success(
                self.request,
                f"Bill {cancl_bill_obj.bill.bill_id} has been successfully cancelled.",
            )

            # Compose an acknowledgement response payload
            ack_payload = compose_bill_cancellation_response_acknowledgement_payload(
                ack_id=req_id,
                res_id=res_id,
                ack_sts_code="7101",
                private_key=private_key,
            )

            # Log the acknowledgement payload
            pg_log.res_ack = xml_to_dict(ack_payload)
            pg_log.save()

            try:
                requests.post(
                    url, data=ack_payload, headers={"Content-Type": "application/xml"}
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send acknowledgement: {e}")
                messages.error(
                    self.request,
                    f"Failed to send acknowledgement for bill {cancl_bill_obj.bill.bill_id}: {e}",
                )
                return redirect(self.success_url)
        else:
            pg_log.status = "ERROR"
            pg_log.status_desc = res_sts_desc
            pg_log.res_data = xml_to_dict(response.text)
            pg_log.save()
            messages.error(
                self.request,
                f"Failed to cancel bill {cancl_bill_obj.bill.bill_id}: {res_sts_desc}",
            )

        return super().form_valid(form)

    def form_invalid(self, form):
        # Log invalid form data to see the validation errors
        logger.error(f"Form errors: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return self.render_to_response(self.get_context_data(form=form))


class BillCancellationUpdateView(LoginRequiredMixin, UpdateView):
    model = CancelledBill
    fields = ["bill", "reason"]
    template_name = "billing/bill_cancellation/bill_cancellation_form.html"
    success_url = reverse_lazy("billing:bill-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        cancl_bill_obj = form.save(commit=False)
        cancl_bill_obj.gen_by = self.request.user
        cancl_bill_obj.appr_by = self.request.user
        cancl_bill_obj.save()

        # Generate a unique request ID
        req_id = generate_request_id()

        url = settings.BILL_CANCELATION_URL

        headers = {
            "Content-Type": "application/xml",
            "Gepg-Com": settings.GEPG_COM,
            "Gepg-Code": settings.GEPG_CODE,
            "Gepg-Alg": settings.GEPG_ALG,
        }

        # Try to load the private key and handle potential errors
        try:
            private_key = load_private_key(
                settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEY_PASSWORD
            )
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        # Compose the bill cancellation payload
        payload = compose_bill_cancellation_payload(
            req_id,
            cancl_bill_obj,
            settings.SP_GRP_CODE,
            settings.SP_SYS_ID,
            private_key,
        )

        # Log the bill cancellation request
        pg_log = PaymentGatewayLog.objects.create(
            bill=cancl_bill_obj.bill,
            req_id=req_id,
            req_type="7",
            req_data=payload,
        )

        # Send the bill cancellation request to the GEPG API and handle potential errors
        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            pg_log.status = "ERROR"
            pg_log.status_desc = f"Failed to send bill cancellation request: {e}"
            pg_log.save()
            logger.error(f"Failed to send bill cancellation request: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        # Parse the response data and handle potential errors
        try:
            res_id, req_id, bill_id, res_sts_code, res_sts_desc = (
                parse_bill_cancellation_response(response.text)
            )
        except Exception as e:
            pg_log.status = "ERROR"
            pg_log.status_desc = f"Failed to parse bill cancellation response: {e}"
            pg_log.save()
            logger.error(f"Failed to parse bill cancellation response: {e}")
            messages.error(self.request, "Internal error occurred. Please try again.")
            return redirect(self.success_url)

        if res_sts_code == "7283":
            # Update the status of the bill to cancelled, and clear the control number
            cancl_bill_obj.status = "CANCELLED"
            cancl_bill_obj.save()

            Bill.objects.filter(bill_id=cancl_bill_obj.bill.bill_id).update(
                cntr_num=None
            )

            # Update the status of the payment gateway log
            pg_log.status = "SUCCESS"
            pg_log.status_desc = res_sts_desc
            pg_log.res_data = xml_to_dict(response.text)
            pg_log.save()
            messages.success(
                self.request,
                f"Bill {cancl_bill_obj.bill.bill_id} has been successfully cancelled.",
            )

            # Compose an acknowledgement response payload
            ack_payload = compose_bill_cancellation_response_acknowledgement_payload(
                ack_id=req_id,
                res_id=res_id,
                ack_sts_code="7101",
                private_key=private_key,
            )

            # Log the acknowledgement payload
            pg_log.res_ack = xml_to_dict(ack_payload)
            pg_log.save()

            try:
                requests.post(
                    url, data=ack_payload, headers={"Content-Type": "application/xml"}
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send acknowledgement: {e}")
                messages.error(
                    self.request,
                    f"Failed to send acknowledgement for bill {cancl_bill_obj.bill.bill_id}: {e}",
                )
                return redirect(self.success_url)
        else:
            pg_log.status = "ERROR"
            pg_log.status_desc = res_sts_desc
            pg_log.res_data = xml_to_dict(response.text)
            pg_log.save()
            messages.error(
                self.request,
                f"Failed to cancel bill {cancl_bill_obj.bill.bill_id}: {res_sts_desc}",
            )

        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        return self.render_to_response(self.get_context_data(form=form))


class BillCancellationListView(LoginRequiredMixin, ListView):
    model = CancelledBill
    template_name = "billing/bill_cancellation/bill_cancellation_list.html"
    context_object_name = "cancelled_bills"


class BillCancellationDetailView(LoginRequiredMixin, DetailView):
    model = CancelledBill
    template_name = "billing/bill_cancellation/bill_cancellation_detail.html"


class BillCancellationDeleteView(LoginRequiredMixin, DeleteView):
    model = CancelledBill
    template_name = "billing/bill_cancellation/bill_cancellation_confirm_delete.html"
    success_url = reverse_lazy("billing:bill-cancellation-list")


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = "billing/payment/payment_list.html"


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = "billing/payment/payment_detail.html"


def check_control_number_request_status(request, pk):
    """Check the status of a bill control number request."""

    bill = get_object_or_404(Bill, id=pk)
    try:
        # Fetch the latest log entry for this bill
        log = PaymentGatewayLog.objects.filter(bill=bill, req_type="1").latest(
            "created_at"
        )

        # If log does not exist
        if not log:
            return JsonResponse(
                {"status": "NOT_FOUND", "message": "No record found for this bill."},
                status=404,
            )

        # Handle log status conditions
        if log.status == "ERROR":
            return JsonResponse({"status": "ERROR", "message": log.status_desc})
        elif log.status == "SUCCESS":
            return JsonResponse(
                {
                    "status": log.status,
                    "message": log.status_desc,
                    "control_number": bill.cntr_num,
                }
            )
        else:
            return JsonResponse({"status": log.status, "message": log.status_desc})

    except ObjectDoesNotExist as e:
        logger.error(f"No log found for bill_id {bill.bill_id}: {str(e)}")
        return JsonResponse(
            {"status": "NOT_FOUND", "message": "No record found for this bill."},
            status=404,
        )

    except Exception as e:
        # Catch all other exceptions
        logger.error(
            f"Error fetching control number request status for bill_id {bill.bill_id}: {str(e)}"
        )
        return JsonResponse(
            {"status": "ERROR", "message": "Internal server error"}, status=500
        )


class BillPrintPDFView(WeasyTemplateView):
    template_name = "billing/printout/bill_print_pdf.html"
    pdf_stylesheets = [
        # settings.STATIC_ROOT + "/semantic-ui/semantic.min.css",
        settings.STATIC_ROOT
        + "/css/bill_print.css",
    ]
    pdf_attachment = True

    # Genaration date
    print_date = timezone.now().strftime("%d-%m-%Y")

    def get_url_fetcher(self):
        # Disable host and certificate verification
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Return a partial function with modified SSL context
        return functools.partial(custom_url_fetcher, ssl_context=context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the bill and generate the PDF filename dynamically using the bill_id
        bill = self.get_bill()
        logo_path = staticfiles_storage.path("img/coat-of-arms-of-tanzania.png")
        qr_code_path = generate_qr_code(
            {
                "opType": "2",
                "shortCode": "001001",
                "billReference": bill.cntr_num,
                "amount": bill.amt,
                "billCcy": bill.currency,
                "billExprDt": bill.expr_date.strftime("%Y-%m-%d"),
                "billPayOpt": bill.pay_opt,
                "billRsv01": f"National Institute for Medical Research|{bill.customer.get_name}",
            },
            logo_path=logo_path,
        )
        context["image_path"] = logo_path
        context["qr_code_path"] = qr_code_path
        context["bill"] = self.get_bill()
        context["print_date"] = self.print_date
        print(qr_code_path)
        return context

    def get_bill(self):
        return Bill.objects.get(pk=self.kwargs["pk"])

    def get_pdf_filename(self):
        # Get the bill and generate the PDF filename dynamically using the bill_id
        bill = self.get_bill()
        return f"{bill.bill_id}.pdf"


class BillTransferPrintPDFView(WeasyTemplateView):
    template_name = "billing/printout/bill_transfer_print_pdf.html"
    pdf_stylesheets = [
        # settings.STATIC_ROOT + "/semantic-ui/semantic.min.css",
        settings.STATIC_ROOT
        + "/css/bill_transfer_print.css",
    ]
    pdf_attachment = True

    # Genaration date
    print_date = timezone.now().strftime("%d-%m-%Y")

    def get_url_fetcher(self):
        # Disable host and certificate verification
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Return a partial function with modified SSL context
        return functools.partial(custom_url_fetcher, ssl_context=context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the bill and generate the PDF filename dynamically using the bill_id
        bill = self.get_bill()
        logo_path = staticfiles_storage.path("img/coat-of-arms-of-tanzania.png")
        qr_code_path = generate_qr_code(
            {
                "opType": "2",
                "shortCode": "001001",
                "billReference": bill.cntr_num,
                "amount": bill.amt,
                "billCcy": bill.currency,
                "billExprDt": bill.expr_date.strftime("%Y-%m-%d"),
                "billPayOpt": bill.pay_opt,
                "billRsv01": f"National Institute for Medical Research|{bill.customer.get_name}",
            },
            logo_path=logo_path,
        )
        context["image_path"] = logo_path
        context["qr_code_path"] = qr_code_path
        context["bill"] = self.get_bill()
        context["print_date"] = self.print_date
        return context

    def get_bill(self):
        return Bill.objects.get(pk=self.kwargs["pk"])

    def get_pdf_filename(self):
        # Get the bill transfer and generate the PDF filename dynamically using the transfer_id
        bill = self.get_bill()
        return f"{bill.bill_id}_Transfer.pdf"


class BillReceiptPrintPDFView(LoginRequiredMixin, WeasyTemplateView):
    template_name = "billing/printout/bill_receipt_print_pdf.html"
    pdf_stylesheets = [
        # settings.STATIC_ROOT + "/semantic-ui/semantic.min.css",
        settings.STATIC_ROOT
        + "/css/bill_receipt_print.css",
    ]
    pdf_attachment = True

    def get_url_fetcher(self):
        # Disable host and certificate verification
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Return a partial function with modified SSL context
        return functools.partial(custom_url_fetcher, ssl_context=context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logo_path = staticfiles_storage.path("img/coat-of-arms-of-tanzania.png")
        context["image_path"] = logo_path
        context["bill_rcpt"] = self.get_payment()
        return context

    def get_payment(self):
        bill = Bill.objects.get(pk=self.kwargs["pk"])
        return Payment.objects.get(bill=bill)

    def get_pdf_filename(self):
        # Get the payment and generate the PDF filename dynamically using the payment_id
        rcpt = self.get_payment()
        return f"{rcpt.bill.bill_id}_Receipt.pdf"
