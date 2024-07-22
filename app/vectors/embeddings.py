import os

from openai import OpenAI
from portkey_ai import Portkey

from ..api.auth_base_class import AuthManagerBaseClass

EMBEDDING_MODEL = "text-embedding-3-small"

def create_embeddings(auth_manager: AuthManagerBaseClass,
                      text: str):
    if auth_manager.is_monitoring_proxy_reachable():
        portkey = Portkey(
            api_key=os.environ.get("PORTKEY_API_KEY"),
            virtual_key=os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
        )

        query_data = portkey.embeddings.create(
            encoding_format='float',
            input=text,
            model=EMBEDDING_MODEL
        ).data
        embeddings = []
        for item in query_data:
            embeddings.extend(item.embedding)
        return embeddings
    else:
        openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = openai_client.embeddings.create(input=[text],
                                                   model=EMBEDDING_MODEL)
        embeddings = []
        for item in response.dict()['data']:
            embeddings.extend(item['embedding'])
        return embeddings
