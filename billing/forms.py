from django import forms
from django.utils import timezone

from .models import (
    Bill,
    BillingDepartment,
    BillItem,
    CancelledBill,
    Customer,
    ExchangeRate,
    PaymentReconciliation,
    RevenueSource,
    RevenueSourceItem,
    ServiceProvider,
    SystemInfo,
    BillingDepartmentAccount,
    Currency,
)


class SystemInfoForm(forms.ModelForm):
    class Meta:
        model = SystemInfo
        fields = "__all__"


class ExchangeRateForm(forms.ModelForm):
    class Meta:
        model = ExchangeRate
        fields = "__all__"


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"


class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = "__all__"


class BillingDepartmentForm(forms.ModelForm):
    class Meta:
        model = BillingDepartment
        fields = "__all__"


class ServiceProviderBillingDepartmentInlineForm(forms.ModelForm):
    class Meta:
        model = BillingDepartment
        fields = ("name", "code", "description")


class BillingDepartmentAccountForm(forms.ModelForm):
    class Meta:
        model = BillingDepartmentAccount
        fields = "__all__"


class BaseServiceProviderBillingDepartmentInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super(BaseServiceProviderBillingDepartmentInlineFormSet, self).clean()
        dept_count = 0
        for form in self.forms:
            if not form.cleaned_data.get("DELETE"):
                dept_count += 1

        if dept_count < 1:
            raise forms.ValidationError("At least one billing department is required.")


ServiceProviderBillingDepartmentInlineFormSet = forms.inlineformset_factory(
    ServiceProvider,
    BillingDepartment,
    form=ServiceProviderBillingDepartmentInlineForm,
    formset=BaseServiceProviderBillingDepartmentInlineFormSet,
    extra=1,
)


class RevenueSourceForm(forms.ModelForm):
    class Meta:
        model = RevenueSource
        fields = "__all__"


class RevenueSourceItemForm(forms.ModelForm):
    class Meta:
        model = RevenueSourceItem
        fields = "__all__"


class BaseRevenueSourceItemInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super(BaseRevenueSourceItemInlineFormSet, self).clean()
        item_count = 0
        for form in self.forms:
            if not form.cleaned_data.get("DELETE"):
                item_count += 1

        if item_count < 1:
            raise forms.ValidationError("At least one revenue source item is required.")


RevenueSourceItemInlineFormSet = forms.inlineformset_factory(
    RevenueSource,
    RevenueSourceItem,
    form=RevenueSourceItemForm,
    formset=BaseRevenueSourceItemInlineFormSet,
    extra=1,
)


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        exclude = (
            "sys_info",
            "bill_id",
            "grp_bill_id",
            "expr_date",
            "cntr_num",
            "amt",
            "eqv_amt",
            "min_amt",
            "max_amt",
        )


class BillItemForm(forms.ModelForm):
    class Meta:
        model = BillItem
        exclude = ("description", "amt", "eqv_amt", "misc_amt")


class BaseBillItemInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        total_qty = 0
        for form in self.forms:
            if (
                not form.cleaned_data.get("DELETE")
                and form.cleaned_data.get("qty") is not None
            ):
                total_qty += form.cleaned_data.get("qty")

        if total_qty < 1:
            raise forms.ValidationError("At least one item is required.")
        return self.cleaned_data


BillItemInlineFormSet = forms.inlineformset_factory(
    Bill, BillItem, form=BillItemForm, formset=BaseBillItemInlineFormSet, extra=1
)


class BillCancellationForm(forms.ModelForm):
    class Meta:
        model = CancelledBill
        fields = ["reason"]


