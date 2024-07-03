import base64
import uuid
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from django.utils import timezone


def load_private_key(pfx_file, password):
    with open(pfx_file, "rb") as f:
        pfx_data = f.read()
    private_key, certificate, additional_certificates = (
        pkcs12.load_key_and_certificates(pfx_data, password.encode())
    )
    return private_key


def sign_payload(payload, private_key):
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def generate_request_id():
    """
    Generate a unique request ID for the bill control number request.
    """

    return str(uuid.uuid4())


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
    coll_cent_code_element.text = "YourCollectionCenterCode"

    bill_desc_element = SubElement(bill_dtl_element, "BillDesc")
    bill_desc_element.text = str(bill_obj.description)

    cust_tin_element = SubElement(bill_dtl_element, "CustTin")
    cust_tin_element.text = str(bill_obj.customer.tin)

    cust_id_element = SubElement(bill_dtl_element, "CustId")
    cust_id_element.text = str(bill_obj.customer.id_num)

    cust_id_type_element = SubElement(bill_dtl_element, "CustIdType")
    cust_id_type_element.text = str(bill_obj.customer.id_type)

    cust_accnt_element = SubElement(bill_dtl_element, "CustAccnt")
    cust_accnt_element.text = str(bill_obj.customer.account_num)

    cust_name_element = SubElement(bill_dtl_element, "CustName")
    cust_name_element.text = str(bill_obj.customer.get_name)

    cust_cell_num_element = SubElement(bill_dtl_element, "CustCellNum")
    cust_cell_num_element.text = str(bill_obj.customer.cell_num)

    cust_email_element = SubElement(bill_dtl_element, "CustEmail")
    cust_email_element.text = str(bill_obj.customer.email)

    bill_gen_dt_element = SubElement(bill_dtl_element, "BillGenDt")
    bill_gen_dt_element.text = str(bill_obj.gen_date.strftime("%Y-%m-%dT%H:%M:%S"))

    bill_expr_dt_element = SubElement(bill_dtl_element, "BillExprDt")
    bill_expr_dt_element.text = str(bill_obj.expr_date.strftime("%Y-%m-%dT%H:%M:%S"))

    bill_gen_by_element = SubElement(bill_dtl_element, "BillGenBy")
    bill_gen_by_element.text = "YourBillGenerator"

    bill_appr_by_element = SubElement(bill_dtl_element, "BillApprBy")
    bill_appr_by_element.text = "YourBillApprover"

    bill_amt_element = SubElement(bill_dtl_element, "BillAmt")
    bill_amt_element.text = str(bill_obj.amt)

    bill_eqv_amt_element = SubElement(bill_dtl_element, "BillEqvAmt")
    bill_eqv_amt_element.text = str(bill_obj.eqv_amt)

    min_pay_amt_element = SubElement(bill_dtl_element, "MinPayAmt")
    min_pay_amt_element.text = str(bill_obj.min_pay_amt)

    ccy_element = SubElement(bill_dtl_element, "Ccy")
    ccy_element.text = "TZS"

    exch_rate_element = SubElement(bill_dtl_element, "ExchRate")
    exch_rate_element.text = "1.00"

    bill_pay_opt_element = SubElement(bill_dtl_element, "BillPayOpt")
    bill_pay_opt_element.text = "1"

    bill_pay_plan_element = SubElement(bill_dtl_element, "BillPayPlan")
    bill_pay_plan_element.text = "1"

    bill_pay_lim_typ_element = SubElement(bill_dtl_element, "BillPayLimTyp")
    bill_pay_lim_typ_element.text = "1"

    bill_pay_lim_amt_element = SubElement(bill_dtl_element, "BillPayLimAmt")
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
        gfs_code_element.text = str(item.rev_src.gfs_code)

        bill_item_ref_element = SubElement(bill_item_element, "BillItemRef")
        bill_item_ref_element.text = "YourBillItemRef"

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
    payload_str = tostring(gepg_element, encoding="utf-8")

    # Sign the payload
    signature = sign_payload(payload_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Return the final XML payload as a string
    return tostring(gepg_element, encoding="utf-8")


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
    payload_str = tostring(gepg_element, encoding="utf-8")

    # Sign the payload
    signature = sign_payload(payload_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Return the XML payload as a string
    return tostring(gepg_element, encoding="utf-8")


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
    payload_str = tostring(gepg_element, encoding="utf-8")

    # Sign the payload
    signature = sign_payload(payload_str, private_key)

    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = signature

    # Return the XML payload as a string
    return tostring(gepg_element, encoding="utf-8")


def compose_bill_reconciliation_request_payload(req_id, sp_grp_code, sys_code, trxDt):
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
    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = "SignatureGoesHere"

    # Return the XML payload as a string
    return tostring(gepg_element, encoding="utf-8")


def compose_bill_reconciliation_response_acknowledgement_payload(
    ack_id, res_id, ack_sts_code
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
    # Add signature element
    signature_element = SubElement(gepg_element, "signature")
    signature_element.text = "SignatureGoesHere"

    # Return the XML payload as a string
    return tostring(gepg_element, encoding="utf-8")


def parse_acknowledgement_response(response_data):
    """
    Parse the initial acknowledgement response received from the Payment Gateway API.
    """

    try:
        # Parse the XML response data
        root = ET.fromstring(response_data)

        # Extract relevant information from the response
        ack_id = root.findtext("billSubReqAck/AckId")
        req_id = root.findtext("billSubReqAck/ReqId")
        ack_sts_code = root.findtext("billSubReqAck/AckStsCode")
        ack_sts_desc = root.findtext("billSubReqAck/AckStsDesc")

        return req_id, ack_sts_code, ack_sts_desc

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing acknowledgement response: {}".format(str(e)))


def parse_final_response(response_data):
    """
    Parse the final response received from the Payment Gateway API.
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

        return res_id, req_id, bill_id, cust_cntr_num, res_sts_code, res_sts_desc

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

        # Extract relevant information from the response
        req_id = root.find(".//ReqId").text
        bill_id = root.find(".//GrpBillId").text
        cntr_num = root.find(".//CustCntrNum").text
        psp_code = root.find(".//PspCode").text
        psp_name = root.find(".//PspName").text
        trx_id = root.find(".//TrxId").text
        payref_id = root.find(".//PayRefId").text
        bill_amt = root.find(".//BillAmt").text
        paid_amt = root.find(".//PaidAmt").text
        paid_ccy = root.find(".//Ccy").text
        coll_acc_num = root.find(".//CollAccNum").text
        trx_date = root.find(".//TrxDtTm").text
        pay_channel = root.find(".//UsdPayChnl").text
        trdpty_trx_id = root.find(".//TrdPtyTrxId").text
        pyr_cell_num = root.find(".//PyrCellNum").text
        pyr_email = root.find(".//PyrEmail").text
        pyr_name = root.find(".//PyrName").text

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
    """

    try:
        # parse the XML response data
        root = ET.fromstring(response_data)
        # Extract relevant information from the response
        res_id = root.find(".//ResId").text
        req_id = root.find(".//ReqId").text
        sp_grp_code = root.find(".//SpGrpCode").text
        sys_code = root.find(".//SysCode").text
        pay_sts_code = root.find(".//PayStsCode").text
        pay_sts_desc = root.find(".//PayStsDesc").text
        pmt_dtls = []
        pmt_trx_dtls = root.findall(".//PmtTrxDtl")
        for pmt_trx_dtl in pmt_trx_dtls:
            cust_cntr_num = pmt_trx_dtl.find(".//CustCntrNum").text
            grp_bill_id = pmt_trx_dtl.find(".//GrpBillId").text
            sp_code = pmt_trx_dtl.find(".//SpCode").text
            bill_id = pmt_trx_dtl.find(".//BillId").text
            bill_ctr_num = pmt_trx_dtl.find(".//BillCtrNum").text
            psp_code = pmt_trx_dtl.find(".//PspCode").text
            psp_name = pmt_trx_dtl.find(".//PspName").text
            trx_id = pmt_trx_dtl.find(".//TrxId").text
            pay_ref_id = pmt_trx_dtl.find(".//PayRefId").text
            bill_amt = pmt_trx_dtl.find(".//BillAmt").text
            paid_amt = pmt_trx_dtl.find(".//PaidAmt").text
            bill_pay_opt = pmt_trx_dtl.find(".//BillPayOpt").text
            ccy = pmt_trx_dtl.find(".//Ccy").text
            coll_acc_num = pmt_trx_dtl.find(".//CollAccNum").text
            trx_dt_tm = pmt_trx_dtl.find(".//TrxDtTm").text
            usd_pay_chnl = pmt_trx_dtl.find(".//UsdPayChnl").text
            trdpty_trx_id = pmt_trx_dtl.find(".//TrdPtyTrxId").text
            pyr_cell_num = pmt_trx_dtl.find(".//PyrCellNum").text
            pyr_email = pmt_trx_dtl.find(".//PyrEmail").text
            pyr_name = pmt_trx_dtl.find(".//PyrName").text
            pmt_dtls.append(
                {
                    "cust_cntr_num": cust_cntr_num,
                    "grp_bill_id": grp_bill_id,
                    "sp_code": sp_code,
                    "bill_id": bill_id,
                    "bill_ctr_num": bill_ctr_num,
                    "psp_code": psp_code,
                    "psp_name": psp_name,
                    "trx_id": trx_id,
                    "pay_ref_id": pay_ref_id,
                    "bill_amt": bill_amt,
                    "paid_amt": paid_amt,
                    "bill_pay_opt": bill_pay_opt,
                    "ccy": ccy,
                    "coll_acc_num": coll_acc_num,
                    "trx_dt_tm": trx_dt_tm,
                    "usd_pay_chnl": usd_pay_chnl,
                    "trdpty_trx_id": trdpty_trx_id,
                    "pyr_cell_num": pyr_cell_num,
                    "pyr_email": pyr_email,
                    "pyr_name": pyr_name,
                }
            )

        return {
            "res_id": res_id,
            "req_id": req_id,
            "sp_grp_code": sp_grp_code,
            "sys_code": sys_code,
            "pay_sts_code": pay_sts_code,
            "pay_sts_desc": pay_sts_desc,
            "pmt_dtls": pmt_dtls,
        }

    except Exception as e:
        # If parsing fails, raise an exception
        raise Exception("Error parsing reconciliation response: {}".format(str(e)))
