import os
import json
import logging
import chromadb
from chromadb.utils import embedding_functions

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PARSED_DIR = os.path.join(BASE_DIR, "data", "parsed")
DB_DIR = os.path.join(BASE_DIR, "data", "vector_db")
COLLECTION_NAME = "mutual_funds_faq"

class VectorStoreManager:
    def __init__(self, db_dir=DB_DIR, collection_name=COLLECTION_NAME):
        self.db_dir = db_dir
        self.collection_name = collection_name
        
        # Initialize embedding function (runs locally)
        logger.info("Initializing SentenceTransformerEmbeddingFunction ('all-MiniLM-L6-v2')...")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Initialize Chroma persistent client
        logger.info(f"Connecting to ChromaDB at: {self.db_dir}")
        self.client = chromadb.PersistentClient(path=self.db_dir)
        
        # Get or create collection using cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def ingest_parsed_files(self, parsed_dir=PARSED_DIR):
        """
        Loads parsed JSON files and inserts them into ChromaDB as atomic chunks.
        """
        if not os.path.exists(parsed_dir):
            logger.error(f"Parsed files directory not found: {parsed_dir}")
            return

        json_files = [f for f in os.listdir(parsed_dir) if f.endswith(".json")]
        if not json_files:
            logger.warning("No parsed JSON files found to ingest.")
            return

        documents = []
        metadatas = []
        ids = []

        logger.info(f"Scanning parsed folder. Found {len(json_files)} files.")

        for filename in json_files:
            file_path = os.path.join(parsed_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                summary_text = data.get("summary_text")
                scheme_name = data.get("scheme_name")
                
                if not summary_text or not scheme_name:
                    logger.warning(f"Skipping {filename}: missing summary_text or scheme_name.")
                    continue
                
                slug = filename.replace(".json", "")
                
                # In single-scheme chunking, the document is the complete summary text.
                documents.append(summary_text)
                
                # We enrich the metadata with flat fields (Chroma metadata only supports primitive types)
                meta = {
                    "scheme_name": scheme_name,
                    "amc_name": data.get("amc_name", "HDFC Mutual Fund"),
                    "source_url": data.get("source_url", ""),
                    "fetch_timestamp": data.get("fetch_timestamp", ""),
                    "last_updated": data.get("last_updated", "")
                }
                metadatas.append(meta)
                ids.append(slug)
                logger.info(f"Prepared document: {scheme_name} (ID: {slug})")
                
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")

        if documents:
            logger.info(f"Adding {len(documents)} document(s) to ChromaDB collection '{self.collection_name}'...")
            
            # Use upsert to avoid duplicate key errors on repeated runs
            self.collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info("Ingestion completed successfully.")
        else:
            logger.warning("No valid documents prepared for ingestion.")

    def similarity_search(self, query, k=2):
        """
        Queries ChromaDB for top-K matching documents.
        """
        logger.info(f"Performing vector similarity search for query: '{query}' (k={k})")
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        return results

def main():
    manager = VectorStoreManager()
    manager.ingest_parsed_files()
    
    # Simple verification test
    logger.info("Running verification search...")
    query = "HDFC Mid-Cap exit load"
    results = manager.similarity_search(query, k=1)
    
    if results and results.get("documents") and results["documents"][0]:
        logger.info("Verification Search Result:")
        logger.info(f"ID: {results['ids'][0][0]}")
        logger.info(f"Document:\n{results['documents'][0][0]}")
        logger.info(f"Metadata: {results['metadatas'][0][0]}")
    else:
        logger.error("Verification search returned no results.")

if __name__ == "__main__":
    main()
