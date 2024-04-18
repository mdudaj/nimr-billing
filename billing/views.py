from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
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
    Bill,
    BillItem,
)
from .forms import (
    CustomerForm,
    ServiceProviderForm,
    ServiceProviderBillingDepartmentInlineFormSet,
    RevenueSourceForm,
    BillForm,
    BillItemInlineFormSet,
)
from .utils import generate_request_id
from .tasks import (
    send_bill_control_number_request,
    process_final_response,
    process_bill_payment_response,
    process_bill_reconciliation_response,
)


class BillingIndexView(TemplateView):
    template_name = "billing/index.html"


class CustomerListView(ListView):
    model = Customer
    template_name = "billing/customer/customer_list.html"


class CustomerDetailView(DetailView):
    model = Customer
    template_name = "billing/customer/customer_detail.html"


class CustomerCreateView(CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer/customer_form.html"
    success_url = reverse_lazy("billing:customer-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context


class CustomerUpdateView(UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer/customer_form.html"
    success_url = reverse_lazy("billing:customer-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context


class CustomerDeleteView(DeleteView):
    model = Customer
    template_name = "billing/customer/customer_confirm_delete.html"
    success_url = reverse_lazy("billing:customer-list")


class ServiceProviderListView(ListView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_list.html"


class ServiceProviderDetailView(DetailView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_detail.html"


class ServiceProviderCreateView(CreateView):
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


class ServiceProviderUpdateView(UpdateView):
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


class ServiceProviderDeleteView(DeleteView):
    model = ServiceProvider
    template_name = "billing/service_provider/sp_confirm_delete.html"
    success_url = reverse_lazy("billing:sp-list")


class RevenueSourceListView(ListView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_list.html"


class RevenueSourceDetailView(DetailView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_detail.html"


class RevenueSourceCreateView(CreateView):
    model = RevenueSource
    form_class = RevenueSourceForm
    template_name = "billing/revenue_source/rs_form.html"
    success_url = reverse_lazy("billing:rs-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        return context


class RevenueSourceUpdateView(UpdateView):
    model = RevenueSource
    form_class = RevenueSourceForm
    template_name = "billing/revenue_source/rs_form.html"
    success_url = reverse_lazy("billing:rs-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context


class RevenueSourceDeleteView(DeleteView):
    model = RevenueSource
    template_name = "billing/revenue_source/rs_confirm_delete.html"
    success_url = reverse_lazy("billing:rs-list")


class BillListView(ListView):
    model = Bill
    template_name = "billing/bill/bill_list.html"


class BillDetailView(DetailView):
    model = Bill
    template_name = "billing/bill/bill_detail.html"


class BillCreateView(CreateView):
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
                send_bill_control_number_request.delay(req_id, self.object)

        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        context["bill_items"] = context["bill_items"]
        return self.render_to_response(self.get_context_data(form=form))


class BillUpdateView(UpdateView):
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


class BillDeleteView(DeleteView):
    model = Bill
    template_name = "billing/bill/bill_confirm_delete.html"
    success_url = reverse_lazy("billing:bill-list")


class BillControlNumberResponseCallbackView(View):
    @csrf_exempt
    def post(self, request):
        # Process the bill control number response received from the GEPG API
        # Extract the response data and call the process_final_response task
        # Return an HTTP response based on the processing outcome

        # Extract the response data from the request
        response_data = request.body.decode("utf-8")

        # Process the final response asynchronously
        process_final_response.delay(response_data)

        # Return an HTTP response
        return HttpResponseRedirect("/")


class BillControlNumberPaymentCallbackView(View):
    @csrf_exempt
    def post(self, request):
        # Process the bill payment information received from the GEPG API

        # Extract the bill payment information from the request
        response_data = request.body.decode("utf-8")

        # Process the bill payment information asynchronously
        process_bill_payment_response.delay(response_data)

        # Return an HTTP response
        return HttpResponseRedirect("/")


class BillControlNumberReconciliationCallbackView(View):
    @csrf_exempt
    def post(self, request):
        # Process the bill reconciliation information received from the GEPG API

        # Extract the bill reconciliation information from the request
        response_data = request.body.decode("utf-8")

        # Process the bill reconciliation information asynchronously
        process_bill_reconciliation_response.delay(response_data)

        # Return an HTTP response
        return HttpResponseRedirect("/")
