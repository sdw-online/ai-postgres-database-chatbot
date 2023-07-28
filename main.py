# Importing necessary libraries
import os
import json
import openai
import psycopg2
import requests
import tiktoken
import streamlit as st
from dotenv import load_dotenv
from assets.system_prompts import get_final_system_prompt
from tenacity import retry, wait_random_exponential, stop_after_attempt



################################################## BACKEND ##################################################



# Load environment variables 
load_dotenv()


# Set up OpenAI variables 
openai.api_key  =   os.getenv("OPENAI_API_KEY")
AI_MODEL        =   'gpt-3.5-turbo-16k'



# Set up Postgres database credentials
db_credentials = {
    'dbname'    :   os.getenv("SEMANTIC_DB"),
    'user'      :   os.getenv("POSTGRES_USERNAME"),
    'password'  :   os.getenv("POSTGRES_PASSWORD"),
    'host'      :   os.getenv("HOST"),
    'port'      :   os.getenv("PORT")
}

# Establish connection with PostgreSQL
try:
    postgres_connection = psycopg2.connect(**db_credentials)
    postgres_connection.set_session(autocommit=True)
except Exception as e:
    raise ConnectionError(f"Unable to connect to the database due to: {e}")



# Create a database cursor to execute PostgreSQL commands
cursor = postgres_connection.cursor()


# Validate the PostgreSQL connection status
if postgres_connection.closed == 0:
    print(f"Connected successfully to {db_credentials['dbname']} database\nConnection Details: {postgres_connection.dsn}")
else:
    raise ConnectionError("Unable to connect to the database")




# Return different information on database objects in Postgres

def get_schema_names(database_connection):
    """ Returns a list of schema names """
    cursor = database_connection.cursor()
    cursor.execute("SELECT schema_name FROM information_schema.schemata;")
    schema_names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return schema_names


def get_table_names(connection, schema_name):
    """ Returns a list of table names """
    cursor = connection.cursor()
    cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_name}';")
    table_names = [table[0] for table in cursor.fetchall()]
    cursor.close()
    return table_names


def get_column_names(connection, table_name, schema_name):
    """ Returns a list of column names """
    cursor = connection.cursor()
    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND table_schema = '{schema_name}';")
    column_names = [col[0] for col in cursor.fetchall()]
    cursor.close()
    return column_names


def get_database_info(connection, schema_names):
    """ Fetches information about the schemas, tables and columns in the database """
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

# Specify function descriptions for OpenAI function calling 
functions = [
    {
        "name": "ask_postgres_database",
        "description": "Use this function to answer user questions about the database. Output should be a fully formed SQL query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": f""" The SQL query that extracts the information that answers the user's question from the Postgres database. Write the SQL in the following schema structure:
                            {database_schema_string}. Write the query in SQL format only, not in JSON. Do not include any line breaks or characters that cannot be executed in Postgres.  
                            """,
                }
            },
            "required": ["query"],
        },
    }
]


def ask_postgres_database(connection, query):
    """ Execute the SQL query provided by OpenAI and return the results """
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        results = str(cursor.fetchall())
        cursor.close()
    except Exception as e:
        results = f"Query failed with error: {e}"
    return results


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



def run_chat_sequence(messages, functions):
    if "live_chat_history" not in st.session_state:
        st.session_state["live_chat_history"] = [{"role": "assistant", "content": "Hello! I'm Andy, how can I assist you?"}]
        # st.session_state["live_chat_history"] = []

    internal_chat_history = st.session_state["live_chat_history"].copy()

    chat_response = send_api_request_to_openai_api(messages, functions)
    assistant_message = chat_response.json()["choices"][0]["message"]
    
    if assistant_message["role"] == "assistant":
        internal_chat_history.append(assistant_message)

    if assistant_message.get("function_call"):
        results = execute_function_call(assistant_message)
        internal_chat_history.append({"role": "function", "name": assistant_message["function_call"]["name"], "content": results})
        internal_chat_history.append({"role": "user", "content": "You are a data analyst - provide personalized/customized explanations on what the results provided means and link them to the the context of the user query using clear, concise words in a user-friendly way. Or answer the question provided by the user in a helpful manner - either way, make sure your responses are human-like and relate to the initial user input. Your answers must not exceed 200 characters"})
        chat_response = send_api_request_to_openai_api(internal_chat_history, functions)
        assistant_message = chat_response.json()["choices"][0]["message"]
        if assistant_message["role"] == "assistant":
            st.session_state["live_chat_history"].append(assistant_message)

    return st.session_state["live_chat_history"][-1]




def clear_chat_history():
    """ Clear the chat history stored in the Streamlit session state """
    del st.session_state["live_chat_history"]
    del st.session_state["full_chat_history"]
    del st.session_state["api_chat_history"]


def count_tokens(text):
    """ Count the total tokens used in a text string """
    if not isinstance(text, str):  
        return 0 
    encoding = tiktoken.encoding_for_model(AI_MODEL)
    total_tokens_in_text_string = len(encoding.encode(text))
    
    return total_tokens_in_text_string


