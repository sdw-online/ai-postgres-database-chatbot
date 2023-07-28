# 🤖 AI Database Chatbot 🤓

This is an AI chatbot that is able to answer any question about the information stored in a relational database. The chatbot created is plugged into a Postgres database. 



# Tools 📝

* **Streamlit:** For an interactive, user-friendly web-based interface.
* **OpenAI:** The power behind the chatbot's intelligent responses.
* **Postgres:** The database where all the magic data resides.



# Folder Structure 📂

```

│   .env
│   .gitignore
│   app.py
│   README.md
│   requirements.txt
│
├───assets
│   │   dark_theme.py
│   │   light_theme.py
│   │   made_by_sdw.py
│   │
│   └───__pycache__
│           ...
│
├───conversation_history
│       ...
│
└───utils
    │   api_functions.py
    │   chat_functions.py
    │   config.py
    │   database_functions.py
    │   function_calling_spec.py
    │   helper_functions.py
    │   system_prompts.py
    │
    └───__pycache__
            ...

```



# Installation 🛠️ 

1. Clone this repository.
2. Navigate to the directory and install the necessary Python packages with `pip install -r requirements.txt`.
3. Add your database credentials and OpenAI API key in the .env file.

# Running the Chatbot 🏃

1. After setting up, run the command: 

```
streamlit run app.py
```

2. The chatbot UI will open in your default web browser. Engage and enjoy!

# How to use it

* Ask questions - Post questions related to data stored in the database the chatbot is connected to
* Get answers - Enjoy the structured and dynamic answers the chatbot provides  
* Save conversations - Preserve conversations into a markdown file for your future use 



# Contribution 👥

Feel free to make pull requests and add your unique spin to this - insights, feedback and suggestions are also welcome too!
