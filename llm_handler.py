import requests
import json
import pyperclip

def call_llm(relevant_apis, user_question):
    base_prompt = (
        "Given a user input and a set of available APIs in the system, generate a detailed plan to execute a sequence of actions that address and fulfill the user's question. "
        "The plan should include:\n\n"
        "Input Analysis: How to parse and understand the user's input.\n"
        "API Mapping: Identifying relevant APIs that can be used to address the user's request.\n"
        "Sequence Planning: Detailed steps and order of API calls.\n"
        "Error Handling: Plan for handling potential errors or exceptions.\n"
        "Optimization: Suggestions for optimizing the sequence of actions for efficiency.\n\n"
        "Ensure the final plan is clear, actionable, and can be easily implemented by a developer. Use only the APIs provided in the list below to try and answer the question.\n\n"
        f"User Question: {user_question}\n\n"
        "Available APIs:\n"
    )
    
    prompt = base_prompt
    for api in relevant_apis:
        prompt += f"  - OperationId: {api['operationId']}\n"
        prompt += f"    Summary: {api['summary']}\n"
        prompt += f"    Description: {api['description']}\n"
        prompt += f"    Path: {api['path']}\n"
        prompt += f"    Method: {api['method']}\n"
        prompt += f"    Tags: {api['tags']}\n"
        prompt += f"    Responses: {api['responses']}\n"
        prompt += f"    Request Body: {api['requestBody']}\n"
        prompt += "-----\n"

    # Print the generated prompt
    print("Generated Prompt:")
    print(prompt)

    # Copy the generated prompt to clipboard
    pyperclip.copy(prompt)
    print("The prompt has been copied to the clipboard.")

    # Ask the user if they want to use the LLM
    use_llm = input("Do you want to use the LLM to generate the sequence? (yes/no): ").strip().lower()
    if use_llm != 'yes':
        return "LLM call skipped by the user."

    url = "http://localhost:11434/api/generate"
    data = {
        "model": "llama3",
        "prompt": prompt
    }

    response_text = ""

    try:
        with requests.post(url, json=data, stream=True) as response:
            response.raise_for_status()
            print("Streaming response:")
            for line in response.iter_lines():
                if line:
                    response_json = line.decode('utf-8')
                    response_data = json.loads(response_json)
                    response_part = response_data.get("response", "")
                    response_text += response_part
                    print(response_part, end="", flush=True)
                    if response_data.get("done"):
                        break
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while calling the LLM: {e}")

    return response_text
