import psycopg2
import os
from dotenv import load_dotenv
import json
import openai
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt
from termcolor import colored
import logging
from datetime import datetime

# Constants and Environment Variables
GPT_MODEL = 'gpt-3.5-turbo-0613'
openai.api_key = os.getenv("OPENAI_API_KEY")
load_dotenv()

# PostgreSQL Connection Setup
host = os.getenv("HOST")
port = os.getenv("PORT")
database = os.getenv("SEMANTIC_DB")
username = os.getenv("POSTGRES_USERNAME")
password = os.getenv("POSTGRES_PASSWORD")
postgres_connection = psycopg2.connect(host=host, port=port, dbname=database, user=username, password=password)
postgres_connection.set_session(autocommit=True)

# Check PostgreSQL connection status
if postgres_connection.closed == 0:
    print(f"Connected successfully to {database} database\nConnection Details: {postgres_connection.dsn}")
else:
    raise ConnectionError("Unable to connect to the database")

# Fetching PostgreSQL Schema Details
def get_schema_names(database_connection):
    cursor = database_connection.cursor()
    cursor.execute("SELECT schema_name FROM information_schema.schemata;")
    schema_names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return schema_names

def get_table_names(connection, schema_name):
    cursor = connection.cursor()
    cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_name}';")
    table_names = [table[0] for table in cursor.fetchall()]
    cursor.close()
    return table_names

def get_column_names(connection, table_name, schema_name):
    cursor = connection.cursor()
    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = '{schema_name}';")
    column_names = [col[0] for col in cursor.fetchall()]
    cursor.close()
    return column_names

def get_database_info(connection, schema_names):
    table_dicts = []
    for schema in schema_names:
        for table_name in get_table_names(connection, schema):
            column_names = get_column_names(connection, table_name, schema)
            table_dicts.append({"table_name": table_name, "column_names": column_names, "schema_name": schema})
    return table_dicts



# To print details to the console:
# schemas = get_schema_names(postgres_connection)
schemas = ['prod', 'dev']
database_schema_dict = get_database_info(postgres_connection, schemas)
database_schema_string = "\n".join(
    [
        f"Schema: {table['schema_name']}\nTable: {table['table_name']}\nColumns: {', '.join(table['column_names'])}"
        for table in database_schema_dict
    ]
)

functions = [
    {
        "name": "ask_postgres_database",
        "description": "Use this function to answer user questions about the database. Output should be a fully formed SQL query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": f"""
                            SQL query extracting info to answer the user's question.
                            SQL should be written using this database schema:
                            {database_schema_string}
                            The query should be returned in plain text, not in JSON.
                            """,
                }
            },
            "required": ["query"],
        },
    }
]




class Functions:
    def __init__(self):
        self.functions = functions