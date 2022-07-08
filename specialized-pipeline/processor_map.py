"""
Contains a Map between Specialized Processor Types and Specialized Classifier Output
"""


def invert_dictionary_with_array(dictionary: dict):
    """
    Inverts a dictionary with arrays as values
    e.g. {key: [value1, value2]} -> {value1: key, value2: key}
    """
    inv_map = {}
    for key, array in dictionary.items():
        for value in array:
            inv_map[value] = key
    return inv_map


# Processors that Split & Classify
CLASSIFIER_PROCESSOR_TYPES = set(
    ["PROCUREMENT_DOCUMENT_SPLIT_PROCESSOR", "LENDING_DOCUMENT_SPLIT_PROCESSOR"]
)

# Map Processor Type to Classifier Output
PROCESSOR_SUPPORTED_DOCUMENT_TYPES = {
    # Default for all non-classified documents
    "FORM_PARSER_PROCESSOR": ["other"],
    # Procurement Processors
    "UTILITY_PROCESSOR": ["utility_statement"],
    "INVOICE_PROCESSOR": ["debit_note", "credit_note", "invoice_statement"],
    "EXPENSE_PROCESSOR": [
        "credit_card_slip",
        "restaurant_statement",
        "air_travel_statement",
        "hotel_statement",
        "car_rental_statement",
        "ground_transportation_statement",
        "receipt_statement",
    ],
    "PURCHASE_ORDER_PROCESSOR": ["purchase_order"],
    # Lending Processors
    "BANK_STATEMENT_PROCESSOR": ["account_statement_bank"],
    "FORM_1040SCH_C_PROCESSOR": [
        "1040sc",
        "1040sc_2018",
        "1040sc_2019",
        "1040sc_2020",
        "1040sc_2021",
    ],
    "FORM_1040_PROCESSOR": ["1040", "1040_2018", "1040_2019", "1040_2020", "1040_2021"],
    "FORM_1099DIV_PROCESSOR": [
        "1099div",
        "1099div_2018",
        "1099div_2019",
        "1099div_2020",
        "1099div_2021",
    ],
    "FORM_1099INT_PROCESSOR": [
        "1099int",
        "1099int_2018",
        "1099int_2019",
        "1099int_2020",
        "1099int_2021",
    ],
    "FORM_1099MISC_PROCESSOR": [
        "1099misc",
        "1099misc_2018",
        "1099misc_2019",
        "1099misc_2020",
        "1099misc_2021",
    ],
    "FORM_1099NEC_PROCESSOR": [
        "1099nec",
        "1099nec_2018",
        "1099nec_2019",
        "1099nec_2020",
        "1099nec_2021",
    ],
    "FORM_1099R_PROCESSOR": [
        "1099r",
        "1099r_2018",
        "1099r_2019",
        "1099r_2020",
        "1099r_2021",
    ],
    "FORM_W2_PROCESSOR": ["w2", "w2_2018", "w2_2019", "w2_2020", "w2_2021"],
    "FORM_W9_PROCESSOR": ["w9", "w9_2017", "w9_2018", "w9_2019", "w9_2020", "w9_2021"],
    "MORTGAGE_STATEMENT_PROCESSOR": ["mortgage_statements"],
    "PAYSTUB_PROCESSOR": ["payslip"],
    "RETIREMENT_INVESTMENT_STATEMENT_PROCESSOR": [
        "account_statement_investment_and_retirement"
    ],
    "FORM_1003_PROCESSOR": ["1003", "1003_2009"],
    "FORM_F11_12956_PROCESSOR": ["f11_12956_2017"],
    "FORM_1099G_PROCESSOR": [
        "1099g",
        "1099g_2018",
        "1099g_2019",
        "1099g_2020",
        "1099g_2021",
    ],
    "FORM_1040SCH_B_PROCESSOR": [
        "1099sb",
        "1099sb_2018",
        "1099sb_2019",
        "1099sb_2020",
        "1099sb_2021",
    ],
    "FORM_1040SCH_D_PROCESSOR": [
        "1099sd",
        "1099sd_2018",
        "1099sd_2019",
        "1099sd_2020",
        "1099sd_2021",
    ],
    "FORM_1040SCH_E_PROCESSOR": [
        "1099se",
        "1099se_2018",
        "1099se_2019",
        "1099se_2020",
        "1099se_2021",
    ],
    "FORM_SSA1099_PROCESSOR": [
        "1099ssa",
        "1099ssa_2018",
        "1099ssa_2019",
        "1099ssa_2020",
        "1099ssa_2021",
    ],
    "FORM_1065_PROCESSOR": [
        "1065",
        "1065_2018",
        "1065_2019",
        "1065_2020",
        "1065_2021",
    ],
    "FORM_1120_PROCESSOR": [
        "1120",
        "1120_2018",
        "1120_2019",
        "1120_2020",
        "1120_2021",
    ],
    "FORM_1120S_PROCESSOR": [
        "1120s",
        "1120s_2018",
        "1120s_2019",
        "1120s_2020",
        "1120s_2021",
    ],
    "FORM_SSA89_PROCESSOR": [
        "ssa_89",
        "ssa_89_2018",
        "ssa_89_2019",
        "ssa_89_2020",
        "ssa_89_2021",
    ],
    "FORM_VBA26_0551_PROCESSOR": ["vba_26_0551_2004"],
    "FORM_VBA26_8923_PROCESSOR": ["vba_26_8923_2021"],
    "FORM_HUD54114_PROCESSOR": ["hud_54114"],
    "FORM_HUD92900B_PROCESSOR": ["hud_92900b"],
    "FORM_HUD92900WS_PROCESSOR": ["hud_92900ws"],
    "FORM_HUD92800_PROCESSOR": ["hud_92800"],
    "FORM_HUD92900A_PROCESSOR": ["hud_92900a"],
    "FORM_USDA_AD3030_PROCESSOR": ["usda_ad_3030"],
    "PROPERTY_INSURANCE_PROCESSOR": ["property_insurance"],
    "FORM_1040NR_PROCESSOR": [
        "1040nr",
        "1040nr_2018",
        "1040nr_2019",
        "1040nr_2020",
        "1040nr_2021",
    ],
    "FORM_1040SR_PROCESSOR": [
        "1040sr",
        "1040sr_2018",
        "1040sr_2019",
        "1040sr_2020",
        "1040sr_2021",
    ],
    "FORM_4506T_PROCESSOR": [
        "4506_T",
        "4506_T_2018",
        "4506_T_2019",
        "4506_T_2020",
        "4506_T_2021",
    ],
    "FORM_4506T_EZ_PROCESSOR": [
        "4506_T_EZ",
        "4506_T_EZ_2018",
        "4506_T_EZ_2019",
        "4506_T_EZ_2020",
        "4506_T_EZ_2021",
    ],
    "FORM_1076_PROCESSOR": ["1076_2016"],
    "FORM_UCC1_PROCESSOR": ["ucc_financing_statement"],
    "FORM_HUD92900LT_PROCESSOR": ["hud_92900lt"],
    "FORM_HUD92051_PROCESSOR": ["hud_92051"],
    "FORM_1005_PROCESSOR": ["1005_1996"],
    "FORM_FLOOD_CERTIFICATE_PROCESSOR": ["dhs_flood_certification"],
    "FORM_HUD92544_PROCESSOR": ["hud_92544"],
    "FORM_PUD_RIDER_PROCESSOR": ["pud_rider"],
    "FORM_CONDOMINIUM_RIDER_PROCESSOR": ["3140_Condominium_Rider"],
    "FORM_ADJUSTABLE_RIDER_PROCESSOR": ["3108_Adjustable_Rate_Rider"],
    "FORM_FAMILY_RIDER_PROCESSOR": ["1_4_Family_Rider_3170"],
    "FORM_BALLOON_RIDER_PROCESSOR": ["3190_Balloon_Rider"],
    "FORM_SECOND_HOME_RIDER_PROCESSOR": ["3890_Second_Home_Rider"],
    "FORM_HUD92541_PROCESSOR": ["hud_92541"],
    "FORM_REVOCABLE_TRUST_RIDER_PROCESSOR": ["revocable_trust_rider"],
    "FORM_USDA_CONDITIONAL_COMMITMENT_PROCESSOR": ["usda_ad_3030"],
    # Identity Processors (Classified using Lending Classifier)
    "US_DRIVER_LICENSE_PROCESSOR": ["us_driver_license"],
    "US_PASSPORT_PROCESSOR": ["us_passport"],
}

DOCUMENT_SUPPORTED_PROCESSOR_TYPES = invert_dictionary_with_array(
    PROCESSOR_SUPPORTED_DOCUMENT_TYPES
)
