import os
import logging
import chromadb
from chromadb.utils import embedding_functions
from src import config

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Map keywords to exact scheme names in vector DB
SCHEME_KEYWORD_MAP = {
    "mid-cap": "HDFC Mid-Cap Opportunities Fund",
    "midcap": "HDFC Mid-Cap Opportunities Fund",
    "mid cap": "HDFC Mid-Cap Opportunities Fund",
    "top 100": "HDFC Top 100 Fund",
    "large cap": "HDFC Top 100 Fund",
    "largecap": "HDFC Top 100 Fund",
    "large-cap": "HDFC Top 100 Fund",
    "small cap": "HDFC Small Cap Fund",
    "smallcap": "HDFC Small Cap Fund",
    "small-cap": "HDFC Small Cap Fund",
    "gold etf": "HDFC Gold ETF Fund of Fund",
    "gold fof": "HDFC Gold ETF Fund of Fund",
    "gold fund": "HDFC Gold ETF Fund of Fund",
    "gold": "HDFC Gold ETF Fund of Fund",
    "defence": "HDFC Defence Fund",
    "defense": "HDFC Defence Fund"
}

class SchemeRetriever:
    def __init__(self, db_dir=config.DB_DIR, collection_name=config.CHROMA_COLLECTION_NAME):
        self.db_dir = db_dir
        self.collection_name = collection_name
        
        # Initialize embedding function (runs locally)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Connect to Chroma
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.collection = self.client.get_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )

    def route_query_to_scheme(self, query):
        """
        Scans the query to identify if it references a specific HDFC mutual fund.
        Returns the exact scheme name if matched, otherwise None.
        """
        query_lower = query.lower()
        for keyword, scheme_name in SCHEME_KEYWORD_MAP.items():
            if keyword in query_lower:
                logger.info(f"Retriever: Routed query to scheme '{scheme_name}' based on keyword '{keyword}'")
                return scheme_name
        return None

    def retrieve_context(self, query):
        """
        Retrieves context chunks from ChromaDB.
        Applies metadata filtering if a specific scheme is identified.
        Returns a list of dicts: [{"text": str, "source_url": str, "last_updated": str, "scheme_name": str}]
        """
        scheme_filter = self.route_query_to_scheme(query)
        
        if scheme_filter:
            # Metadata filter: strict retrieval for exactly one fund (k=1)
            logger.info(f"Retriever: Querying ChromaDB with metadata filter: where scheme_name = '{scheme_filter}'")
            results = self.collection.query(
                query_texts=[query],
                n_results=1,
                where={"scheme_name": scheme_filter}
            )
        else:
            # Fallback search: semantic query across all funds (k=2)
            logger.info("Retriever: Querying ChromaDB without filters (k=2 fallback)")
            results = self.collection.query(
                query_texts=[query],
                n_results=2
            )

        contexts = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            
            for doc, meta in zip(docs, metas):
                contexts.append({
                    "text": doc,
                    "source_url": meta.get("source_url", ""),
                    "last_updated": meta.get("last_updated", "N/A"),
                    "scheme_name": meta.get("scheme_name", "")
                })
        
        logger.info(f"Retriever: Fetched {len(contexts)} context chunk(s).")
        return contexts


def test_retriever():
    retriever = SchemeRetriever()
    test_queries = [
        "What is the exit load of HDFC Small Cap?",
        "Who is the manager of HDFC Gold ETF?",
        "What are the tax implications?"
    ]
    
    print("\n--- Retriever Verification Test ---")
    for q in test_queries:
        print(f"Query: '{q}'")
        contexts = retriever.retrieve_context(q)
        for i, ctx in enumerate(contexts):
            print(f"  [{i+1}] Scheme: {ctx['scheme_name']}")
            print(f"      URL: {ctx['source_url']}")
            print(f"      Last Updated: {ctx['last_updated']}")
            print(f"      Content Snippet: {ctx['text'][:150]}...")
        print("-" * 30)

if __name__ == "__main__":
    test_retriever()