def prepare_sidebar_data(database_schema_dict):
    """ Add a sidebar for visualizing the database schema objects  """
    sidebar_data = {}
    for table in database_schema_dict:
        schema_name = table["schema_name"]
        table_name = table["table_name"]
        columns = table["column_names"]

        if schema_name not in sidebar_data:
            sidebar_data[schema_name] = {}

        sidebar_data[schema_name][table_name] = columns
    return sidebar_data



################################################## FRONTEND ##################################################


    
# Prepare data for the sidebar dropdowns
sidebar_data = prepare_sidebar_data(database_schema_dict)



st.sidebar.markdown("<div class='made_by'>Made by SDW🔋</div>", unsafe_allow_html=True)


made_by_style = '''
<style>
    .made_by {
        position: fixed; 
        bottom: 10px;
        right: 10px;
        font-weight: bold;
        background-color: rgba(0, 0, 0, 0.7);  # adding a slight background for readability
        padding: 5px 10px;
        border-radius: 5px;
    }
</style>
'''

st.markdown(made_by_style, unsafe_allow_html=True)


st.sidebar.title("🔍 Postgres DB Objects Viewer")

# Dropdown for Schema selection
selected_schema = st.sidebar.selectbox("📂 Select a schema", list(sidebar_data.keys()))

# Dropdown for Table selection based on chosen Schema
selected_table = st.sidebar.selectbox("📜 Select a table", list(sidebar_data[selected_schema].keys()))

# Display columns of the chosen table with interactivity using checkboxes
st.sidebar.subheader(f"🔗 Columns in {selected_table}")
for col in sidebar_data[selected_schema][selected_table]:
    is_checked = st.sidebar.checkbox(f"📌 {col}")  # This will return True if checked
    # You can add functionalities based on whether a checkbox is checked or not



# Retrieve the current theme from session state
current_theme = st.session_state.get("theme", "light")
st.markdown(f"<body class='{current_theme}'></body>", unsafe_allow_html=True)

# Add a button to clear the chat/conversation
if st.sidebar.button("Clear Conversation🗑️"):
    clear_chat_history()



dark = '''
<style>
    /* Main App styling */
    .stApp, .stApp .stMarkdown p, .stApp .sidebar .sidebar-content {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Main headers styling */
    .stApp .stMarkdown h1, .stApp .stMarkdown h2, .stApp .stMarkdown h3 {
        color: #FAFAFA;
    }

    /* Sidebar headers styling */
    .stApp .sidebar .stMarkdown h1, .stApp .sidebar .stMarkdown h2, .stApp .sidebar .stMarkdown h3 {
        color: #FAFAFA;
    }

    /* Button styling */
    .stButton>button {
        background-color: #FF4B4B;
        color: #0E1117;
    }

    .stButton>button:hover {
        background-color: #E73232; 
        color: #FAFAFA;
    }

    .stButton>button:active {
        background-color: #262730; 
        color: #FAFAFA;
    }

    /* Other stylings remain the same ... */
</style>
'''

light = '''
<style>
    /* Main App styling */
    .stApp, .stApp .stMarkdown p, .stApp .sidebar .sidebar-content {
        background-color: #FFFFFF;
        color: #31333F;
    }

    /* Main headers styling */
    .stApp .stMarkdown h1, .stApp .stMarkdown h2 {
        color: #666666;
    }

    .stApp .stMarkdown h3 {
        color: #666666; /* Changed to a mid-gray for better visibility */
        background-color: transparent;
        margin: 0; /* Remove margin to blend seamlessly */
        padding: 0; /* Remove padding if any */
    }

    /* Sidebar headers styling */
    .stApp .sidebar .stMarkdown h1, .stApp .sidebar .stMarkdown h2 {
        color: #666666;
    }

    .stApp .sidebar .stMarkdown h3 {
        color: #666666; /* Adjusted to mid-gray for better visibility against white background */
        background-color: #FFFFFF; 
        margin: 0; /* Remove margin to blend seamlessly */
        padding: 0; /* Remove padding if any */
    }

    /* Input and text area styling */
    .stTextInput input, .stTextArea>textarea, .st-chat-inputbox {
        background-color: transparent;
        color: #31333F;
    }

    /* Button styling */
    .stButton>button {
        background-color: #FF4B4B;
        color: #31333F; /* Adjusted this for better visibility */
    }

    .stButton>button:hover {
        background-color: #E73232;
        color: #FFFFFF; /* Adjusted this for better visibility */
    }

    .stButton>button:active {
        background-color: #D62727;
        color: #FFFFFF; /* Adjusted this for better visibility */
    }

    /* Specific class with a long list of concatenated class names */
    .st-bf.st-ck.st-ek.st-el.st-em.st-en.st-cl.st-cn.st-cm.st-co.st-cp.st-b8.st-eo.st-cf.st-bm.st-e6.st-ep.st-eq.st-er.st-es.st-ae.st-af.st-ag.st-be.st-ai.st-aj.st-bx.st-et.st-eu.st-ev.st-am.st-fb {
        background-color: #FFFFFF;
        color: rgba(38, 39, 48, 0.5);
    }

    /* First class with a list of concatenated class names */
    .st-bf.st-b3.st-bl.st-eb.st-bn.st-bo.st-bp.st-bq.st-br.st-bs.st-bt.st-bu.st-ec.st-b1.st-bw.st-bh.st-bi.st-bj.st-bk.st-ed.st-ee.st-ef.st-eg.st-ck.st-eh.st-ei.st-cp {
        color: #31333F;
    }

    /* Chat input container styling */
    .stChatFloatingInputContainer.css-usj992.ehod42b2 {
        background-color: #FFFFFF;
    }

    /* Adjusting background for the specified class */
    .css-nahz7x.eqr7zpz4, .css-k7vsyb.eqr7zpz1 {
        background-color: transparent; /* Making them transparent */
        color: #31333F;
    }

    /* XPath Specific Styling */
    [id="root"] > div:nth-child(1) > div:nth-child(1) > div > div > div > section:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div > div:nth-child(3) > div > div {
        background-color: #FFFFFF;
    }

    [id="root"] > div:nth-child(1) > div:nth-child(1) > div > div > div > section:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div > div:nth-child(1) > div > div:nth-child(4) > div > div,
    [id="root"] > div:nth-child(1) > div:nth-child(1) > div > div > div > section:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div > div:nth-child(1) > div > div:nth-child(1) > div > div {
        color: #31333F;
    }

    [id="root"] > div:nth-child(1) > div:nth-child(1) > div > div > div > section:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div > div:nth-child(6) > div:nth-child(2) > div:nth-child(1) > div > div > div > div {
        color: #31333F;
    }

    /* Other stylings remain the same ... */

</style>
'''



