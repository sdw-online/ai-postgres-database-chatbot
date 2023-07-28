# Importing necessary libraries
import os
import json
import openai
import psycopg2
import requests
import tiktoken
import streamlit as st
from dotenv import load_dotenv
from utils.system_prompts import get_final_system_prompt
from tenacity import retry, wait_random_exponential, stop_after_attempt

from utils.system_prompts import get_final_system_prompt
from utils.api_functions import send_api_request_to_openai_api
from utils.chat_functions import run_chat_sequence, clear_chat_history, count_tokens, prepare_sidebar_data
from utils.database_functions import get_schema_names, get_table_names, get_database_info, ask_postgres_database, postgres_connection



@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def send_api_request_to_openai_api(messages, functions=None, function_call=None, model=AI_MODEL, openai_api_key=os.getenv("OPENAI_API_KEY")):
    """ Send the API request to the OpenAI API via Chat Completions  """
    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {openai_api_key}"}
        json_data = {"model": model, "messages": messages}
        if functions: 
            json_data.update({"functions": functions})
        if function_call: 
            json_data.update({"function_call": function_call})
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=json_data)
        response.raise_for_status()

        return response
    
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to connect to OpenAI API due to: {e}")


def execute_function_call(message):
    """ Run the function call provided by OpenAI's API response """
    if message["function_call"]["name"] == "ask_postgres_database":
        query = json.loads(message["function_call"]["arguments"])["query"]
        print(f"SQL query: {query} \n")
        results = ask_postgres_database(postgres_connection, query)
        print(f"Results A: {results} \n")
    else:
        results = f"Error: function {message['function_call']['name']} does not exist"
    return results