class CancelledBillForm(forms.ModelForm):
    class Meta:
        model = CancelledBill
        fields = ["bill", "reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Eligibility: only bills with a control number and not already cancelled.
        bill_qs = (
            Bill.objects.select_related("customer")
            .filter(cntr_num__isnull=False, cancelledbill__isnull=True)
            .order_by("-created_at")
        )
        self.fields["bill"].queryset = bill_qs
        self.fields["bill"].widget.attrs.update(
            {
                "class": "bill-select2",
                "data-placeholder": "Search bill by ID, customer, or control number...",
            }
        )

        # Avoid rendering a massive <select> list; Select2 will populate via AJAX.
        if not self.is_bound:
            if self.instance.pk and getattr(self.instance, "bill_id", None):
                bill = getattr(self.instance, "bill", None)
                if bill:
                    label = f"{bill.bill_id} | {bill.customer.get_name()} | {bill.currency} {bill.amt} | CN {bill.cntr_num}"
                    self.fields["bill"].choices = [(bill.pk, label)]
            else:
                self.fields["bill"].choices = []


class BillCurrencyUpdateForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ["currency"]


class PaymentReconciliationForm(forms.ModelForm):
    trx_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )

    class Meta:
        model = PaymentReconciliation
        fields = ["trx_date"]


class FinancialReportFilterForm(forms.Form):
    PERIOD_FISCAL_YEAR = "FY"
    PERIOD_FISCAL_QUARTER = "FQ"
    PERIOD_DATE_RANGE = "DR"

    BASIS_COLLECTIONS = "COLLECTIONS"
    BASIS_BILLS_ISSUED = "BILLS"

    period = forms.ChoiceField(
        choices=(
            (PERIOD_FISCAL_YEAR, "Fiscal Year (Tanzania)"),
            (PERIOD_FISCAL_QUARTER, "Fiscal Quarter (Tanzania)"),
            (PERIOD_DATE_RANGE, "Custom Date Range"),
        ),
        required=True,
    )
    fiscal_year = forms.IntegerField(
        required=False,
        help_text="Fiscal year start (e.g. 2025 means 2025/2026; Tanzania FY starts 01-July).",
    )
    quarter = forms.ChoiceField(
        choices=(("1", "Q1 (Jul–Sep)"), ("2", "Q2 (Oct–Dec)"), ("3", "Q3 (Jan–Mar)"), ("4", "Q4 (Apr–Jun)")),
        required=False,
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    basis = forms.ChoiceField(
        choices=((BASIS_COLLECTIONS, "Collections (Payments)"), (BASIS_BILLS_ISSUED, "Bills Issued")),
        required=True,
    )
    currency = forms.ChoiceField(
        required=False,
        choices=(),
        help_text="Optional filter by currency.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        currency_choices = [("", "All")]
        currency_choices += list(Currency.objects.values_list("code", "code").order_by("code"))
        self.fields["currency"].choices = currency_choices

        now = timezone.now()
        default_fy = now.year if now.month >= 7 else now.year - 1
        self.fields["fiscal_year"].initial = default_fy
        self.fields["period"].initial = self.PERIOD_FISCAL_QUARTER
        self.fields["basis"].initial = self.BASIS_COLLECTIONS

        # default quarter from current date in Tanzania fiscal year
        # Jul-Sep=Q1, Oct-Dec=Q2, Jan-Mar=Q3, Apr-Jun=Q4
        month = now.month
        if month in (7, 8, 9):
            q = "1"
        elif month in (10, 11, 12):
            q = "2"
        elif month in (1, 2, 3):
            q = "3"
        else:
            q = "4"
        self.fields["quarter"].initial = q

    def clean(self):
        cleaned = super().clean()
        period = cleaned.get("period")
        fiscal_year = cleaned.get("fiscal_year")
        quarter = cleaned.get("quarter")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")

        if period in {self.PERIOD_FISCAL_YEAR, self.PERIOD_FISCAL_QUARTER} and not fiscal_year:
            self.add_error("fiscal_year", "Fiscal year is required.")
        if period == self.PERIOD_FISCAL_QUARTER and not quarter:
            self.add_error("quarter", "Quarter is required.")
        if period == self.PERIOD_DATE_RANGE:
            if not start_date:
                self.add_error("start_date", "Start date is required.")
            if not end_date:
                self.add_error("end_date", "End date is required.")
            if start_date and end_date and start_date > end_date:
                self.add_error("end_date", "End date must be after start date.")

        return cleaned
