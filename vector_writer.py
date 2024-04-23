import data_cleaner as data_cleaner
import os
import time

from dotenv import load_dotenv
from llama_index.core import Settings, SimpleDirectoryReader
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from pinecone.grpc import PineconeGRPC

load_dotenv('environment.env')

# Globals
Settings.embed_model = OpenAIEmbedding()

# local_directory = "data"
# dummy_session_date = "10/24/2021"
local_directory = "data2"
dummy_session_date = "03/03/2023"

#clean and prep local documents for Pinecone store ingestion
raw_documents = SimpleDirectoryReader(local_directory).load_data()
cleaned_docs = []
for d in raw_documents: 
    cleaned_text = data_cleaner.clean_up_text(d.get_content())
    d.set_content(cleaned_text)
    cleaned_docs.append(d)

# Iterate through `cleaned_docs` and add our new metadata key:value pairs
metadata_additions = {
    "patient": "John Doe",
    "session_date": dummy_session_date
}

 # Update dict in place
[cd.metadata.update(metadata_additions) for cd in cleaned_docs]

# Initialize connection to Pinecone
pc = PineconeGRPC(api_key=os.environ.get('PINECONE_API_KEY'))

index_name = 'patient-john-doe'

# wait for index to be initialized  
while not pc.describe_index(index_name).status['ready']:
    print("sleeping")
    time.sleep(1)

#check index current stats
index = pc.Index(index_name)

# Initialize VectorStore
vector_store = PineconeVectorStore(pinecone_index=index)

# This will be the model we use both for Node parsing and for vectorization
embed_model = OpenAIEmbedding(api_key=os.environ.get('OPENAI_API_KEY'))

# Define the initial pipeline
pipeline = IngestionPipeline(
    transformations=[
        SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95, 
            embed_model=embed_model,
            ),
        embed_model,
        ],
        vector_store=vector_store
    )

# Now we run our pipeline!
pipeline.run(documents=cleaned_docs)