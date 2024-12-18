import pandas as pd
import torch
import pickle
from sentence_transformers import SentenceTransformer
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Custom function to load the pickle file with CPU mapping for Torch tensors
def load_books_data(file_path):
    # Open the pickle file
    with open(file_path, 'rb') as f:
        # Load the pickle data with map_location to CPU for torch tensors
        data = pickle.load(f)

        # Iterate through each column to check if it's a torch tensor and move it to CPU
        for col in data.columns:
            if isinstance(data[col].iloc[0], torch.Tensor):  # If it's a tensor
                # Ensure that any tensors are moved to CPU
                data[col] = data[col].apply(lambda x: x.cpu() if isinstance(x, torch.Tensor) else x)
    
    return data

# Load the data and ensure SBERT embeddings are on CPU
books_data = load_books_data("books_data_cpu.pkl")

# Check if the embeddings are correctly loaded (optional)
print(books_data.head())  # Check the loaded data

# Load BM25 model from the pickle file (ensure any tensor objects are on CPU)
with open("bm25_model.pkl", "rb") as bm25_file:
    bm25 = pickle.load(bm25_file)

# Load SBERT model
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')

# BM25 Search Function
def bm25_search(query, top_n=10):
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)
    top_indices = scores.argsort()[-top_n:][::-1]
    return books_data.iloc[top_indices]

# SBERT Search Function
def sbert_search(query, top_n=10):
    query_embedding = sbert_model.encode(query, convert_to_tensor=True)
    cos_scores = torch.nn.functional.cosine_similarity(query_embedding, torch.stack(books_data['sbert_embedding'].to_list()))
    top_results = torch.topk(cos_scores, k=top_n)
    top_indices = top_results.indices.tolist()
    return books_data.iloc[top_indices]

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "")
    method = data.get("method", "bm25")

    if not query:
        return jsonify({"error": "Please provide a query."})

    # Perform search based on method chosen
    if method == "bm25":
        results = bm25_search(query)
    else:
        results = sbert_search(query)

    # Convert results to JSON format
    response = results[['title', 'authors', 'average_rating']].to_dict(orient="records")
    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True)
