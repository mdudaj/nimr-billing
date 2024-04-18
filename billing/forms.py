from django import forms
from .models import (
    Customer,
    ServiceProvider,
    BillingDepartment,
    RevenueSource,
    Bill,
    BillItem,
)


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
    form=ServiceProviderForm,
    formset=BaseServiceProviderBillingDepartmentInlineFormSet,
    extra=1,
)


class RevenueSourceForm(forms.ModelForm):
    class Meta:
        model = RevenueSource
        fields = "__all__"


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        exclude = (
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
        exclude = ("eqv_amt", "misc_amt")


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
