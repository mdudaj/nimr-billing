import base64
import functools
import logging
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring

import qrcode
import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from django.template.loader import get_template
from django.utils import timezone
from django_weasyprint.utils import django_url_fetcher
from PIL import Image
from weasyprint import HTML

logger = logging.getLogger(__name__)


def clean_data(value):
    """
    Clean the input value by stripping leading/trailing whitespace or newline characters.
    If the value is not a string, it is returned as-is.
    """
    if isinstance(value, str):
        return value.strip()
    return value


def generate_qr_code(data, logo_path=None):
    """
    Generate a QR code image for the provided data.
    """
    # Create a QR code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Create the QR code image
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Overlay the QR code image with a logo image if provided
    if logo_path:
        # Open the logo image
        img_logo = Image.open(logo_path)

        # Calculate the size of the logo image
        qr_size = img_qr.size[0]
        logo_size = int(qr_size * 0.3)  # 30% of the QR code size

        # Resize the logo image
        img_logo = img_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Calculate the position to place the logo image
        pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)

        # Overlay the logo image on the QR code image
        img_qr.paste(img_logo, pos, mask=img_logo)

    # Save the QR code image to a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img_qr.save(temp_file, format="PNG")
    temp_file.close()  # Close the file so WeasyPrint can access it

    return temp_file.name


def custom_url_fetcher(url, *args, **kwargs):
    # Rewrite requests for CDN URLs to file path in STATIC_ROOT to use local file
    cloud_storage_url = "https://cdnjs.cloudflare.com/ajax/libs/semantic-ui/2.2.4/"
    if url.startswith(cloud_storage_url):
        # Replace the CDN URL with a local file path in STATIC_ROOT or STATIC_URL
        # with your local file path "/static/semantic-ui/semantic.min.css"

        # Extract the relative path of the file from the CDN URL
        file_path = url.replace(cloud_storage_url, "")

        # Build the full file path using STATIC_ROOT (for local files)
        local_file_path = os.path.join(settings.STATIC_ROOT, "semantic-ui", file_path)

        # Convert the file path to a URL by prefixing it with "file://" scheme
        url = f"file://{local_file_path}"

    # Return the modified URL
    return django_url_fetcher(url, *args, **kwargs)


def generate_pdf(bill_obj, template_name, base_url):
    """
    Generate a PDF file for the bill object.
    """

    # Get the template for the bill
    template = get_template(f"billing/bill/{template_name}")

    logo = settings.STATIC_ROOT + "/img/coat-of-arms-of-tanzania.png"

    # Render the template with the bill object
    html = template.render({"bill": bill_obj, "logo": logo})

    # Create a PDF file from the HTML
    pdf = HTML(string=html, base_url=base_url).write_pdf()

    return pdf


def select_billing_email_recipients(bill, payer_email=None):
    """Return (recipients, suppression_reason).

    Defaults are conservative: customer email only; payer email disabled unless enabled.
    """

    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    recipients = []

    customer_email = getattr(getattr(bill, "customer", None), "email", None)
    customer_email = (customer_email or "").strip()
    payer_email = (payer_email or "").strip()

    def _is_valid(email):
        if not email:
            return False
        try:
            validate_email(email)
        except ValidationError:
            return False
        return True

    if getattr(settings, "BILLING_EMAIL_DELIVERY_CUSTOMER_ENABLED", True) and _is_valid(
        customer_email
    ):
        recipients.append(customer_email)

    if getattr(settings, "BILLING_EMAIL_DELIVERY_PAYER_ENABLED", False) and _is_valid(
        payer_email
    ):
        # Conservative default: only allow payer email when it matches customer email.
        if payer_email and payer_email == customer_email:
            recipients.append(payer_email)
        else:
            return recipients, "payer_email_not_allowed_by_policy"

    recipients = sorted(set(recipients))
    if recipients:
        return recipients, None

    if customer_email and not _is_valid(customer_email):
        return [], "invalid_customer_email"

    return [], "no_recipient_email"


