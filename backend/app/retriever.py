from app.media_retriever import MediaRetriever

def get_media_retriever(
    embed_model,
    qdrant_client,
    bm25_models,
    bm25_vocabs,
    movie_collection_name,
    tv_collection_name,
):
    return MediaRetriever(
        embed_model=embed_model,
        qdrant_client=qdrant_client,
        bm25_models=bm25_models,
        bm25_vocabs=bm25_vocabs,
        movie_collection_name=movie_collection_name,
        tv_collection_name=tv_collection_name,
    )
