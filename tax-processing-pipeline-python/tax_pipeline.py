# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# type: ignore
"""Tax Processing Functions"""

from decimal import Decimal
from typing import Dict, List, Tuple

_FORM_1099DIV = "FORM_1099DIV"
_FORM_1099INT = "FORM_1099INT"
_FORM_1099MISC = "FORM_1099MISC"
_FORM_1099NEC = "FORM_1099NEC"
_FORM_W2 = "FORM_W2"

# Standard Deduction for Single Filing in 2020
_STANDARD_DEDUCTION = 12400


def calculate_tax_values(data: dict) -> List[List]:
    # pylint: disable=too-many-locals
    """
    Calculate tax values based on extracted data from documents
    """

    form_1099div = data.get(_FORM_1099DIV)
    form_1099int = data.get(_FORM_1099INT)
    form_1099misc = data.get(_FORM_1099MISC)
    form_1099nec = data.get(_FORM_1099NEC)
    form_w2 = data.get(_FORM_W2)

    all_forms = [form_1099div, form_1099int, form_1099misc, form_1099nec, form_w2]

    # Don't continue if no data provided
    if not any(all_forms):
        return []
    # Personal Information
    full_name, ssn, address = get_personal_info(all_forms)

    # Wages, salaries, tips, etc
    line_1 = get_numerical_form_value(form_w2, "WagesTipsOtherCompensation")
    # Taxable interest
    line_2b = get_numerical_form_value(form_1099int, "InterestIncome")
    # Qualified dividends
    line_3a = get_numerical_form_value(form_1099div, "QualifiedDividends")
    # Ordinary dividends
    line_3b = get_numerical_form_value(form_1099div, "TotalOrdinaryDividends")

    # Not used for this demo
    line_4b = 0
    line_5b = 0
    line_6b = 0

    # Capital gain or (loss).
    line_7 = get_numerical_form_value(form_1099div, "TotalCapitalGainDistribution")
    # Other income from Schedule 1, line 9
    line_8 = get_numerical_form_value(
        form_1099nec, "NonemployeeCompensation"
    ) + get_numerical_form_value(form_1099misc, "Rents")

    # Add lines 1, 2b, 3b, 4b, 5b, 6b, 7, and 8
    line_9 = line_1 + line_2b + line_3b + line_4b + line_5b + line_6b + line_7 + line_8

    # total adjustments to income
    line_10c = 0
    #  adjusted gross income
    line_11 = line_9 - line_10c
    # Standard Deduction
    line_12 = _STANDARD_DEDUCTION
    # Qualified business income deduction
    line_13 = 0
    # Add lines 12 and 13
    line_14 = line_12 + line_13
    # Taxable income. Subtract line 14 from line 11. If zero or less, enter -0-
    line_15 = max(0, line_11 - line_14)

    # Tax from Taxable Income
    line_16 = calculate_owed_tax(line_15)
    # Total Tax
    line_24 = line_16
    # Tax Withheld from Form W-2
    line_25a = get_numerical_form_value(form_w2, "FederalIncomeTaxWithheld")
    # Tax Withheld from Form 1099s
    line_25b = (
        get_numerical_form_value(form_1099div, "FederalIncomeTaxWithheld")
        + get_numerical_form_value(form_1099int, "FederalIncomeTaxWithheld")
        + get_numerical_form_value(form_1099misc, "FederalIncomeTaxWithheld")
        + get_numerical_form_value(form_1099nec, "FederalIncomeTaxWithheld")
    )

    # Total Tax Withheld
    line_25d = line_25a + line_25b
    # Total Payments
    line_33 = line_25d

    # FORMAT: Line Number, Comment, Data
    output_1040 = [
        # Headers
        # ["Line Number", "Comment", "Data", "Source"],
        ["", "Full Name", full_name, ""],
        ["", "Social Security Number", ssn, ""],
        ["", "Home address", address, ""],
        ["1", "Wages, salaries, tips, etc.", line_1, _FORM_W2],
        ["2b", "Taxable interest", line_2b, _FORM_1099INT],
        ["3a", "Qualified dividends", line_3a, _FORM_1099DIV],
        ["3b", "Ordinary dividends", line_3b, _FORM_1099DIV],
        ["4b", "IRA distributions, Taxable Amount", line_4b, ""],
        ["5b", "Pensions and annuities, Taxable Amount", line_5b, ""],
        ["7", "Capital gain or (loss)", line_7, _FORM_1099DIV],
        [
            "8",
            "Other income from Schedule 1, line 9",
            line_8,
            f"{_FORM_1099NEC} & {_FORM_1099MISC}",
        ],
        [
            "9",
            "Add lines 1, 2b, 3b, 4b, 5b, 6b, 7, and 8. \
                This is your total income",
            line_9,
            "",
        ],
        ["10c", "Total adjustments to income", line_10c, ""],
        ["11", "Adjusted gross income", line_11, ""],
        ["12", "Standard deduction", line_12, ""],
        ["13", "Qualified business income deduction", line_13, ""],
        ["14", "Add lines 12 and 13", line_14, ""],
        [
            "15",
            "Taxable income. Subtract line 14 from line 11. \
            If zero or less, enter 0",
            line_15,
            "",
        ],
        ["16", "Tax from Taxable Income", line_16, ""],
        ["24", "Total Tax", line_24, ""],
        ["25a", "Tax Withheld from Form W-2", line_25a, _FORM_W2],
        [
            "25b",
            "Tax Withheld from Form 1099(s)",
            line_25b,
            f"{_FORM_1099DIV}, {_FORM_1099INT}, {_FORM_1099NEC}, \
                {_FORM_1099MISC}",
        ],
        ["25d", "Total Tax Withheld", line_25d, ""],
        ["33", "Total Payments", line_33, ""],
    ]

    # If line 33 is more than line 24, subtract line 24 from line 33.
    # This is the amount you overpaid
    if line_33 > line_24:
        line_34 = line_33 - line_24
        output_1040.append(
            [
                "34",
                "If line 33 is more than line 24, subtract line 24 from line 33. \
                This is the amount you overpaid",
                line_34,
            ]
        )
    else:
        # Subtract line 33 from line 24.
        # This is the amount you owe now
        line_37 = line_24 - line_33
        output_1040.append(
            [
                line_37,
                "If line 33 is less than line 24, subtract line 33 from line 24. \
                This is the amount you owe now",
                line_37,
            ]
        )

    return output_1040


