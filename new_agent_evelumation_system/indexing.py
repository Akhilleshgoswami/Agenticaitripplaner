from dotenv import load_dotenv
from langchain_core import vectorstores
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from filerader import read_multiple_pdf

load_dotenv()

embedding = OpenAIEmbeddings(model="text-embedding-3-large")

vector_store = InMemoryVectorStore(embedding)


DOC_PATHS = ["pdf/climate_change.pdf", "pdf/global_warming.pdf"]

docs = read_multiple_pdf(DOC_PATHS)

text_spitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
all_spilte = text_spitter.split_documents(docs)


vector_store.add_documents(documents=all_spilte)
