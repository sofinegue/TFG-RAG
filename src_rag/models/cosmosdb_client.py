"""
CosmosDB Client for storing and retrieving chunks with embeddings
"""

import os
import uuid
from typing import Dict, List, Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from config import config

#TODO Should Import a Dynamic Chunk Model?


class CosmosDBClient:
    def __init__(self):
        # Initialize Cosmos client
        self.client = CosmosClient(
            url=config.cosmosdb_endpoint,
            credential=config.cosmosdb_key
        )
        self.database_name = config.cosmosdb_database
        self.container_name = config.cosmosdb_container

        # Ensure database & container exist
        self.database = self._create_database_if_not_exists()
        self.container = self._create_container_if_not_exists()

    def _create_database_if_not_exists(self):
        try:
            return self.client.create_database_if_not_exists(self.database_name)
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error creating database {self.database_name}: {e}")
            raise

    def _create_container_if_not_exists(self):
        try:
            return self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/chunk_id"),
                offer_throughput=400
            )
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error creating container {self.container_name}: {e}")
            raise

    def upsert_chunk(self, chunk: Dict) -> None:
        """
        Insert or update a chunk in CosmosDB
        """
        if "chunk_id" not in chunk:
            chunk["chunk_id"] = str(uuid.uuid4())
        self.container.upsert_item(chunk)

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict]:
        """
        Retrieve a chunk by ID
        """
        try:
            return self.container.read_item(item=chunk_id, partition_key=chunk_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def query_chunks(self, query: str, top: int = 10) -> List[Dict]:
        """
        Run a SQL-style query against CosmosDB
        """
        items = list(self.container.query_items(
            query=f"SELECT TOP {top} * FROM c WHERE CONTAINS(c.content, @q)",
            parameters=[{"name": "@q", "value": query}],
            enable_cross_partition_query=True
        ))
        return items

    def delete_chunk(self, chunk_id: str) -> None:
        """
        Delete a chunk by ID
        """
        try:
            self.container.delete_item(item=chunk_id, partition_key=chunk_id)
        except exceptions.CosmosResourceNotFoundError:
            pass


# Singleton client
cosmos_client = CosmosDBClient()