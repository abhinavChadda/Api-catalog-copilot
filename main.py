import os
import marqo
from api_loader import load_openapi_specifications, extract_responses, extract_request_body
from query_processor import preprocess_query, detect_intent, decompose_query
from llm_handler import call_llm

NUM_RESPONSES = 15
BATCH_SIZE = 128

def create_and_index_documents(index_name, endpoints):
    print(f"Creating index '{index_name}'...")
    mq.create_index(index_name)
    print(f"Index '{index_name}' created successfully.")
    
    # Index the endpoints in batches
    print("Indexing the endpoints...")
    try:
        for i in range(0, len(endpoints), BATCH_SIZE):
            batch = endpoints[i:i + BATCH_SIZE]
            response = mq.index(index_name).add_documents(batch, tensor_fields=["summary", "description", "operationId", "requestBody", "tags"])
            print(f"Indexed batch {i // BATCH_SIZE + 1} successfully.")
            if 'errors' in response:
                print("Errors detected in add documents call: " + str(response['errors']))
    except Exception as e:
        print(f"Error indexing documents: {e}")

def search_relevant_apis(sub_query, index_name, num_responses):
    filtered_query = preprocess_query(sub_query)
    intent = detect_intent(sub_query)
    search_query = f"{filtered_query} {intent}"
    try:
        results = mq.index(index_name).search(q=search_query, limit=num_responses)
        return results['hits']
    except Exception as e:
        print(f"Error during search: {e}")
        return []

if __name__ == "__main__":
    directory = input("Enter the directory containing the OpenAPI YAML files (leave empty for current directory): ").strip()
    if not directory:
        directory = os.getcwd()

    specs = load_openapi_specifications(directory)

    print("Extracting endpoint details...")
    endpoints = []
    for spec in specs:
        for path, methods in spec['paths'].items():
            if isinstance(methods, dict):
                for method, details in methods.items():
                    if isinstance(details, dict):
                        concise_responses = extract_responses(details.get('responses', {}), spec)
                        concise_request_body = extract_request_body(details.get('requestBody', {}), spec)
                        endpoint = {
                            'path': path,
                            'method': method,
                            'summary': details.get('summary', ''),
                            'description': details.get('description', ''),
                            'tags': ', '.join(details.get('tags', [])),
                            'responses': str(concise_responses),
                            'operationId': details.get('operationId', ''),
                            'requestBody': str(concise_request_body),
                        }
                        endpoints.append(endpoint)
    print(f"Extracted {len(endpoints)} endpoints.")

    print("Initializing Marqo client...")
    mq = marqo.Client(url='http://localhost:8882')
    print("Marqo client initialized successfully.")

    index_name = "api-endpoints"

    def index_exists(index_name):
        existing_indices = mq.get_indexes()
        return any(index['indexName'] == index_name for index in existing_indices['results'])

    if index_exists(index_name):
        user_input = input(f"Index '{index_name}' exists. Do you want to delete and recreate it? (yes/no): ").strip().lower()
        if user_input == 'yes':
            print(f"Deleting index '{index_name}'...")
            mq.index(index_name).delete()
            print(f"Index '{index_name}' deleted successfully.")
            create_and_index_documents(index_name, endpoints)
        else:
            print("Skipping indexing and moving to search query.")
    else:
        create_and_index_documents(index_name, endpoints)

    while True:
        query = input("Enter your query (or type 'exit' to quit): ").strip()
        if query.lower() == 'exit':
            break
        
        relevant_apis = []
        sub_queries = decompose_query(query)
        for sub_query in sub_queries:
            relevant_apis.extend(search_relevant_apis(sub_query, index_name, NUM_RESPONSES))
        
        # Print the selected APIs before calling the LLM
        print("Selected APIs:")
        for api in relevant_apis:
            print(f"  OperationId: {api['operationId']}")
            print(f"  Summary: {api['summary']}")
            print(f"  Description: {api['description']}")
            print(f"  Path: {api['path']}")
            print(f"  Method: {api['method']}")
            print(f"  Tags: {api['tags']}")
            print(f"  Responses: {api['responses']}")
            print(f"  Request Body: {api['requestBody']}")
            print("-----")
        
        response = call_llm(relevant_apis, query)
        print("LLM Response:")
        print(response)
