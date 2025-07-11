"""
Trigger Training in UI
"""

# pylint: disable=E0401
# pylint: disable=W0613
# pylint: disable=W0718
# pylint: disable=R0914
# pylint: disable=R0801


from collections import defaultdict
import traceback

import functions_framework
from google.api_core.client_options import ClientOptions

# from google.cloud import storage
from google.cloud import documentai_v1beta3 as documentai


def list_documents(client, project_id, processor_id):
    """
    Lists all documents in the processor's dataset.
    """
    dataset_name = (
        f"projects/{project_id}/locations/us/processors/{processor_id}/dataset"
    )
    documents = []
    # Paginated document list
    for document in client.list_documents(dataset=dataset_name):
        documents.append(document)

    return documents


def extract_labels_from_document(document):
    """
    Extracts labels from a document's annotations.
    """
    label_counts = defaultdict(int)

    # Iterate over document's entities or annotations
    for entity in document.entities:
        # Assuming 'entity.type' represents the label
        label = entity.type
        label_counts[label] += 1

        if label == "line_item":
            for prop in entity.properties:
                label_counts[prop.type] += 1

    return label_counts


def get_document(client, dataset_name, doc_id):
    """
    Get document from the dataset
    """
    document_id = documentai.DocumentId()
    document_id.unmanaged_doc_id.doc_id = doc_id

    request = documentai.GetDocumentRequest(
        dataset=dataset_name,
        document_id=document_id,
    )

    # Make the request
    response = client.get_document(request=request)

    return response.document


def get_dataset_schema(client, project_id, processor_id):
    """
    Fetches the dataset schema to get the valid labels.
    """
    dataset_schema_name = f"""projects/{project_id}/locations/us/processors/{processor_id}/
                                dataset/datasetSchema"""
    dataset_schema = client.get_dataset_schema(name=dataset_schema_name)

    valid_labels = {
        prop.name
        for entity_type in dataset_schema.document_schema.entity_types
        for prop in entity_type.properties
        if not prop.property_metadata
    }

    return valid_labels


def get_label_stats(client, project_id, processor_id):
    """
    Fetch label statistics from all documents in the dataset by examining annotations.
    """

    dataset_name = (
        f"projects/{project_id}/locations/us/processors/{processor_id}/dataset"
    )

    valid_labels = get_dataset_schema(client, project_id, processor_id)
    documents = list_documents(client, project_id, processor_id)

    # overall_label_counts = defaultdict(int)
    train_label_count = defaultdict(int)
    test_label_count = defaultdict(int)

    train_count = 0
    test_count = 0

    # Iterate through each document and count the labels
    for document in documents:
        # print(document.dataset_type)
        if str(document.dataset_type) == "DatasetSplitType.DATASET_SPLIT_TRAIN":
            train_count += 1
        elif str(document.dataset_type) == "DatasetSplitType.DATASET_SPLIT_TEST":
            test_count += 1

        document_data = get_document(
            client, dataset_name, document.document_id.unmanaged_doc_id.doc_id
        )
        label_counts = extract_labels_from_document(document_data)

        # Aggregate label counts
        for label, count in label_counts.items():
            if label in valid_labels:
                if str(document.dataset_type) == "DatasetSplitType.DATASET_SPLIT_TRAIN":
                    train_label_count[label] += count
                elif (
                    str(document.dataset_type) == "DatasetSplitType.DATASET_SPLIT_TEST"
                ):
                    test_label_count[label] += count

    return train_label_count, test_label_count, train_count, test_count


def validate_labels(train_label_stats, test_label_stats, train_count, test_count):
    """
    Validate that each label has at least 10 annotations.
    """
    train_failed_annotations = {}
    test_failed_annotations = {}

    if train_count < 10 or test_count < 10:
        print(
            f"""Train Dataset has {train_count} documents
                    and Test dataset has {test_count} documents"""
        )
        print(
            """There must be atleast 10 documents in each
                    of these splits to continue with the training"""
        )
        return False, None

    for label, count in train_label_stats.items():
        if count < 10:
            train_failed_annotations[label] = count

    for label, count in test_label_stats.items():
        if count < 10:
            test_failed_annotations[label] = count

    if len(train_failed_annotations) > 0 or len(test_failed_annotations) > 0:
        return False, {
            "train": train_failed_annotations,
            "test": test_failed_annotations,
        }

    return True, None


def train_processor(client, project_id, processor_id, dataset_name, new_version_name):
    """
    Function to initiate processor training.
    """
    # Define the parent (processor resource name)
    parent = f"projects/{project_id}/locations/us/processors/{processor_id}"

    # Create the train processor version request
    request = documentai.TrainProcessorVersionRequest(
        parent=parent,
        processor_version=documentai.ProcessorVersion(display_name=new_version_name),
    )

    # Trigger the training process
    operation = client.train_processor_version(request=request)

    print(f"Training operation started: {operation.operation.name}")


@functions_framework.http
def process_training_request(request):
    """Cloud Function to trigger training in UI"""
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            location = request_json.get("location")
            processor_id = request_json.get("train_processor_id")
            new_version_name = request_json.get("new_version_name")
        else:
            project_id = request.args.get("project_id")
            location = request.args.get("location")
            processor_id = request.args.get("processor_id")
            new_version_name = request.args.get("new_version_name")

        try:
            dataset_name = f"""projects/{project_id}/locations/
                            {location}/processors/{processor_id}/dataset"""

            # Create Document AI client
            client_options = ClientOptions(
                api_endpoint=f"{location}-documentai.googleapis.com"
            )

            client = documentai.DocumentServiceClient(client_options=client_options)

            # Get label statistics by examining document annotations
            print("Getting dataset and labels statistics for validation...")
            (
                train_label_stats,
                test_label_stats,
                train_count,
                test_count,
            ) = get_label_stats(client, project_id, processor_id)

            # Validate label statistics
            print("Validating dataset and labels criteria before training...")
            status, failed_annotations = validate_labels(
                train_label_stats, test_label_stats, train_count, test_count
            )

            if status:
                # Initiate training if the dataset is valid
                client = documentai.DocumentProcessorServiceClient(
                    client_options=client_options
                )
                train_processor(
                    client, project_id, processor_id, dataset_name, new_version_name
                )
                return {
                    "state:": "SUCCESS",
                    "message": f"Training started for processor {processor_id}",
                }, 200
            print(
                """Dataset doesn't have sufficient documents or
                    some labels do not have sufficient annotations"""
            )
            print("Details:", failed_annotations)

            return {
                "state": "FAILED",
                "message": "Dataset doesn't meet the training criteria",
                "details": failed_annotations,
            }, 400

        except Exception as e:
            print(e)
            return {
                "state": "FAILED",
                "message": f"UNABLE TO COMPLETE BECAUSE {e}, {traceback.format_exc()}",
            }, 500
    except Exception as e:
        print(e)
        return {
            "state": "FAILED",
            "message": "UNABLE TO GET THE NEEDED PARAMETERS TO RUN THE CLOUD FUNCTION",
        }, 400