def generate_invoice_pdf_bytes(bill):
    """Generate invoice PDF bytes using the existing transfer printout template."""

    from django.contrib.staticfiles.storage import staticfiles_storage

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

    template = get_template("billing/printout/bill_transfer_print_pdf.html")
    html = template.render(
        {
            "image_path": logo_path,
            "qr_code_path": qr_code_path,
            "bill": bill,
            "print_date": timezone.now().strftime("%d-%m-%Y"),
        }
    )

    stylesheets = [settings.STATIC_ROOT + "/css/bill_transfer_print.css"]
    return HTML(
        string=html,
        base_url=settings.STATIC_ROOT,
        url_fetcher=custom_url_fetcher,
    ).write_pdf(stylesheets=stylesheets)


def generate_receipt_pdf_bytes(payment):
    """Generate receipt PDF bytes using the existing receipt printout template."""

    from django.contrib.staticfiles.storage import staticfiles_storage

    logo_path = staticfiles_storage.path("img/coat-of-arms-of-tanzania.png")
    template = get_template("billing/printout/bill_receipt_print_pdf.html")
    html = template.render(
        {
            "image_path": logo_path,
            "bill_rcpt": payment,
        }
    )

    stylesheets = [settings.STATIC_ROOT + "/css/bill_receipt_print.css"]
    return HTML(
        string=html,
        base_url=settings.STATIC_ROOT,
        url_fetcher=custom_url_fetcher,
    ).write_pdf(stylesheets=stylesheets)


def load_private_key(pfx_file, password):
    with open(pfx_file, "rb") as f:
        pfx_data = f.read()
    private_key, certificate, additional_certificates = (
        pkcs12.load_key_and_certificates(pfx_data, password.encode())
    )
    return private_key


def sign_payload(payload, private_key):
    # Ensure the payload is a byte string
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Sign the payload with the private key using PKCS1v15 padding and SHA-256 hashing algorithm
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def generate_request_id():
    """
    Generate a unique request ID for the bill control number request.
    """

    return str(uuid.uuid4())


def xml_to_dict(xml_str):
    """
    Convert an XML string to a dictionary.
    """
    root = ET.fromstring(xml_str)
    return {root.tag: _element_to_dict(root)}


def _element_to_dict(element):
    """
    Convert an XML element to a dictionary.
    """
    dict_ = {}
    # Include the element's attributes
    dict_.update(element.attrib)

    # Include the element's text content if it's not empty
    if element.text and element.text.strip():
        dict_["text"] = element.text.strip()

    # Process child elements
    for child in element:
        child_dict = _element_to_dict(child)
        if child.tag in dict_:
            if not isinstance(dict_[child.tag], list):
                dict_[child.tag] = [dict_[child.tag]]
            dict_[child.tag].append(child_dict)
        else:
            dict_[child.tag] = child_dict

    return dict_


