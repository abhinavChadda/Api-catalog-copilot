import os
import yaml
import marqo
import nltk
import re

# Download NLTK stop words
nltk.download('stopwords')
from nltk.corpus import stopwords

# Define stop words
STOP_WORDS = set(stopwords.words('english'))

# Variable to control the number of responses displayed from the database
NUM_RESPONSES = 5

# Function to load all YAML files from the specified directory
def load_openapi_specifications(directory):
    specs = []
    for filename in os.listdir(directory):
        if filename.endswith(".yaml"):
            filepath = os.path.join(directory, filename)
            print(f"Loading OpenAPI specification from {filepath}...")
            with open(filepath) as f:
                spec = yaml.safe_load(f)
                specs.append(spec)
            print(f"OpenAPI specification {filename} loaded successfully.")
    return specs

# Function to resolve $ref references
def resolve_ref(ref, spec):
    ref_path = ref.split('/')[1:]  # Split the $ref path and skip the initial '#'
    resolved = spec
    for part in ref_path:
        resolved = resolved.get(part, {})
    return resolved

# Function to extract properties including handling allOf, $ref, and items
def extract_properties(schema, spec):
    properties = {}
    if 'allOf' in schema:
        for sub_schema in schema['allOf']:
            sub_properties = extract_properties(sub_schema, spec)
            properties.update(sub_properties)
    elif '$ref' in schema:
        resolved_schema = resolve_ref(schema['$ref'], spec)
        properties.update(extract_properties(resolved_schema, spec))
    elif 'properties' in schema:
        for prop, prop_details in schema['properties'].items():
            if isinstance(prop_details, dict):
                if '$ref' in prop_details:
                    resolved_schema = resolve_ref(prop_details['$ref'], spec)
                    sub_properties = extract_properties(resolved_schema, spec)
                    properties.update(sub_properties)
                elif 'items' in prop_details and '$ref' in prop_details['items']:
                    resolved_schema = resolve_ref(prop_details['items']['$ref'], spec)
                    sub_properties = extract_properties(resolved_schema, spec)
                    properties.update(sub_properties)
                else:
                    prop_desc = prop_details.get('description', 'No description')
                    properties[prop] = prop_desc
            elif isinstance(prop_details, list):
                for item in prop_details:
                    if '$ref' in item:
                        resolved_schema = resolve_ref(item['$ref'], spec)
                        sub_properties = extract_properties(resolved_schema, spec)
                        properties.update(sub_properties)
                    else:
                        prop_desc = item.get('description', 'No description')
                        properties[prop] = prop_desc
    return properties

# Function to create and index documents
def create_and_index_documents(indexName, endpoints):
    print(f"Creating index '{indexName}'...")
    mq.create_index(indexName)
    print(f"Index '{indexName}' created successfully.")
    
    # Index the endpoints
    print("Indexing the endpoints...")
    try:
        response = mq.index(indexName).add_documents(endpoints, tensor_fields=["summary", "description", "operationId", "requestBody", "tags"])
        print("New endpoints indexed successfully.")
        if 'errors' in response:
            print("Errors detected in add documents call: " + str(response['errors']))
    except Exception as e:
        print(f"Error indexing documents: {e}")

# Function to extract concise responses information
def extract_responses(responses, spec):
    concise_responses = {}
    for status, details in responses.items():
        concise_responses[status] = []
        if 'content' in details:
            for content_type, content_details in details['content'].items():
                schema = content_details.get('schema', {})
                properties = extract_properties(schema, spec)
                for prop, prop_desc in properties.items():
                    concise_responses[status].append(f"{prop}: {prop_desc}")
    return concise_responses

# Function to extract concise requestBody information
def extract_request_body(requestBody, spec):
    concise_request_body = []
    if 'content' in requestBody:
        for content_type, content_details in requestBody['content'].items():
            schema = content_details.get('schema', {})
            properties = extract_properties(schema, spec)
            for prop, prop_desc in properties.items():
                concise_request_body.append(f"{prop}: {prop_desc}")
    return concise_request_body

# Function to preprocess user query
def preprocess_query(query):
    query_tokens = query.split()
    filtered_tokens = [token for token in query_tokens if token.lower() not in STOP_WORDS]
    filtered_query = ' '.join(filtered_tokens)
    return filtered_query

# Function to detect intent based on keywords and patterns
def detect_intent(query):
    query = query.lower()
    if re.search(r'\b(what|which|who|where|when|how|find|show|get)\b', query):
        return "get"
    elif re.search(r'\b(create|add|make|insert|post|register)\b', query):
        return "create"
    elif re.search(r'\b(update|edit|modify|put|change)\b', query):
        return "update"
    elif re.search(r'\b(delete|remove|erase|cancel|destroy)\b', query):
        return "delete"
    else:
        return "unknown"

# Function to decompose complex queries while preserving context
def decompose_query(query):
    # Preserve the main structure of the query for each part
    parts = re.split(r'\b(and|then|next|after that)\b', query, flags=re.IGNORECASE)
    sub_queries = []
    base_query = ""
    for part in parts:
        part = part.strip()
        if part.lower() in ["and", "then", "next", "after that"]:
            base_query = sub_queries[-1] if sub_queries else query
        else:
            if base_query:
                sub_queries.append(f"{base_query.split()[0]} {part}")
            else:
                sub_queries.append(part)
    return sub_queries

# Function to search for relevant APIs
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

# Function to construct API chain from sub-queries
def construct_api_chain(sub_queries, index_name, num_responses):
    api_chain = []
    for sub_query in sub_queries:
        relevant_apis = search_relevant_apis(sub_query, index_name, num_responses)
        api_chain.append({
            'sub_query': sub_query,
            'relevant_apis': relevant_apis
        })
    return api_chain

# Ask user for the directory containing the OpenAPI YAML files or use current directory as default
directory = input("Enter the directory containing the OpenAPI YAML files (leave empty for current directory): ").strip()
if not directory:
    directory = os.getcwd()

# Load all OpenAPI specifications from the specified directory
specs = load_openapi_specifications(directory)

# Step 1: Extract endpoint details from all specs
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

# Step 2: Initialize Marqo client
print("Initializing Marqo client...")
mq = marqo.Client(url='http://localhost:8882')
print("Marqo client initialized successfully.")

# Index name
index_name = "api-endpoints"

# Check if the index exists
def index_exists(index_name):
    existing_indices = mq.get_indexes()
    return any(index['indexName'] == index_name for index in existing_indices['results'])

# Delete and recreate the index if user confirms
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

# Step 3: Define the search function
def search_endpoints(query):
    print(f"Searching for query: '{query}'")
    sub_queries = decompose_query(query)
    print(f"Decomposed into sub-queries: {sub_queries}")
    api_chain = construct_api_chain(sub_queries, index_name, NUM_RESPONSES)
    return api_chain

# Continuously ask the user for queries and print search results
while True:
    query = input("Enter your query (or type 'exit' to quit): ").strip()
    if query.lower() == 'exit':
        break
    
    api_chain = search_endpoints(query)
    
    print("API Chain:")
    for step in api_chain:
        print(f"Sub-query: {step['sub_query']}")
        for api in step['relevant_apis']:
            print(f"  OperationId: {api['operationId']}")
            print(f"  Summary: {api['summary']}")
            print(f"  Description: {api['description']}")
            print(f"  Path: {api['path']}")
            print(f"  Method: {api['method']}")
            print(f"  Tags: {api['tags']}")
            print(f"  Responses: {api['responses']}")
            print(f"  Request Body: {api['requestBody']}")
            print("-----")
