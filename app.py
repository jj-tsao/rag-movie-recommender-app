from src.chatbot import build_chat_fn
from src.setup import setup_retriever
from src.ui import create_interface


def main():
    # Persistent Qdrant connection and RAG retriever
    retriever = setup_retriever()

    # Build chat function with retriever injected
    chat_fn = build_chat_fn(retriever)

    # Create and launch UI
    demo = create_interface(chat_fn)
    demo.launch(inbrowser=True, debug=True, share=False)


if __name__ == "__main__":
    main()
