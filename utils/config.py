import os 
import openai
from dotenv import load_dotenv


load_dotenv()


# Set up Postgres database credentials
db_credentials = {
    'dbname'    :   os.getenv("SEMANTIC_DB"),
    'user'      :   os.getenv("POSTGRES_USERNAME"),
    'password'  :   os.getenv("POSTGRES_PASSWORD"),
    'host'      :   os.getenv("HOST"),
    'port'      :   os.getenv("PORT")
}


# Set up OpenAI variables 
openai.api_key  =   os.getenv("OPENAI_API_KEY")
AI_MODEL        =   'gpt-3.5-turbo-16k'
