from billing.models import (
    Bill,
    Customer,
    BillingDepartment,
    ServiceProvider,
    RevenueSource,
    RevenueSourceItem,
    BillItem,
)

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, TestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os


class BillCurrencyTestCase(TestCase):
    def setUp(self):
        # Setup test data

        # Create Customer
        self.customer = Customer.objects.create(
            first_name="John",
            middle_name="A.",
            last_name="Doe",
            tin="123456789",
            id_num="1234567890123456",
            id_type="1",
            account_num="9876543210",
            cell_num="255700000000",
            email="john.doe@example.com",
        )

        # Create ServiceProvider
        self.service_provider = ServiceProvider.objects.create(
            name="Test Service Provider",
            code="SP001",
            grp_code="SP001",
            sys_code="SYS001",
        )

        # Create BillingDepartment
        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="Test Department",
            description="This is a test billing department",
            code="DEPT001",
            account_num="1234567890123456",
        )

        # Create RevenueSource
        self.revenue_source = RevenueSource.objects.create(
            name="Revenue Source 1",
            gfs_code="GFS001",
            category="Category A",
            sub_category="Sub-category A1",
        )

        # Create RevenueSourceItem
        self.revenue_source_item = RevenueSourceItem.objects.create(
            rev_src=self.revenue_source,
            description="Revenue Source Item 1",
            amt=1000.00,
            currency="TZS",
        )

    def test_valid_currency_tzs(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.department,
            currency="TZS",
            amt=1000,
        )
        self.assertEqual(bill.currency, "TZS")

    def test_valid_currency_usd(self):
        bill = Bill.objects.create(
            customer=self.customer,
            dept=self.department,
            currency="USD",
            amt=1000,
        )
        self.assertEqual(bill.currency, "USD")

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            Bill.objects.create(
                customer=self.customer,
                dept=self.department,
                currency="EUR",  # Invalid currency
                amt=1000,
            )


class BillPostingTestCase(LiveServerTestCase):
    def setUp(self):
        # Set up Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920x1080")

        # Set up Selenium WebDriver (Chrome)
        self.browser = webdriver.Chrome(options=chrome_options)
        self.browser.maximize_window()

        # Get the custom User model
        User = get_user_model()

        # Create a test user and authenticate
        self.user = User.objects.create_user(
            email="testuser@example.com", password="password"
        )

        # Verify user creation
        if not User.objects.filter(email="testuser@example.com").exists():
            raise Exception("User creation failed.")

        # Log in using Django's test client
        login_success = self.client.login(
            email="testuser@example.com", password="password"
        )
        if not login_success:
            raise Exception(
                "Login failed, check user credentials or test client setup."
            )

        # Check for the sessionid cookie
        if "sessionid" not in self.client.cookies:
            raise Exception("Sessionid cookie not found, ensure user is logged in.")

        # Get the client's session cookie and add it to Selenium
        cookie = self.client.cookies["sessionid"]
        self.browser.get(
            self.live_server_url
        )  # Load a page to set the domain for cookies
        self.browser.add_cookie(
            {
                "name": "sessionid",
                "value": cookie.value,
                "path": "/",
            }
        )

        # Create the test environment with necessary data
        # Create Customer
        self.customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            cell_num="255700000000",
            email="john.doe@example.com",
        )

        # Create ServiceProvider
        self.service_provider = ServiceProvider.objects.create(
            name="Test Service Provider",
            code="SP19917",
            grp_code="SP19917",
            sys_code="TNIMR002",
        )

        # Create BillingDepartment
        self.billing_dept = BillingDepartment.objects.create(
            service_provider=self.service_provider,
            name="NIMR HQ",
            description="National Institute for Medical Research, Headquarters",
            code="CC1003029398740",
            account_num="1234567890123456",
        )

        # Create RevenueSource
        self.revenue_source = RevenueSource.objects.create(
            name="Ethical clearance fee",
            gfs_code="140101",
            category="Intellectual Property Products",
            sub_category="Research and Development",
        )

        # Create RevenueSourceItem
        self.revenue_source_item = RevenueSourceItem.objects.create(
            rev_src=self.revenue_source,
            description="Ordinary Proposal (Expedited Review) for Tanzanian Collaborators",
            amt=1100000.00,
            currency="TZS",
        )

    def fill_bill_form(self, currency="TZS"):
        # Open the browser and navigate to the Bill creation page
        self.browser.get(f"{self.live_server_url}/bill/create/")

        # Optional sleep to ensure page has time to load (debugging only)
        time.sleep(5)  # You can adjust or remove this after testing

        # Take a screenshot before failure (for debugging purposes)
        self.browser.save_screenshot("before_error.png")

        # Wait until the form loads
        WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.NAME, "description"))
        )

        # Fill in the form
        self.browser.find_element(By.NAME, "description").send_keys(
            "Test Bill Description"
        )
        self.browser.find_element(By.NAME, "dept").send_keys(
            self.billing_dept.pk
        )  # Select billing department
        self.browser.find_element(By.NAME, "customer").send_keys(
            self.customer.pk
        )  # Select customer
        self.browser.find_element(By.NAME, "currency").send_keys(currency)

        # Select currency (valid or invalid)
        currency_dropdown = self.browser.find_element(By.NAME, "currency")
        currency_dropdown.send_keys(currency)

        # Add a bill item
        self.browser.find_element(By.NAME, "billitem_set-0-dept").send_keys(
            self.billing_dept.pk
        )  # Select bill item billing department
        self.browser.find_element(By.NAME, "billitem_set-0-rev_src_itm").send_keys(
            self.revenue_source_item.pk
        )

        # Submit the form
        submit_button = self.browser.find_element(
            By.CSS_SELECTOR, "button[type='submit']"
        )
        submit_button.click()

    def test_invalid_currency(self):
        # Fill the form with invalid currency (e.g., 'EUR' which is not allowed)
        self.fill_bill_form(currency="EUR")

        # Wait for the error message (invalid currency should trigger form error)
        # WebDriverWait(self.browser, 10).until(
        #     EC.presence_of_element_located((By.CLASS_NAME, "errorlist"))
        # )

        # Take a screenshot of the error page
        self.browser.save_screenshot("invalid_currency_error.png")

        # Debugging: Print the page source
        print(self.browser.page_source)

        # Verify that the form has an error related to invalid currency
        # error_message = self.browser.find_element(By.CLASS_NAME, "errorlist").text
        # self.assertIn("Select a valid choice", error_message)

    def tearDown(self):
        self.browser.quit()
