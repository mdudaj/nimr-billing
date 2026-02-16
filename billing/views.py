import functools
import logging
import ssl
from datetime import date

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
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
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth

from .forms import (
    BillCancellationForm,
    BillForm,
    BillItemInlineFormSet,
    CustomerForm,
    PaymentReconciliationForm,
    FinancialReportFilterForm,
    RevenueSourceForm,
    RevenueSourceItemInlineFormSet,
    ServiceProviderBillingDepartmentInlineFormSet,
    ServiceProviderForm,
    SystemInfoForm,
    BillingDepartmentAccountForm,
)
from .models import (
    Bill,
    BillingDepartment,
    BillingDepartmentAccount,
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
    _static_file_path,
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        month_start = today.replace(day=1)

        payments = Payment.objects.all()
        bills = Bill.objects.all()

        # All-time totals (collections)
        paid_by_currency = {
            row["currency"]: row
            for row in payments.values("currency").annotate(
                total_paid=Sum("paid_amt"),
                paid_count=Count("bill_id"),
            )
        }
        context["total_paid_tzs_invoices"] = paid_by_currency.get("TZS", {}).get(
            "total_paid", 0
        )
        context["paid_tzs_invoices_count"] = paid_by_currency.get("TZS", {}).get(
            "paid_count", 0
        )
        context["total_paid_usd_invoices"] = paid_by_currency.get("USD", {}).get(
            "total_paid", 0
        )
        context["paid_usd_invoices_count"] = paid_by_currency.get("USD", {}).get(
            "paid_count", 0
        )
        # Backwards-compatible naming used by older dashboard template.
        context["total_tzs_revenues"] = context["total_paid_tzs_invoices"]
        context["total_usd_revenues"] = context["total_paid_usd_invoices"]

        # Outstanding (unpaid bills)
        unpaid_by_currency = {
            row["currency"]: row
            for row in bills.filter(payment__isnull=True)
            .values("currency")
            .annotate(
                total_unpaid=Sum("amt"),
                unpaid_count=Count("id"),
            )
        }
        context["total_unpaid_tzs_invoices"] = unpaid_by_currency.get("TZS", {}).get(
            "total_unpaid", 0
        )
        context["unpaid_tzs_invoices_count"] = unpaid_by_currency.get("TZS", {}).get(
            "unpaid_count", 0
        )
        context["total_unpaid_usd_invoices"] = unpaid_by_currency.get("USD", {}).get(
            "total_unpaid", 0
        )
        context["unpaid_usd_invoices_count"] = unpaid_by_currency.get("USD", {}).get(
            "unpaid_count", 0
        )

        # KPI: today + month collections
        paid_today = payments.filter(trx_date__date=today)
        paid_month = payments.filter(trx_date__date__gte=month_start, trx_date__date__lte=today)

        context["paid_today_by_currency"] = list(
            paid_today.values("currency").annotate(
                payments_count=Count("bill_id"),
                total_paid=Sum("paid_amt"),
            )
        )
        context["paid_month_by_currency"] = list(
            paid_month.values("currency").annotate(
                payments_count=Count("bill_id"),
                total_paid=Sum("paid_amt"),
            )
        )

        context["bills_today_count"] = bills.filter(gen_date__date=today).count()
        context["bills_month_count"] = bills.filter(
            gen_date__date__gte=month_start, gen_date__date__lte=today
        ).count()

        # Visualization: last 6 months collections (by currency)
        six_months_ago = (month_start - timezone.timedelta(days=183)).replace(day=1)
        monthly = (
            payments.filter(trx_date__date__gte=six_months_ago)
            .annotate(month=TruncMonth("trx_date"))
            .values("month", "currency")
            .annotate(total_paid=Sum("paid_amt"))
            .order_by("month", "currency")
        )

        month_map = {}
        for row in monthly:
            key = row["month"].date().replace(day=1)
            month_map.setdefault(key, {"month": key, "TZS": 0, "USD": 0})
            month_map[key][row["currency"]] = row["total_paid"] or 0

        monthly_rows = [month_map[k] for k in sorted(month_map.keys())][-6:]
        max_tzs = max([r["TZS"] for r in monthly_rows] or [0])
        max_usd = max([r["USD"] for r in monthly_rows] or [0])
        for r in monthly_rows:
            r["tzs_pct"] = (float(r["TZS"]) / float(max_tzs) * 100) if max_tzs else 0
            r["usd_pct"] = (float(r["USD"]) / float(max_usd) * 100) if max_usd else 0
        context["monthly_collections"] = monthly_rows
        context["monthly_collections_max_tzs"] = max_tzs
        context["monthly_collections_max_usd"] = max_usd

        return context


class FinancialReportView(LoginRequiredMixin, TemplateView):
    template_name = "billing/reports/financial_report.html"

    def _period_range(self, form: FinancialReportFilterForm):
        period = form.cleaned_data["period"]

        if period == FinancialReportFilterForm.PERIOD_DATE_RANGE:
            return (
                form.cleaned_data["start_date"],
                form.cleaned_data["end_date"],
                "Custom Range",
            )

        fiscal_year = int(form.cleaned_data["fiscal_year"])
        fy_start = date(fiscal_year, 7, 1)
        fy_end = date(fiscal_year + 1, 6, 30)

        if period == FinancialReportFilterForm.PERIOD_FISCAL_YEAR:
            return fy_start, fy_end, f"FY {fiscal_year}/{fiscal_year + 1}"

        quarter = int(form.cleaned_data["quarter"])
        if quarter == 1:
            return date(fiscal_year, 7, 1), date(fiscal_year, 9, 30), f"FY{fiscal_year} Q1"
        if quarter == 2:
            return date(fiscal_year, 10, 1), date(fiscal_year, 12, 31), f"FY{fiscal_year} Q2"
        if quarter == 3:
            return date(fiscal_year + 1, 1, 1), date(fiscal_year + 1, 3, 31), f"FY{fiscal_year} Q3"
        return date(fiscal_year + 1, 4, 1), date(fiscal_year + 1, 6, 30), f"FY{fiscal_year} Q4"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FinancialReportFilterForm(self.request.GET or None)
        context["filter_form"] = form

        if not form.is_valid():
            # Render the page with validation errors.
            return context

        start_date, end_date, period_label = self._period_range(form)
        basis = form.cleaned_data["basis"]
        currency = (form.cleaned_data.get("currency") or "").strip()

        context["period_start"] = start_date
        context["period_end"] = end_date
        context["period_label"] = period_label
        context["basis"] = basis
        context["currency"] = currency

        if basis == FinancialReportFilterForm.BASIS_COLLECTIONS:
            payments = Payment.objects.select_related("bill").filter(
                trx_date__date__gte=start_date,
                trx_date__date__lte=end_date,
            )
            if currency:
                payments = payments.filter(currency=currency)

            context["totals_by_currency"] = list(
                payments.values("currency").annotate(
                    payments_count=Count("bill_id"),
                    total_paid=Sum("paid_amt"),
                )
            )
            context["totals_by_collection_account"] = list(
                payments.values("currency", "coll_acc_num").annotate(
                    payments_count=Count("bill_id"),
                    total_paid=Sum("paid_amt"),
                ).order_by("currency", "coll_acc_num")
            )

            # Approximate MoFP-style stream totals by summing bill items for bills that were paid in the period.
            bill_items = BillItem.objects.select_related(
                "rev_src_itm",
                "rev_src_itm__rev_src",
                "bill",
            ).filter(
                bill__payment__trx_date__date__gte=start_date,
                bill__payment__trx_date__date__lte=end_date,
            )
            if currency:
                bill_items = bill_items.filter(bill__currency=currency)
            context["totals_by_revenue_stream"] = list(
                bill_items.values(
                    "bill__currency",
                    "rev_src_itm__rev_src__gfs_code",
                    "rev_src_itm__rev_src__name",
                )
                .annotate(total_amount=Sum("amt"), bills_count=Count("bill_id", distinct=True))
                .order_by("bill__currency", "rev_src_itm__rev_src__gfs_code")
            )

        else:
            bills = Bill.objects.filter(
                gen_date__date__gte=start_date,
                gen_date__date__lte=end_date,
            )
            if currency:
                bills = bills.filter(currency=currency)

            context["totals_by_currency"] = list(
                bills.values("currency").annotate(
                    bills_count=Count("id"),
                    total_billed=Sum("amt"),
                )
            )

            bill_items = BillItem.objects.select_related(
                "rev_src_itm",
                "rev_src_itm__rev_src",
                "bill",
            ).filter(
                bill__gen_date__date__gte=start_date,
                bill__gen_date__date__lte=end_date,
            )
            if currency:
                bill_items = bill_items.filter(bill__currency=currency)
            context["totals_by_revenue_stream"] = list(
                bill_items.values(
                    "bill__currency",
                    "rev_src_itm__rev_src__gfs_code",
                    "rev_src_itm__rev_src__name",
                )
                .annotate(total_amount=Sum("amt"), bills_count=Count("bill_id", distinct=True))
                .order_by("bill__currency", "rev_src_itm__rev_src__gfs_code")
            )

        return context


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
    paginate_by = 25
    ordering = ["-trx_date", "currency__code"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("currency")

        search = (self.request.GET.get("search") or "").strip()
        if search:
            search_query = models.Q(currency__code__icontains=search) | models.Q(
                currency__name__icontains=search
            )
            try:
                search_date = date.fromisoformat(search)
            except ValueError:
                search_date = None
            if search_date:
                search_query |= models.Q(trx_date=search_date)
            queryset = queryset.filter(search_query)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        return context


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
    paginate_by = 25
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
                | models.Q(tin__icontains=search)
                | models.Q(email__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        return context


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
        if not billingdepartment.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
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
        if not billingdepartment.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
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


class BillingDepartmentAccountListView(LoginRequiredMixin, ListView):
    model = BillingDepartmentAccount
    template_name = "billing/billing_department_account/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("billing_department", "account_currency")
            .filter(billing_department_id=self.kwargs["dept_pk"])
            .order_by("bank", "account_currency__code", "account_num")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["department"] = get_object_or_404(
            BillingDepartment, pk=self.kwargs["dept_pk"]
        )
        return context


class BillingDepartmentAccountCreateView(LoginRequiredMixin, CreateView):
    model = BillingDepartmentAccount
    form_class = BillingDepartmentAccountForm
    template_name = "billing/billing_department_account/account_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "billing:dept-account-list", kwargs={"dept_pk": self.kwargs["dept_pk"]}
        )

    def get_initial(self):
        initial = super().get_initial()
        initial["billing_department"] = self.kwargs["dept_pk"]
        return initial

    def form_valid(self, form):
        form.instance.billing_department_id = self.kwargs["dept_pk"]
        return super().form_valid(form)


class BillingDepartmentAccountUpdateView(LoginRequiredMixin, UpdateView):
    model = BillingDepartmentAccount
    form_class = BillingDepartmentAccountForm
    template_name = "billing/billing_department_account/account_form.html"

    def get_success_url(self):
        return reverse_lazy(
            "billing:dept-account-list", kwargs={"dept_pk": self.object.billing_department_id}
        )


class BillingDepartmentAccountDeleteView(LoginRequiredMixin, DeleteView):
    model = BillingDepartmentAccount
    template_name = "billing/billing_department_account/account_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy(
            "billing:dept-account-list", kwargs={"dept_pk": self.object.billing_department_id}
        )


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
    paginate_by = 25
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("customer")

        # Search functionality
        search = self.request.GET.get("search")
        if search:
            search_query = (
                models.Q(bill_id__icontains=search)
                | models.Q(description__icontains=search)
                | models.Q(customer__first_name__icontains=search)
                | models.Q(customer__last_name__icontains=search)
            )
            if search.isdigit():
                try:
                    search_num = int(search)
                except (ValueError, OverflowError):
                    search_num = None
                if search_num is not None and search_num <= 9223372036854775807:
                    search_query |= models.Q(cntr_num=search_num)
            queryset = queryset.filter(search_query)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        return context


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

                self.object.recalculate_amounts()

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

                self.object.recalculate_amounts()

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
class BillControlNumberPaymentCallbackView(View):

    def post(self, request):
        pg_log = None

        try:
            raw_body = request.body.decode("utf-8", errors="ignore")
            logger.info("Payment callback received")

            # ---- Parse safely ----
            try:
                parsed = parse_payment_response(raw_body)
            except Exception:
                logger.exception("Payment response parsing failed")
                return HttpResponse("INVALID", status=400)

            if not parsed or len(parsed) != 17:
                logger.error("Parsed payment response has invalid structure")
                return HttpResponse("INVALID", status=400)

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
            ) = parsed

            # ---- ACK FIRST (critical) ----
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
            except Exception:
                logger.exception("Failed to generate ACK")
                return HttpResponse("ERROR", status=500)

            # ---- Idempotency check ----
            pg_log, created = PaymentGatewayLog.objects.get_or_create(
                req_id=req_id,
                req_type="5",
                defaults={
                    "status": "RECEIVED",
                    "status_desc": "Callback received",
                    "req_data": xml_to_dict(raw_body),
                },
            )

            if not created:
                logger.info("Duplicate callback received for req_id=%s", req_id)
                return HttpResponse(ack_payload, content_type="text/xml", status=200)

            # ---- Bill lookup ----
            try:
                bill = Bill.objects.get(bill_id=bill_id)
                pg_log.bill = bill
                pg_log.sys_info = bill.sys_info
                pg_log.save(update_fields=["bill", "sys_info"])
            except Bill.DoesNotExist:
                pg_log.status = "ERROR"
                pg_log.status_desc = "Bill not found"
                pg_log.save()
                return HttpResponse(ack_payload, content_type="text/xml", status=200)

            # ---- Fire-and-forget Celery ----
            try:
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
                pg_log.status = "QUEUED"
                pg_log.status_desc = "Payment processing queued"
            except Exception:
                logger.exception("Failed to enqueue Celery task")
                pg_log.status = "ERROR"
                pg_log.status_desc = "Celery enqueue failed"

            pg_log.req_ack = xml_to_dict(ack_payload)
            pg_log.save()

            return HttpResponse(ack_payload, content_type="text/xml", status=200)

        except Exception:
            logger.exception("Unhandled exception in payment callback")
            return HttpResponse("ERROR", status=500)


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
    paginate_by = 25
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("bill", "bill__customer", "gen_by", "appr_by")
        )
        search = self.request.GET.get("search")
        if search:
            search_query = (
                models.Q(bill__bill_id__icontains=search)
                | models.Q(bill__customer__first_name__icontains=search)
                | models.Q(bill__customer__last_name__icontains=search)
                | models.Q(bill__customer__tin__icontains=search)
                | models.Q(bill__customer__email__icontains=search)
            )
            if search.isdigit():
                try:
                    search_num = int(search)
                except (ValueError, OverflowError):
                    search_num = None
                if search_num is not None and search_num <= 9223372036854775807:
                    search_query |= models.Q(bill__cntr_num=search_num) | models.Q(
                        cust_cntr_num=search_num
                    )
            queryset = queryset.filter(search_query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        return context


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
    paginate_by = 25
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("bill", "bill__customer")

        search = self.request.GET.get("search")
        if search:
            search_query = (
                models.Q(bill__bill_id__icontains=search)
                | models.Q(payref_id__icontains=search)
                | models.Q(currency__icontains=search)
                | models.Q(psp_name__icontains=search)
                | models.Q(trx_id__icontains=search)
                | models.Q(trdpty_trx_id__icontains=search)
                | models.Q(bill__customer__first_name__icontains=search)
                | models.Q(bill__customer__last_name__icontains=search)
                | models.Q(bill__customer__tin__icontains=search)
                | models.Q(bill__customer__email__icontains=search)
            )
            if search.isdigit():
                try:
                    search_num = int(search)
                except (ValueError, OverflowError):
                    search_num = None
                if search_num is not None and search_num <= 9223372036854775807:
                    search_query |= models.Q(cust_cntr_num=search_num) | models.Q(
                        bill__cntr_num=search_num
                    )
            queryset = queryset.filter(search_query)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        return context


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = "billing/payment/payment_detail.html"


def check_control_number_request_status(request, pk):
    """Check the status of a bill control number request."""

    try:
        bill = get_object_or_404(Bill, id=pk)
    except Exception:
        return JsonResponse(
            {"status": "NOT_FOUND", "message": "Bill not found."}, status=404
        )

    try:
        # Fetch the latest log entry for this bill
        log = PaymentGatewayLog.objects.filter(bill=bill, req_type="1").latest(
            "created_at"
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

    except PaymentGatewayLog.DoesNotExist:
        # Return pending status instead of logging error
        return JsonResponse(
            {
                "status": "PENDING",
                "message": "Payment status check in progress. Please try again later.",
            },
            status=202,
        )

    except Exception as e:
        # Only log critical errors, not missing records
        return JsonResponse(
            {"status": "ERROR", "message": "Service temporarily unavailable"},
            status=503,
        )


class BillPrintPDFView(WeasyTemplateView):
    template_name = "billing/printout/bill_print_pdf.html"
    pdf_stylesheets = [
        # settings.STATIC_ROOT + "/semantic-ui/semantic.min.css",
        _static_file_path("css/bill_print.css"),
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
        logo_path = _static_file_path("img/coat-of-arms-of-tanzania.png")
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
        context["bill"] = bill
        context["print_date"] = self.print_date
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
        _static_file_path("css/bill_transfer_print.css"),
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
        accounts = list(
            bill.dept.accounts.select_related("account_currency")
            .filter(account_currency__code=bill.currency)
            .order_by("bank", "account_num")
        )
        logo_path = _static_file_path("img/coat-of-arms-of-tanzania.png")
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
        context["bill"] = bill
        context["accounts"] = accounts
        context["print_date"] = self.print_date
        return context

    def get_bill(self):
        return Bill.objects.get(pk=self.kwargs["pk"])

    def get_pdf_filename(self):
        # Get the bill transfer and generate the PDF filename dynamically using the transfer_id
        bill = self.get_bill()
        return f"{bill.bill_id}_NatHREC.pdf"


class BillReceiptPrintPDFView(LoginRequiredMixin, WeasyTemplateView):
    template_name = "billing/printout/bill_receipt_print_pdf.html"
    pdf_stylesheets = [
        # settings.STATIC_ROOT + "/semantic-ui/semantic.min.css",
        _static_file_path("css/bill_receipt_print.css"),
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
        logo_path = _static_file_path("img/coat-of-arms-of-tanzania.png")
        context["image_path"] = logo_path
        context["bill_rcpt"] = self.get_payment()
        return context

    def get_payment(self):
        bill = Bill.objects.get(pk=self.kwargs["pk"])
        return Payment.objects.get(bill=bill)

    def get_pdf_filename(self):
        # Get the payment and generate the PDF filename dynamically using the payment_id
        rcpt = self.get_payment()
        return f"{rcpt.bill.bill_id}_Receipt_NatHREC.pdf"