# Initialize the theme in session state
if "theme" not in st.session_state:
    st.session_state.theme = "light"

# Toggle theme on button click
if st.sidebar.button("Toggle Theme🚨"):
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

# Apply the theme based on session state
theme_style = dark if st.session_state.theme == "dark" else light
st.markdown(theme_style, unsafe_allow_html=True)





MAX_TOKENS_ALLOWED      =   3000
MAX_MESSAGES_TO_OPENAI  =   5
TOKEN_BUFFER            =   100  # This is an arbitrary number to provide a buffer to avoid exact token limits


# Add title to the Streamlit chatbot app
st.title("🤖 AI Database Chatbot 🤓")

# Initialize the full chat messages history for UI
if "full_chat_history" not in st.session_state:
    st.session_state["full_chat_history"] = [{"role": "system", "content": get_final_system_prompt(db_credentials=db_credentials)}]


# Initialize the API chat messages history for OpenAI requests
if "api_chat_history" not in st.session_state:
    st.session_state["api_chat_history"] = [{"role": "system", "content": get_final_system_prompt(db_credentials=db_credentials)}]


if (prompt := st.chat_input("What do you want to know?")) is not None:
    st.session_state.full_chat_history.append({"role": "user", "content": prompt})
    
    # Limit the number of messages sent to OpenAI by token count
    total_tokens = sum(count_tokens(message["content"]) for message in st.session_state["api_chat_history"])
    while total_tokens + count_tokens(prompt) + TOKEN_BUFFER > MAX_TOKENS_ALLOWED:
        removed_message = st.session_state["api_chat_history"].pop(0)
        total_tokens -= count_tokens(removed_message["content"])

    st.session_state.api_chat_history.append({"role": "user", "content": prompt})


# Display previous chat messages from full_chat_history (ingore system prompt message)
for message in st.session_state["full_chat_history"][1:]:
    if message["role"] == "user":
        st.chat_message("user", avatar='🧑‍💻').write(message["content"])
    elif message["role"] == "assistant":
        st.chat_message("assistant", avatar='🤖').write(message["content"])

if st.session_state["api_chat_history"][-1]["role"] != "assistant":
    with st.spinner("⌛Connecting to AI model..."):
        # Send only the most recent messages to OpenAI from api_chat_history
        recent_messages = st.session_state["api_chat_history"][-MAX_MESSAGES_TO_OPENAI:]
        new_message = run_chat_sequence(recent_messages, functions)  # Get the latest message
        
        # Add this latest message to both api_chat_history and full_chat_history
        st.session_state["api_chat_history"].append(new_message)
        st.session_state["full_chat_history"].append(new_message)
        
        # Display the latest message from the assistant
        st.chat_message("assistant", avatar='🤖').write(new_message["content"])

    max_tokens = MAX_TOKENS_ALLOWED
    current_tokens = sum(count_tokens(message["content"]) for message in st.session_state["full_chat_history"])
    progress = min(1.0, max(0.0, current_tokens / max_tokens))
    st.progress(progress)
    st.write(f"Tokens Used: {current_tokens}/{max_tokens}")
    if current_tokens > max_tokens:
        st.warning("Note: Due to character limits, some older messages might not be considered in ongoing conversations with the AI.")

