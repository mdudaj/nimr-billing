import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from billing.models import (
    BillingDepartment,
    BillingDepartmentAccount,
    Currency,
    RevenueSource,
    RevenueSourceItem,
    ServiceProvider,
)


class Command(BaseCommand):
    help = "Upsert (update or create) service provider and revenue source reference data from JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dump",
            action="store_true",
            help="Dump current DB reference data as JSON (use --output to write to file)",
        )
        parser.add_argument(
            "--path",
            default="billing/fixtures/reference_data.json",
            help="Path to JSON file (default: billing/fixtures/reference_data.json)",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output path for --dump (default: same as --path). Use '-' for stdout.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created/updated without saving changes",
        )

    def _dec2(self, value: Decimal) -> str:
        try:
            return str(value.quantize(Decimal("0.01")))
        except Exception:
            return format(value, "f")

    def _dump_reference_data(self) -> dict:
        payload = {"service_providers": [], "revenue_sources": []}

        for sp in ServiceProvider.objects.all().order_by("code", "id"):
            sp_entry = {
                "code": sp.code,
                "name": sp.name,
                "grp_code": sp.grp_code,
                "sys_code": sp.sys_code,
                "departments": [],
            }

            for dept in (
                BillingDepartment.objects.filter(service_provider=sp)
                .order_by("code", "name", "id")
            ):
                dept_entry = {
                    "code": dept.code,
                    "name": dept.name,
                    "description": dept.description,
                    "accounts": [],
                }

                accounts = list(
                    dept.accounts.select_related("account_currency").order_by(
                        "bank", "account_currency__code", "account_num", "id"
                    )
                )
                # If no new-style accounts exist, include legacy account fields (if complete).
                if (
                    not accounts
                    and dept.bank
                    and dept.bank_swift_code
                    and dept.account_num
                    and dept.account_currency_id
                ):
                    accounts = [
                        BillingDepartmentAccount(
                            billing_department=dept,
                            bank=dept.bank,
                            bank_swift_code=dept.bank_swift_code,
                            account_num=dept.account_num,
                            account_currency=dept.account_currency,
                        )
                    ]

                for acct in accounts:
                    ccy = getattr(acct.account_currency, "code", None)
                    if not ccy:
                        continue
                    dept_entry["accounts"].append(
                        {
                            "bank": acct.bank,
                            "bank_swift_code": acct.bank_swift_code,
                            "account_num": acct.account_num,
                            "currency": ccy,
                        }
                    )

                sp_entry["departments"].append(dept_entry)

            payload["service_providers"].append(sp_entry)

        for rs in RevenueSource.objects.all().order_by("gfs_code", "name", "id"):
            rs_entry = {
                "gfs_code": rs.gfs_code,
                "name": rs.name,
                "category": rs.category,
                "sub_category": rs.sub_category,
                "items": [],
            }
            for item in (
                RevenueSourceItem.objects.filter(rev_src=rs)
                .order_by("currency", "description", "id")
            ):
                rs_entry["items"].append(
                    {
                        "description": item.description,
                        "amt": self._dec2(item.amt),
                        "currency": item.currency,
                    }
                )
            payload["revenue_sources"].append(rs_entry)

        return payload

    def _get_or_create_currency(self, code: str, *, dry_run: bool) -> Currency:
        code = (code or "").strip().upper()
        if not code:
            raise CommandError("Currency code is required")

        obj = Currency.objects.filter(code=code).first()
        if obj:
            return obj

        if dry_run:
            self.stdout.write(f"[DRY-RUN] Would create Currency {code}")
            return Currency(code=code, name=code)

        obj, _ = Currency.objects.get_or_create(code=code, defaults={"name": code})
        return obj

    def _upsert_service_provider(self, sp_data: dict, *, dry_run: bool) -> ServiceProvider:
        code = (sp_data.get("code") or "").strip()
        grp_code = (sp_data.get("grp_code") or "").strip()
        name = (sp_data.get("name") or "").strip()
        sys_code = (sp_data.get("sys_code") or "").strip()

        if not code:
            raise CommandError("service_providers[].code is required")
        if not grp_code:
            raise CommandError(f"service_providers[{code}].grp_code is required")
        if not name:
            raise CommandError(f"service_providers[{code}].name is required")

        obj = ServiceProvider.objects.filter(code=code).first()
        if obj and obj.grp_code != grp_code:
            raise CommandError(
                f"ServiceProvider code={code} exists but grp_code differs "
                f"(db={obj.grp_code!r}, json={grp_code!r}); refusing to update unique keys"
            )

        if not obj:
            obj = ServiceProvider.objects.filter(grp_code=grp_code).first()
            if obj and obj.code != code:
                raise CommandError(
                    f"ServiceProvider grp_code={grp_code} exists but code differs "
                    f"(db={obj.code!r}, json={code!r}); refusing to update unique keys"
                )

        if obj:
            changes = []
            for field, new_value in {
                "name": name,
                "sys_code": sys_code or obj.sys_code,
            }.items():
                if new_value and getattr(obj, field) != new_value:
                    setattr(obj, field, new_value)
                    changes.append(field)

            if changes:
                if dry_run:
                    self.stdout.write(f"[DRY-RUN] Would update ServiceProvider {code}: {', '.join(changes)}")
                else:
                    obj.save(update_fields=changes + ["updated_at"])
            return obj

        if dry_run:
            self.stdout.write(f"[DRY-RUN] Would create ServiceProvider {code}")
            return ServiceProvider(code=code, grp_code=grp_code, name=name, sys_code=sys_code)

        try:
            return ServiceProvider.objects.create(
                code=code, grp_code=grp_code, name=name, sys_code=sys_code
            )
        except IntegrityError as e:
            raise CommandError(f"Failed creating ServiceProvider {code}: {e}") from e

    def _upsert_department(
        self, sp: ServiceProvider, dept_data: dict, *, dry_run: bool
    ) -> BillingDepartment:
        code = (dept_data.get("code") or "").strip() or None
        name = (dept_data.get("name") or "").strip()
        description = (dept_data.get("description") or "").strip() or None

        if not name:
            raise CommandError(f"departments[{sp.code}].name is required")

        obj = None
        if code:
            obj = BillingDepartment.objects.filter(code=code).first()
            if obj and obj.name != name:
                raise CommandError(
                    f"BillingDepartment code={code} exists but name differs "
                    f"(db={obj.name!r}, json={name!r}); refusing to update unique keys"
                )

        if not obj:
            obj = BillingDepartment.objects.filter(name=name).first()
            if obj and code and obj.code and obj.code != code:
                raise CommandError(
                    f"BillingDepartment name={name!r} exists but code differs "
                    f"(db={obj.code!r}, json={code!r}); refusing to update unique keys"
                )

        if obj:
            changes = []
            if obj.service_provider_id != sp.id:
                obj.service_provider = sp
                changes.append("service_provider")

            if description != obj.description:
                obj.description = description
                changes.append("description")

            # Safe backfill: allow setting code only when currently NULL.
            if code and obj.code is None and code != obj.code:
                obj.code = code
                changes.append("code")

            if changes:
                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Would update BillingDepartment {obj.id} ({name}): {', '.join(changes)}"
                    )
                else:
                    obj.save(update_fields=changes + ["updated_at"])
            return obj

        if dry_run:
            self.stdout.write(f"[DRY-RUN] Would create BillingDepartment {name}")
            return BillingDepartment(service_provider=sp, name=name, code=code, description=description)

        try:
            return BillingDepartment.objects.create(
                service_provider=sp, name=name, code=code, description=description
            )
        except IntegrityError as e:
            raise CommandError(f"Failed creating BillingDepartment '{name}': {e}") from e

    def _upsert_department_account(
        self, dept: BillingDepartment, acct_data: dict, *, dry_run: bool
    ) -> BillingDepartmentAccount:
        bank = (acct_data.get("bank") or "").strip()
        bank_swift_code = (acct_data.get("bank_swift_code") or "").strip()
        account_num = (acct_data.get("account_num") or "").strip()
        currency_code = (acct_data.get("currency") or "").strip()

        if not bank:
            raise CommandError(f"accounts[{dept.id}].bank is required")
        if not bank_swift_code:
            raise CommandError(f"accounts[{dept.id}].bank_swift_code is required")
        if not account_num:
            raise CommandError(f"accounts[{dept.id}].account_num is required")
        if not currency_code:
            raise CommandError(f"accounts[{dept.id}].currency is required")

        currency = self._get_or_create_currency(currency_code, dry_run=dry_run)
        if dry_run:
            if not currency.pk:
                self.stdout.write(
                    f"[DRY-RUN] Would create BillingDepartmentAccount ({dept.name}, {bank}, {currency.code}, {account_num})"
                )
                return BillingDepartmentAccount(
                    billing_department=dept,
                    bank=bank,
                    bank_swift_code=bank_swift_code,
                    account_currency=currency,
                    account_num=account_num,
                )

            obj = BillingDepartmentAccount.objects.filter(
                billing_department=dept,
                bank=bank,
                account_currency=currency,
                account_num=account_num,
            ).first()
            if not obj:
                self.stdout.write(
                    f"[DRY-RUN] Would create BillingDepartmentAccount ({dept.name}, {bank}, {currency.code}, {account_num})"
                )
                return BillingDepartmentAccount(
                    billing_department=dept,
                    bank=bank,
                    bank_swift_code=bank_swift_code,
                    account_currency=currency,
                    account_num=account_num,
                )

            if obj.bank_swift_code != bank_swift_code:
                self.stdout.write(
                    f"[DRY-RUN] Would update BillingDepartmentAccount {obj.id}: bank_swift_code"
                )
            return obj

        obj, created = BillingDepartmentAccount.objects.get_or_create(
            billing_department=dept,
            bank=bank,
            account_currency=currency,
            account_num=account_num,
            defaults={"bank_swift_code": bank_swift_code},
        )

        if not created and obj.bank_swift_code != bank_swift_code:
            obj.bank_swift_code = bank_swift_code
            obj.save(update_fields=["bank_swift_code", "updated_at"])

        return obj

    def _upsert_revenue_source(self, rs_data: dict, *, dry_run: bool) -> RevenueSource:
        gfs_code = (rs_data.get("gfs_code") or "").strip()
        name = (rs_data.get("name") or "").strip()
        category = (rs_data.get("category") or "").strip()
        sub_category = (rs_data.get("sub_category") or "").strip()

        if not gfs_code:
            raise CommandError("revenue_sources[].gfs_code is required")
        if not name:
            raise CommandError(f"revenue_sources[{gfs_code}].name is required")

        qs = RevenueSource.objects.filter(gfs_code=gfs_code).order_by("id")
        obj = qs.first()
        if qs.count() > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"Multiple RevenueSource rows found for gfs_code={gfs_code}; updating id={obj.id}"
                )
            )

        if obj:
            changes = []
            for field, new_value in {
                "name": name,
                "category": category or obj.category,
                "sub_category": sub_category or obj.sub_category,
            }.items():
                if new_value and getattr(obj, field) != new_value:
                    setattr(obj, field, new_value)
                    changes.append(field)

            if changes:
                if dry_run:
                    self.stdout.write(f"[DRY-RUN] Would update RevenueSource {gfs_code}: {', '.join(changes)}")
                else:
                    obj.save(update_fields=changes + ["updated_at"])
            return obj

        if dry_run:
            self.stdout.write(f"[DRY-RUN] Would create RevenueSource {gfs_code}")
            return RevenueSource(
                gfs_code=gfs_code,
                name=name,
                category=category,
                sub_category=sub_category,
            )

        return RevenueSource.objects.create(
            gfs_code=gfs_code,
            name=name,
            category=category,
            sub_category=sub_category,
        )

    def _upsert_revenue_item(
        self, rs: RevenueSource, item_data: dict, *, dry_run: bool
    ) -> RevenueSourceItem:
        description = (item_data.get("description") or "").strip()
        currency = (item_data.get("currency") or "").strip().upper() or "TZS"
        amt_raw = item_data.get("amt")

        if not description:
            raise CommandError(f"revenue_sources[{rs.gfs_code}].items[].description is required")
        if amt_raw is None or str(amt_raw).strip() == "":
            raise CommandError(f"revenue_sources[{rs.gfs_code}].items[{description}].amt is required")

        # Ensure supported currency choice values exist.
        currency = currency.upper()
        if currency not in {"TZS", "USD"}:
            raise CommandError(
                f"Unsupported currency '{currency}' for RevenueSourceItem (supported: TZS, USD)"
            )

        try:
            amt = Decimal(str(amt_raw))
        except (InvalidOperation, ValueError) as e:
            raise CommandError(
                f"Invalid amt for revenue_sources[{rs.gfs_code}].items[{description}]: {amt_raw}"
            ) from e
        obj = RevenueSourceItem.objects.filter(
            rev_src=rs, description=description, currency=currency
        ).order_by("id").first()

        if obj:
            if obj.amt != amt:
                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Would update RevenueSourceItem {obj.id}: amt"
                    )
                else:
                    obj.amt = amt
                    obj.save(update_fields=["amt", "updated_at"])
            return obj

        if dry_run:
            self.stdout.write(
                f"[DRY-RUN] Would create RevenueSourceItem ({rs.gfs_code}, {currency}): {description}"
            )
            return RevenueSourceItem(rev_src=rs, description=description, currency=currency, amt=amt)

        return RevenueSourceItem.objects.create(
            rev_src=rs, description=description, currency=currency, amt=amt
        )

    def handle(self, *args, **options):
        if options.get("dump"):
            out_path = options.get("output") or options.get("path")
            payload = self._dump_reference_data()
            rendered = json.dumps(payload, indent=2) + "\n"
            if out_path == "-":
                self.stdout.write(rendered)
            else:
                Path(out_path).write_text(rendered, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(f"Wrote {out_path}"))
            return

        dry_run = options["dry_run"]
        path = Path(options["path"])

        if not path.exists():
            raise CommandError(f"File not found: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}") from e

        service_providers = payload.get("service_providers") or []
        revenue_sources = payload.get("revenue_sources") or []

        if not isinstance(service_providers, list):
            raise CommandError("service_providers must be a list")
        if not isinstance(revenue_sources, list):
            raise CommandError("revenue_sources must be a list")

        if dry_run:
            self.stdout.write("DRY RUN MODE - No changes will be made")

        with transaction.atomic():
            for sp_data in service_providers:
                sp = self._upsert_service_provider(sp_data, dry_run=dry_run)
                for dept_data in sp_data.get("departments") or []:
                    dept = self._upsert_department(sp, dept_data, dry_run=dry_run)
                    for acct_data in dept_data.get("accounts") or []:
                        self._upsert_department_account(dept, acct_data, dry_run=dry_run)

            for rs_data in revenue_sources:
                rs = self._upsert_revenue_source(rs_data, dry_run=dry_run)
                for item_data in rs_data.get("items") or []:
                    self._upsert_revenue_item(rs, item_data, dry_run=dry_run)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Reference data seed completed."))
