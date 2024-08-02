import logging
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
    ListView,
    DetailView,
)
from django.shortcuts import render


from .models import (
    Customer,
    ServiceProvider,
    BillingDepartment,
    RevenueSource,
    RevenueSourceItem,
    Bill,
    BillItem,
    PaymentGatewayLog,
    SystemInfo,
)
from .forms import (
    CustomerForm,
    ServiceProviderForm,
    ServiceProviderBillingDepartmentInlineFormSet,
    RevenueSourceForm,
    RevenueSourceItemInlineFormSet,
    BillForm,
    BillItemInlineFormSet,
    SystemInfoForm,
)
from .utils import (
    compose_acknowledgement_response_payload,
    compose_payment_response_acknowledgement_payload,
    generate_request_id,
    load_private_key,
    parse_bill_control_number_response,
    parse_payment_response,
    xml_to_dict,
)
from .tasks import (
    send_bill_control_number_request,
    process_bill_control_number_response,
    process_bill_payment_response,
    process_bill_reconciliation_response,
)


logger = logging.getLogger(__name__)


class BillingIndexView(LoginRequiredMixin, TemplateView):
    template_name = "billing/index.html"


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


class GetBillControlNumberView(LoginRequiredMixin, View):
    # Update template when a control number becomes available
    def get(self, request, *args, **kwargs):
        bill_id = kwargs.get("bill_id")
        try:
            bill = Bill.objects.get(bill_id=bill_id)
            if bill.cntr_num:
                return JsonResponse({"control_number": bill.cntr_num})
            else:
                return JsonResponse({"control_number": "Still processing ..."})
        except Bill.DoesNotExist:
            return JsonResponse({"Error": "Bill not found"}, status=404)


class BillDetailView(LoginRequiredMixin, DetailView):
    model = Bill
    template_name = "billing/bill/bill_detail.html"


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
                self.object.save()

                # Generate a unique request ID
                req_id = generate_request_id()

                # Send the bill control number request to the GEPG API
                send_bill_control_number_request.delay(req_id, self.object.bill_id)

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
                self.object.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["bill_items"] = context["bill_items"]
        return self.render_to_response(self.get_context_data(form=form))


class BillDeleteView(LoginRequiredMixin, DeleteView):
    # TODO: This view should be updated to handle the cancellation of a bill instead of deleting it
    model = Bill
    template_name = "billing/bill/bill_confirm_delete.html"
    success_url = reverse_lazy("billing:bill-list")


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
            pg_log = PaymentGatewayLog.objects.filter(req_id=req_id).update(
                res_data=xml_to_dict(response_data)
            )

            # Compose an acknowledgement response payload
            private_key = load_private_key("security/gepgclientprivate.pfx", "passpass")
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
class BillControlNumberPaymentCallbackView(View):
    def dispatch(self, *args, **kwargs):
        logger.info(
            "CSRF exempt applied to bill controll number payment response callback request"
        )
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Process the bill payment information received from the GEPG API

        try:
            # Extract the bill payment information from the request
            response_data = request.body.decode("utf-8")

            # Log the incoming request data
            logger.info(f"Received payment callback request with data: {response_data}")

            # Parse the bill payment information
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
            ) = parse_payment_response(response_data)

            # Create a payment gateway log entry
            bill = Bill.objects.get(bill_id=bill_id)
            pg_log = PaymentGatewayLog.objects.create(
                sys_info=bill.sys_info,
                bill=Bill.objects.get(bill_id=bill_id),
                req_id=req_id,
                req_type="5",
                req_data=xml_to_dict(response_data),
            )

            # Compose an acknowledgement response payload
            ack_id = generate_request_id()
            private_key = load_private_key("security/gepgclientprivate.pfx", "passpass")
            ack_payload = compose_payment_response_acknowledgement_payload(
                ack_id=ack_id,
                req_id=req_id,
                ack_sts_code="7101",
                private_key=private_key,
            )

            # Process the bill payment information asynchronously
            logger.info(
                f"Schedule processing of payment response data: {response_data}"
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

            # Log the acknowledgement payload
            logger.info(f"Acknowledgement payload: {ack_payload}")

            # Update the payment gateway log with the acknowledgement payload
            pg_log.req_ack = xml_to_dict(ack_payload)
            pg_log.save()

            # Return an HTTP response with the acknowledgement payload
            return HttpResponse(ack_payload, content_type="text/xml", status=200)
        except Exception as e:
            # Log the error
            print(e)
            logger.error(f"An error occurred: {str(e)}")

            # Return an HTTP response
            return HttpResponseRedirect("ERROR", status=500)


@method_decorator(csrf_exempt, name="dispatch")
class BillControlNumberReconciliationCallbackView(View):
    def dispatch(self, *args, **kwargs):
        logger.info(
            "CSRF exempt applied to bill controll number reconciliation response callback request"
        )
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Process the bill reconciliation information received from the GEPG API

        # Extract the bill reconciliation information from the request
        response_data = request.body.decode("utf-8")

        # Process the bill reconciliation information asynchronously
        process_bill_reconciliation_response.delay(response_data)

        # Return an HTTP response
        return HttpResponseRedirect("/")