def get_personal_info(forms: List[Dict]) -> Tuple[str, str, str]:
    """
    Extract Name, SSN, and address from forms.
    Checks each form to see if it has the information.
    """
    # pylint: disable=line-too-long

    full_name, ssn, address = "", "", ""

    for form in forms:
        if full_name and ssn and address:
            break
        if not form:
            continue
        if not full_name:
            full_name = form.get("EmployeeName", "") or form.get("RecipientName", "")
        if not ssn:
            ssn = form.get("SSN", "") or form.get("RecipientTIN", "")
        if not address:
            # Get Address as a single string
            address = (
                form.get("EmployeeAddress", "")
                or form.get("RecipientAddress", "")
                or f'{form.get("RecipientAddressLine1", "")} {form.get("RecipientAddressLine2", "")}'
                or f'{form.get("RecipientStreetAddress", "")} {form.get("RecipientCityStateCountry", "")}'
            )

    return full_name, ssn, address


def get_numerical_form_value(form: dict, form_key: str) -> Decimal:
    """
    Get the value of a form field as a Decimal.
    Remove $ and , from numbers
    """
    if not form:
        return Decimal()
    raw_value = form.get(form_key, "0")
    clean_value = raw_value.replace("$", "").replace(",", "") or "0"
    return Decimal(clean_value)


def calculate_owed_tax(line_15: Decimal) -> Decimal:
    """
    Calculate Tax Based on 2020 Brackets
    Assumes Filing Single.
    """
    brackets_2020 = [9_875, 40_125, 85_525, 163_300, 207_350, 518_400, -1]
    tax_rates_2020 = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]

    cumulative_tax = Decimal(0)
    subtractive_income = line_15

    for bracket, tax_rate in zip(brackets_2020, tax_rates_2020):
        tax_rate = Decimal(tax_rate)
        bracket = Decimal(bracket)
        if subtractive_income > bracket and bracket != -1:
            cumulative_tax += tax_rate * bracket
            subtractive_income -= bracket
        else:
            cumulative_tax += tax_rate * subtractive_income
            break

    return cumulative_tax.quantize(Decimal("0.01"))
