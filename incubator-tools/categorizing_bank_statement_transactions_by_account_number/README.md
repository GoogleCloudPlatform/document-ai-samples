# Purpose and Description

This document guides to categorize the transactions for each account number from the bank statement parsed json.

## Input Details

* **gcs_input_path**: Input GCS path which contains bank statement parser JSON files.
* **gcs_output_path**: GCS path to store post processed(JSON) results.

## Output Details

<table>
    <tr>
        <td><b>Bank Statement parser output entity type Before post processing</b></td>
        <td><b>After post processing</b></td>
    </tr>
    <tr>
        <td>account_number</td>
        <td>account_0_number<br>account_1_number  ..etc</td>
    </tr>
    <tr>
        <td>account_type</td>
        <td>account_0_name<br>account_1_name   ..etc</td>
    </tr>
    <tr>
        <td>starting_balance</td>
        <td>account_0_beggining_balance<br>account_1_beggining_balance  ..etc</td>
    </tr>
    <tr>
        <td>ending_balance</td>
        <td>account_0_ending_balance<br>account_1_ending_balance  ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_deposit_date</td>
        <td>account_0_transaction/deposit_date<br>account_1_transaction/deposit_date  ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_deposit_description</td>
        <td>account_0_transaction/deposit_description<br>account_1_transaction/deposit_description ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_deposit</td>
        <td>account_0_transaction/deposit<br>account_1_transaction/deposit  ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_withdrawal_date</td>
        <td>account_0_transaction/withdrawal_date<br>account_1_transaction/withdrawal_date  ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_withdrawal_description</td>
        <td>account_0_transaction/withdrawal_description<br>account_1_transaction/withdrawal_description ..etc</td>
    </tr>
    <tr>
        <td>table_item/transaction_withdrawal</td>
        <td>account_0_transaction/withdrawal<br>account_1_transaction/withdrawal ..etc</td>
    </tr>
    <tr>
        <td>table_item</td>
        <td>account_0_trasaction<br>account_1_transaction  ..etc</td>
    </tr>
    </table>
