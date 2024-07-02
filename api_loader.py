import os
import yaml

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

def resolve_ref(ref, spec):
    ref_path = ref.split('/')[1:]  # Split the $ref path and skip the initial '#'
    resolved = spec
    for part in ref_path:
        resolved = resolved.get(part, {})
    return resolved

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

def extract_request_body(requestBody, spec):
    concise_request_body = []
    if 'content' in requestBody:
        for content_type, content_details in requestBody['content'].items():
            schema = content_details.get('schema', {})
            properties = extract_properties(schema, spec)
            for prop, prop_desc in properties.items():
                concise_request_body.append(f"{prop}: {prop_desc}")
    return concise_request_body

