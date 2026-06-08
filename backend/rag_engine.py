import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

# Path where ChromaDB will store its embedded vector files locally
CHROMA_PERSIST_DIR = "./chroma_db"

def initialize_vector_db():
    print("[*] Initializing HuggingFace Embeddings (all-MiniLM-L6-v2)...")
    # Using a fast, highly accurate sentence transformer for embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("[*] Connecting to ChromaDB Vector Store...")
    vector_db = Chroma(
        collection_name="infra_dpr_collection",
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )
    return vector_db

def ingest_mock_dpr_text(vector_db):
    print("\n[*] Simulating ingestion of a massive 500-page Detailed Project Report (DPR)...")
    
    # We simulate a massive, complex engineering document with dense bureaucratic text.
    mock_dpr_content = """
    DETAILED PROJECT REPORT (DPR) - SECTION 4.2: ENVIRONMENTAL IMPACT ASSESSMENT
    The proposed highway alignment passes through 4.5 kilometers of the densely forested buffer zone. 
    However, as of the current date, the Formal Forest Clearance (Stage II) from the Ministry of Environment, 
    Forest and Climate Change (MoEFCC) has not been secured. The contractor is advised to commence work 
    only on the non-forest patches until the clearance is legally obtained.
    
    SECTION 7.1: LAND ACQUISITION STATUS
    Under the NHAI Act, 3G notifications have been published for 92% of the required land. However, physical 
    possession (3H) has only been completed for 65% of the right-of-way. There are massive ongoing farmer protests 
    in Village Y regarding compensation rates, leading to a temporary stay order by the local tribunal.
    
    SECTION 9.3: FINANCIAL ESTIMATES & UTILITIES
    The Schedule of Rates (SoR) used for this budget calculation is based on the 2021 index. Given the current 
    inflationary trends, the steel and cement costs are highly underestimated by approximately 18%. Furthermore, 
    the shifting of the 33kV high-tension electrical transmission line is unbudgeted and remains unplanned.
    """
    
    # Wrap it in a Langchain Document
    doc = Document(page_content=mock_dpr_content, metadata={"source": "Mock_DPR_Project_Alpha.pdf"})
    
    print("[*] Chunking document using RecursiveCharacterTextSplitter...")
    # Split the massive text into smaller, mathematically semantic chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents([doc])
    
    print(f"[*] Generated {len(chunks)} semantic chunks. Embedding into Vector Database...")
    # Add chunks to ChromaDB
    vector_db.add_documents(chunks)
    vector_db.persist()
    print("[*] Document successfully vectorized and persisted to disk! ✅")

def search_risk_factors(vector_db):
    print("\n=========================================")
    print("🔍 RAG ENGINE: RISK FACTOR SEARCH 🔍")
    print("=========================================\n")
    
    queries = [
        "Are there any issues with the forest clearance?",
        "What is the current status of land acquisition?",
        "Is there a risk of financial underestimation or utility shifting issues?"
    ]
    
    for query in queries:
        print(f"\n[USER QUERY]: {query}")
        print("[AI SEARCHING 500-PAGE DOC...]")
        
        # Perform similarity search
        results = vector_db.similarity_search(query, k=1)
        
        for res in results:
            print(f"--> [EXTRACTED EVIDENCE]: {res.page_content.strip()}")
            print(f"--> [SOURCE]: {res.metadata['source']}")

if __name__ == "__main__":
    print("=========================================")
    print("🚀 INFRA-AI RAG VECTOR ENGINE 🚀")
    print("=========================================\n")
    
    db = initialize_vector_db()
    ingest_mock_dpr_text(db)
    search_risk_factors(db)
    
    print("\n=========================================")
    print("🏆 PHASE 3 RAG ENGINE COMPLETE 🏆")
    print("=========================================")
