import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
llm = ChatOpenAI(model="gpt-4o", api_key=api_key, temperature=0)
