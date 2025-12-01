# ai_engine/lib/chroma_helpers.py
import time
import chromadb

def store_memory(memory_collection, text):
    """Stores a piece of text in the ChromaDB long-term memory."""
    if not memory_collection:
        print("Cannot store memory, ChromaDB client not available.")
        return "Memory is not available."
    try:
        # We use the text itself as the document and a timestamped ID.
        doc_id = f"memory_{int(time.time())}"
        memory_collection.add(
            documents=[text],
            ids=[doc_id]
        )
        print(f"Successfully stored memory: '{text}'")
        return f"Okay, I've remembered that: {text}"
    except Exception as e:
        print(f"Error storing memory in ChromaDB: {e}")
        return "I had trouble remembering that."

def retrieve_memories(memory_collection, text, n_results=3):
    """Retrieves the most relevant memories from ChromaDB."""
    if not memory_collection:
        print("Cannot retrieve memories, ChromaDB client not available.")
        return "No memories found."
    try:
        results = memory_collection.query(
            query_texts=[text],
            n_results=n_results
        )
        documents = results.get('documents')
        if documents and documents[0]:
            # Return a formatted string of the top results.
            retrieved = "\n".join([f"- {doc}" for doc in documents[0]])
            print(f"Retrieved memories for prompt '{text}':\n{retrieved}")
            return retrieved
        else:
            return "No relevant memories found."
    except Exception as e:
        print(f"Error retrieving memories from ChromaDB: {e}")
        return "I had trouble accessing my memory."
