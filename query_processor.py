import re
import nltk
from nltk.corpus import stopwords

# Download NLTK stop words
nltk.download('stopwords')

STOP_WORDS = set(stopwords.words('english'))

def preprocess_query(query):
    query_tokens = query.split()
    filtered_tokens = [token for token in query_tokens if token.lower() not in STOP_WORDS]
    filtered_query = ' '.join(filtered_tokens)
    return filtered_query

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

def decompose_query(query):
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

def construct_api_chain(sub_queries, search_relevant_apis, index_name, num_responses):
    api_chain = []
    for sub_query in sub_queries:
        relevant_apis = search_relevant_apis(sub_query, index_name, num_responses)
        api_chain.append({
            'sub_query': sub_query,
            'relevant_apis': relevant_apis
        })
    return api_chain