def compose_bill_control_number_request_payload(
    req_id, bill_obj, sp_grp_code, sp_code, sub_sp_code, sp_sys_id, private_key
):
    """
    Compose the XML payload for the bill control number request based on the provided Bill object.
    """

    # Create the root element
    gepg_element = Element("Gepg")

    # Create the billSubReq element
    bill_sub_req_element = SubElement(gepg_element, "billSubReq")

    # Create the BillHdr element
    bill_hdr_element = SubElement(bill_sub_req_element, "BillHdr")

    # Add ReqId to BillHdr
    req_id_element = SubElement(bill_hdr_element, "ReqId")
    req_id_element.text = str(req_id)

    # Add other mandatory fields to BillHdr
    sp_code_element = SubElement(bill_hdr_element, "SpGrpCode")
    sp_code_element.text = str(sp_grp_code)

    sys_code_element = SubElement(bill_hdr_element, "SysCode")
    sys_code_element.text = str(sp_sys_id)

    bill_typ_element = SubElement(bill_hdr_element, "BillTyp")
    bill_typ_element.text = str(bill_obj.type)

    pay_typ_element = SubElement(bill_hdr_element, "PayTyp")
    pay_typ_element.text = str(bill_obj.pay_type)

    grp_bill_id_element = SubElement(bill_hdr_element, "GrpBillId")
    grp_bill_id_element.text = str(bill_obj.grp_bill_id)

    # Create the BillDtls element
    bill_dtls_element = SubElement(bill_sub_req_element, "BillDtls")

    # Create the BillDtl element
    bill_dtl_element = SubElement(bill_dtls_element, "BillDtl")

    # Add fields to BillDtl
    bill_id_element = SubElement(bill_dtl_element, "BillId")
    bill_id_element.text = str(bill_obj.bill_id)

    sp_code_element = SubElement(bill_dtl_element, "SpCode")
    sp_code_element.text = str(sp_code)

    coll_cent_code_element = SubElement(bill_dtl_element, "CollCentCode")
    coll_cent_code_element.text = str(bill_obj.dept.code)

    bill_desc_element = SubElement(bill_dtl_element, "BillDesc")
    bill_desc_element.text = str(bill_obj.description)

    cust_tin_element = SubElement(bill_dtl_element, "CustTin")
    cust_tin_element.text = str(bill_obj.customer.tin)

    cust_id_element = SubElement(bill_dtl_element, "CustId")
    cust_id_element.text = str(bill_obj.customer.id_num)

    cust_id_type_element = SubElement(bill_dtl_element, "CustIdTyp")
    cust_id_type_element.text = str(bill_obj.customer.id_type)

    cust_accnt_element = SubElement(bill_dtl_element, "CustAccnt")
    cust_accnt_element.text = str(bill_obj.customer.account_num)

    cust_name_element = SubElement(bill_dtl_element, "CustName")
    cust_name_element.text = str(bill_obj.customer.get_name())

    cust_cell_num_element = SubElement(bill_dtl_element, "CustCellNum")
    cust_cell_num_element.text = str(bill_obj.customer.cell_num)

    cust_email_element = SubElement(bill_dtl_element, "CustEmail")
    cust_email_element.text = str(bill_obj.customer.email)

    bill_gen_dt_element = SubElement(bill_dtl_element, "BillGenDt")
    bill_gen_dt_element.text = str(bill_obj.gen_date.strftime("%Y-%m-%dT%H:%M:%S"))

    bill_expr_dt_element = SubElement(bill_dtl_element, "BillExprDt")
    bill_expr_dt_element.text = str(bill_obj.expr_date.strftime("%Y-%m-%dT%H:%M:%S"))

    bill_gen_by_element = SubElement(bill_dtl_element, "BillGenBy")
    bill_gen_by_element.text = str(bill_obj.gen_by)

    bill_appr_by_element = SubElement(bill_dtl_element, "BillApprBy")
    bill_appr_by_element.text = str(bill_obj.appr_by)

    bill_amt_element = SubElement(bill_dtl_element, "BillAmt")
    bill_amt_element.text = str(bill_obj.amt)

    bill_eqv_amt_element = SubElement(bill_dtl_element, "BillEqvAmt")
    bill_eqv_amt_element.text = str(bill_obj.eqv_amt)

    min_pay_amt_element = SubElement(bill_dtl_element, "MinPayAmt")
    min_pay_amt_element.text = str(bill_obj.min_amt)

    ccy_element = SubElement(bill_dtl_element, "Ccy")
    ccy_element.text = str(bill_obj.currency)

    exch_rate_element = SubElement(bill_dtl_element, "ExchRate")
    exch_rate_element.text = "1.00"

    bill_pay_opt_element = SubElement(bill_dtl_element, "BillPayOpt")
    bill_pay_opt_element.text = "1"

    bill_pay_plan_element = SubElement(bill_dtl_element, "PayPlan")
    bill_pay_plan_element.text = "1"
    # bill_pay_plan_element.text = str(bill_obj.pay_plan)

    bill_pay_lim_typ_element = SubElement(bill_dtl_element, "PayLimTyp")
    bill_pay_lim_typ_element.text = "1"
    # bill_pay_lim_typ_element.text = str(bill_obj.pay_lim_type)

    bill_pay_lim_amt_element = SubElement(bill_dtl_element, "PayLimAmt")
    bill_pay_lim_amt_element.text = "0.00"

    coll_psp_element = SubElement(bill_dtl_element, "CollPsp")
    coll_psp_element.text = ""

    # Create the BillItems element
    bill_items_element = SubElement(bill_dtl_element, "BillItems")

    # Iterate over BillItem objects related to the bill and add them to BillItems
    for item in bill_obj.billitem_set.all():
        bill_item_element = SubElement(bill_items_element, "BillItem")

        # Add fields for each BillItem
        ref_bill_id_element = SubElement(bill_item_element, "RefBillId")
        ref_bill_id_element.text = str(item.bill.bill_id)

        sub_sp_code_element = SubElement(bill_item_element, "SubSpCode")
        sub_sp_code_element.text = str(sub_sp_code)

        gfs_code_element = SubElement(bill_item_element, "GfsCode")
        gfs_code_element.text = str(item.rev_src_itm.rev_src.gfs_code)

        bill_item_ref_element = SubElement(bill_item_element, "BillItemRef")
        bill_item_ref_element.text = str(item.rev_src_itm.rev_src.name)

        use_item_ref_on_pay_element = SubElement(bill_item_element, "UseItemRefOnPay")
        use_item_ref_on_pay_element.text = (
            str(item.ref_on_pay) if item.ref_on_pay else "N"
        )

        bill_item_amt_element = SubElement(bill_item_element, "BillItemAmt")
        bill_item_amt_element.text = str(item.amt)

        bill_item_eqv_amt_element = SubElement(bill_item_element, "BillItemEqvAmt")
        bill_item_eqv_amt_element.text = str(item.eqv_amt)

        coll_sp_element = SubElement(bill_item_element, "CollSp")
        coll_sp_element.text = str(sp_code)

    # Convert the XML to a string
    bill_sub_req_str = tostring(
        bill_sub_req_element, encoding="utf-8", method="xml"
    ).decode("utf-8")

    # Sign the payload
    signature = sign_payload(bill_sub_req_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def compose_acknowledgement_response_payload(ack_id, res_id, ack_sts_code, private_key):
    """
    Compose the XML payload for the acknowledgement response based on the provided parameters.
    """

    # Create the root element
    gepg_element = Element("Gepg")

    # Create the billSubResAck element
    bill_sub_res_ack_element = SubElement(gepg_element, "billSubResAck")

    # Add AckId to billSubResAck
    ack_id_element = SubElement(bill_sub_res_ack_element, "AckId")
    ack_id_element.text = str(ack_id)

    # Add ResId to billSubResAck
    res_id_element = SubElement(bill_sub_res_ack_element, "ResId")
    res_id_element.text = str(res_id)

    # Add AckStsCode to billSubResAck
    ack_sts_code_element = SubElement(bill_sub_res_ack_element, "AckStsCode")
    ack_sts_code_element.text = str(ack_sts_code)

    # Convert the XML to a string
    bill_sub_res_ack_str = tostring(
        bill_sub_res_ack_element, encoding="utf-8", method="xml"
    ).decode("utf-8")

    # Sign the payload
    signature = sign_payload(bill_sub_res_ack_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def compose_payment_response_acknowledgement_payload(
    ack_id, req_id, ack_sts_code, private_key
):
    """
    Compose the XML payload for the payment response acknowledgement based on the provided parameters.
    """
    # Create the root element
    gepg_element = Element("Gepg")

    # Create the pmtSpNtfReqAck element
    pmt_sp_ntf_req_ack_element = SubElement(gepg_element, "pmtSpNtfReqAck")

    # Add AckId to pmtSpNtfReqAck
    ack_id_element = SubElement(pmt_sp_ntf_req_ack_element, "AckId")
    ack_id_element.text = str(ack_id)

    # Add ReqId to pmtSpNtfReqAck
    req_id_element = SubElement(pmt_sp_ntf_req_ack_element, "ReqId")
    req_id_element.text = str(req_id)

    # Add AckStsCode to pmtSpNtfReqAck
    ack_sts_code_element = SubElement(pmt_sp_ntf_req_ack_element, "AckStsCode")
    ack_sts_code_element.text = str(ack_sts_code)

    # Convert the XML to a string
    pmt_sp_ntf_req_ack_element_str = tostring(
        pmt_sp_ntf_req_ack_element, encoding="utf-8"
    )

    # Sign the payload
    signature = sign_payload(pmt_sp_ntf_req_ack_element_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def compose_bill_reconciliation_request_payload(
    req_id, sp_grp_code, sys_code, trxDt, private_key
):
    """
    Compose the XML payload for the reconciliation request based on the provided request ID.
    """
    # Create the root element
    gepg_element = Element("Gepg")
    # Create the sucSpPmtReq element
    suc_sp_pmt_req_element = SubElement(gepg_element, "sucSpPmtReq")
    # Add ReqId to sucSpPmtReq
    req_id_element = SubElement(suc_sp_pmt_req_element, "ReqId")
    req_id_element.text = str(req_id)
    # Add other mandatory fields to sucSpPmtReq
    sp_grp_code_element = SubElement(suc_sp_pmt_req_element, "SpGrpCode")
    sp_grp_code_element.text = str(sp_grp_code)
    sys_code_element = SubElement(suc_sp_pmt_req_element, "SysCode")
    sys_code_element.text = str(sys_code)
    trxDt_element = SubElement(suc_sp_pmt_req_element, "TrxDt")
    trxDt_element.text = str(trxDt)
    # Add optional fields to sucSpPmtReq
    rsv1_element = SubElement(suc_sp_pmt_req_element, "Rsv1")
    rsv2_element = SubElement(suc_sp_pmt_req_element, "Rsv2")
    rsv3_element = SubElement(suc_sp_pmt_req_element, "Rsv3")

    # Convert the XML to a string
    suc_sp_pmt_req_element_str = tostring(suc_sp_pmt_req_element, encoding="utf-8")

    # Sign the payload
    signature = sign_payload(suc_sp_pmt_req_element_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def compose_bill_reconciliation_response_acknowledgement_payload(
    ack_id, res_id, ack_sts_code, private_key
):
    """
    Compose the XML payload for the reconciliation response acknowledgement based on the provided parameters.
    """
    # Create the root element
    gepg_element = Element("Gepg")
    # Create the sucSpPmtResAck element
    suc_sp_pmt_res_ack_element = SubElement(gepg_element, "sucSpPmtResAck")
    # Add AckId to sucSpPmtResAck
    ack_id_element = SubElement(suc_sp_pmt_res_ack_element, "AckId")
    ack_id_element.text = str(ack_id)
    # Add ResId to sucSpPmtResAck
    res_id_element = SubElement(suc_sp_pmt_res_ack_element, "ResId")
    res_id_element.text = str(res_id)
    # Add AckStsCode to sucSpPmtResAck
    ack_sts_code_element = SubElement(suc_sp_pmt_res_ack_element, "AckStsCode")
    ack_sts_code_element.text = str(ack_sts_code)

    # Convert the XML to a string
    suc_sp_pmt_res_ack_element_str = tostring(
        suc_sp_pmt_res_ack_element, encoding="utf-8"
    )

    # Sign the payload
    signature = sign_payload(suc_sp_pmt_res_ack_element_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def parse_bill_control_number_request_acknowledgement(response_data):
    """
    Parse the bill controll number request acknowledgement received from the GEPG API.
    """

    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        ack_id = root.findtext("billSubReqAck/AckId")
        req_id = root.findtext("billSubReqAck/ReqId")
        ack_sts_code = root.findtext("billSubReqAck/AckStsCode")
        ack_sts_desc = root.findtext("billSubReqAck/AckStsDesc")

        return ack_id, req_id, ack_sts_code, ack_sts_desc

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing acknowledgement response: {}".format(str(e)))


def parse_bill_control_number_response(response_data):
    """
    Parse the bill control number response received from the Payment Gateway API.
    """

    try:
        # parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        res_id = root.find(".//ResId").text
        req_id = root.find(".//ReqId").text
        bill_id = root.find(".//GrpBillId").text
        cust_cntr_num = root.find(".//CustCntrNum").text
        res_sts_code = root.find(".//ResStsCode").text
        res_sts_desc = root.find(".//ResStsDesc").text
        bill_sts_code = root.find(".//BillStsCode").text
        bill_sts_desc = root.find(".//BillStsDesc").text

        return (
            res_id,
            req_id,
            bill_id,
            cust_cntr_num,
            res_sts_code,
            res_sts_desc,
            bill_sts_code,
            bill_sts_desc,
        )

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing final response: {}".format(str(e)))


def parse_payment_response(response_data):
    """
    Parse the payment response received from the Payment Gateway API.
    """

    try:
        # parse the XML response data
        root = ET.fromstring(response_data)

        # Helper function to get text or log if element is missing
        def get_text_or_log(element_name, xpath):
            element = root.find(xpath)
            if element is None:
                logger.error(f"Missing element: {element_name}")
                return ""
            return element.text if element.text is not None else ""

        # Extract relevant information from the response
        req_id = get_text_or_log("ReqId", ".//ReqId")
        bill_id = get_text_or_log("GrpBillId", ".//GrpBillId")
        cntr_num = get_text_or_log("CustCntrNum", ".//CustCntrNum")
        psp_code = get_text_or_log("PspCode", ".//PspCode")
        psp_name = get_text_or_log("PspName", ".//PspName")
        trx_id = get_text_or_log("TrxId", ".//TrxId")
        payref_id = get_text_or_log("PayRefId", ".//PayRefId")
        bill_amt = get_text_or_log("BillAmt", ".//BillAmt")
        paid_amt = get_text_or_log("PaidAmt", ".//PaidAmt")
        paid_ccy = get_text_or_log("Ccy", ".//Ccy")
        coll_acc_num = get_text_or_log("CollAccNum", ".//CollAccNum")
        trx_date = get_text_or_log("TrxDtTm", ".//TrxDtTm")
        pay_channel = get_text_or_log("UsdPayChnl", ".//UsdPayChnl")
        trdpty_trx_id = get_text_or_log("TrdPtyTrxId", ".//TrdPtyTrxId")
        pyr_cell_num = get_text_or_log("PyrCellNum", ".//PyrCellNum")
        pyr_email = get_text_or_log("PyrEmail", ".//PyrEmail")
        pyr_name = get_text_or_log("PyrName", ".//PyrName")

        # Convert trx_date to a timezone-aware datetime
        if trx_date:
            trx_date = timezone.make_aware(datetime.fromisoformat(trx_date))

        return (
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

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing payment response: {}".format(str(e)))


def parse_bill_reconciliation_request_acknowledgement(response_data):
    """
    Parse the reconciliation request acknowledgement received from the Payment Gateway API.
    """

    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)
        # Extract relevant information from the response
        ack_id = root.findtext("sucSpPmtReqAck/AckId")
        req_id = root.findtext("sucSpPmtReqAck/ReqId")
        ack_sts_code = root.findtext("sucSpPmtReqAck/AckStsCode")
        ack_sts_desc = root.findtext("sucSpPmtReqAck/AckStsDesc")

        return ack_id, req_id, ack_sts_code, ack_sts_desc

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception(
            "Error parsing reconciliation request acknowledgement: {}".format(str(e))
        )


def parse_bill_reconciliation_response(response_data):
    """
    Parse the reconciliation response received from the Payment Gateway API.
    Clean the extracted data by removing unnecessary whitespace or newline characters.
    """
    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        res_id = clean_data(
            root.find(".//ResId").text if root.find(".//ResId") is not None else ""
        )
        req_id = clean_data(
            root.find(".//ReqId").text if root.find(".//ReqId") is not None else ""
        )
        pay_sts_code = clean_data(
            root.find(".//PayStsCode").text
            if root.find(".//PayStsCode") is not None
            else ""
        )
        pay_sts_desc = clean_data(
            root.find(".//PayStsDesc").text
            if root.find(".//PayStsDesc") is not None
            else ""
        )

        # Extract a list of reconciliation records from the response
        pmt_trx_dtls = []

        for pmt_trx_dtl in root.findall(".//PmtTrxDtl"):
            # Handle each field safely in case it's missing
            pmt_trx_dtl_data = {
                "cust_cntr_num": clean_data(
                    pmt_trx_dtl.find("CustCntrNum").text
                    if pmt_trx_dtl.find("CustCntrNum") is not None
                    else ""
                ),
                "grp_bill_id": clean_data(
                    pmt_trx_dtl.find("GrpBillId").text
                    if pmt_trx_dtl.find("GrpBillId") is not None
                    else ""
                ),
                "sp_code": clean_data(
                    pmt_trx_dtl.find("SpCode").text
                    if pmt_trx_dtl.find("SpCode") is not None
                    else ""
                ),
                "bill_id": clean_data(
                    pmt_trx_dtl.find("BillId").text
                    if pmt_trx_dtl.find("BillId") is not None
                    else ""
                ),
                "bill_ctr_num": clean_data(
                    pmt_trx_dtl.find("BillCtrNum").text
                    if pmt_trx_dtl.find("BillCtrNum") is not None
                    else ""
                ),
                "psp_code": clean_data(
                    pmt_trx_dtl.find("PspCode").text
                    if pmt_trx_dtl.find("PspCode") is not None
                    else ""
                ),
                "psp_name": clean_data(
                    pmt_trx_dtl.find("PspName").text
                    if pmt_trx_dtl.find("PspName") is not None
                    else ""
                ),
                "trx_id": clean_data(
                    pmt_trx_dtl.find("TrxId").text
                    if pmt_trx_dtl.find("TrxId") is not None
                    else ""
                ),
                "payref_id": clean_data(
                    pmt_trx_dtl.find("PayRefId").text
                    if pmt_trx_dtl.find("PayRefId") is not None
                    else ""
                ),
                "bill_amt": float(
                    pmt_trx_dtl.find("BillAmt").text
                    if pmt_trx_dtl.find("BillAmt") is not None
                    else 0.0
                ),
                "paid_amt": float(
                    pmt_trx_dtl.find("PaidAmt").text
                    if pmt_trx_dtl.find("PaidAmt") is not None
                    else 0.0
                ),
                "bill_pay_opt": clean_data(
                    pmt_trx_dtl.find("BillPayOpt").text
                    if pmt_trx_dtl.find("BillPayOpt") is not None
                    else ""
                ),
                "currency": clean_data(
                    pmt_trx_dtl.find("Ccy").text
                    if pmt_trx_dtl.find("Ccy") is not None
                    else ""
                ),
                "coll_acc_num": clean_data(
                    pmt_trx_dtl.find("CollAccNum").text
                    if pmt_trx_dtl.find("CollAccNum") is not None
                    else ""
                ),
                "trx_date": (
                    datetime.fromisoformat(pmt_trx_dtl.find("TrxDtTm").text)
                    if pmt_trx_dtl.find("TrxDtTm") is not None
                    else None
                ),
                "usd_pay_chnl": clean_data(
                    pmt_trx_dtl.find("UsdPayChnl").text
                    if pmt_trx_dtl.find("UsdPayChnl") is not None
                    else ""
                ),
                "trdpty_trx_id": clean_data(
                    pmt_trx_dtl.find("TrdPtyTrxId").text
                    if pmt_trx_dtl.find("TrdPtyTrxId") is not None
                    else ""
                ),
                "qt_ref_id": clean_data(
                    pmt_trx_dtl.find("QtRefId").text
                    if pmt_trx_dtl.find("QtRefId") is not None
                    else ""
                ),
                "pyr_cell_num": clean_data(
                    pmt_trx_dtl.find("PyrCellNum").text
                    if pmt_trx_dtl.find("PyrCellNum") is not None
                    else ""
                ),
                "pyr_email": clean_data(
                    pmt_trx_dtl.find("PyrEmail").text
                    if pmt_trx_dtl.find("PyrEmail") is not None
                    else ""
                ),
                "pyr_name": clean_data(
                    pmt_trx_dtl.find("PyrName").text
                    if pmt_trx_dtl.find("PyrName") is not None
                    else ""
                ),
            }
            pmt_trx_dtls.append(pmt_trx_dtl_data)

        return res_id, req_id, pay_sts_code, pay_sts_desc, pmt_trx_dtls

    except ET.ParseError as e:
        raise Exception(f"XML parsing error: {str(e)}")
    except ValueError as e:
        raise Exception(f"Date format error: {str(e)}")
    except Exception as e:
        raise Exception(f"Error parsing reconciliation response: {str(e)}")


def compose_bill_cancellation_payload(
    req_id, cancl_bill_obj, sp_grp_code, sp_sys_id, private_key
):
    """Compose the XML payload for the bill cancellation request."""

    # Create the root element
    gepg_element = Element("Gepg")

    # Create the billCanclReq element
    bill_cancl_req_element = SubElement(gepg_element, "billCanclReq")

    # Add mandatory fields to billCanclReq
    req_id_element = SubElement(bill_cancl_req_element, "ReqId")
    req_id_element.text = str(req_id)

    sp_grp_code_element = SubElement(bill_cancl_req_element, "SpGrpCode")
    sp_grp_code_element.text = str(sp_grp_code)

    sys_code_element = SubElement(bill_cancl_req_element, "SysCode")
    sys_code_element.text = str(sp_sys_id)

    bill_typ_element = SubElement(bill_cancl_req_element, "BillTyp")
    bill_typ_element.text = "1"

    grp_bill_id_element = SubElement(bill_cancl_req_element, "GrpBillId")
    grp_bill_id_element.text = str(cancl_bill_obj.bill.grp_bill_id)

    cancl_gen_by_element = SubElement(bill_cancl_req_element, "CanclGenBy")
    cancl_gen_by_element.text = "Justine Tibalinda"

    cancl_appr_by_element = SubElement(bill_cancl_req_element, "CanclApprBy")
    cancl_appr_by_element.text = "Justine Tibalinda"

    cancl_reasn_element = SubElement(bill_cancl_req_element, "CanclReasn")
    cancl_reasn_element.text = str(cancl_bill_obj.reason)

    # Convert the XML to a string
    bill_cancl_req_str = tostring(
        bill_cancl_req_element, encoding="utf-8", method="xml"
    ).decode("utf-8")

    # Sign the payload
    signature = sign_payload(bill_cancl_req_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def parse_bill_cancellation_request_acknowledgement(response_data):
    """Parse the bill cancellation request acknowledgement received from the Payment Gateway API."""

    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        ack_id = root.find(".//AckId").text
        req_id = root.find(".//ReqId").text
        ack_sts_code = root.find(".//AckStsCode").text
        ack_sts_desc = root.find(".//AckStsDesc").text

        return ack_id, req_id, ack_sts_code, ack_sts_desc

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception(
            "Error parsing cancellation request acknowledgement: {}".format(str(e))
        )


def parse_bill_cancellation_response(response_data):
    """Parse the bill cancellation response received from the Payment Gateway API."""

    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        res_id = root.find(".//ResId").text
        req_id = root.find(".//ReqId").text
        grp_bill_id = root.find(".//GrpBillId").text
        res_sts_code = root.find(".//CanclStsCode").text
        res_sts_desc = root.find(".//CanclStsDesc").text

        return res_id, req_id, grp_bill_id, res_sts_code, res_sts_desc

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing cancellation response: {}".format(str(e)))


def compose_bill_cancellation_response_acknowledgement_payload(
    ack_id, res_id, ack_sts_code, private_key
):
    """
    Compose the XML payload for the bill cancellation acknowledgement based on the provided parameters.
    """

    # Create the root element
    gepg_element = Element("Gepg")

    # Create the billCanclReqAck element
    bill_cancl_req_ack_element = SubElement(gepg_element, "billCanclReqAck")

    # Add AckId to billCanclReqAck
    ack_id_element = SubElement(bill_cancl_req_ack_element, "AckId")
    ack_id_element.text = str(ack_id)

    # Add ReqId to billCanclReqAck
    res_id_element = SubElement(bill_cancl_req_ack_element, "ResId")
    res_id_element.text = str(res_id)

    # Add AckStsCode to billCanclReqAck
    ack_sts_code_element = SubElement(bill_cancl_req_ack_element, "AckStsCode")
    ack_sts_code_element.text = str(ack_sts_code)

    # Convert the XML to a string
    bill_cancl_req_ack_str = tostring(
        bill_cancl_req_ack_element, encoding="utf-8", method="xml"
    ).decode("utf-8")

    # Sign the payload
    signature = sign_payload(bill_cancl_req_ack_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Convert the whole XML to a string
    payload_str = tostring(gepg_element, encoding="utf-8", method="xml").decode("utf-8")

    # Return the XML payload as a string
    return payload_str


def get_exchange_rate(url: str, currency_code: str):
    """
    Fetches and extracts exchange rate data for a given currency code from the provided URL.

    Args:
        url (str): The URL to fetch the exchange rate data from.
        currency_code (str): The currency code to fetch the exchange rate for.

    Returns:
        tuple: A tuple containing the exchange rate data or None if currency code is not found.
    """
    try:
        # Fetch the html content from the URL
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the table containing the exchange rate data
        table = soup.find("table", id="table1")
        if not table:
            print("Exchange rate data not found.")
            return None

        # Iterate over the rows in the table
        rows = table.find("tbody").find_all("tr")
        for row in rows:
            columns = row.find_all("td")
            if len(columns) < 6:
                continue

            if columns[1].get_text(strip=True) == currency_code:
                # # Exctract the relevant columns: currency, buying, selling, transaction date
                buying = float(columns[2].get_text(strip=True))
                selling = float(columns[3].get_text(strip=True))
                trx_date = columns[5].get_text(strip=True)

                return buying, selling, trx_date

        return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching exchange rate data: {str(e)}")
        return None

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None
