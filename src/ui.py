import gradio as gr
from gradio_rangeslider import RangeSlider

dark_mode = """
function refresh() {
    const url = new URL(window.location);
    if (url.searchParams.get('__theme') !== 'dark') {
        url.searchParams.set('__theme', 'dark');
        window.location.href = url.href;
    }
}
"""


def create_interface(chat_fn):
    movie_genres = [
        "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family",
        "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", "Science Fiction",
        "TV Movie", "Thriller", "War", "Western"
    ]

    tv_genres = [
        "Action & Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family",
        "Kids", "Mystery", "News", "Reality", "Sci-Fi & Fantasy", "Soap", "Talk", "War & Politics", "Western"
    ]

    def update_genres(media_type):
        return gr.update(
            choices=movie_genres if media_type == "Movies" else tv_genres,
            value=[]
        )
    
    with gr.Blocks(fill_height=True, js=dark_mode, css="""
    .message-wrap {
    overflow-anchor: none;
    }
    .message-wrap:last-child {
    overflow-anchor: auto;
    }
    .chat-container {
    scroll-behavior: smooth;
    }
    .messages-wrapper {
    min-height: 400px;
    }
    """) as demo:
        gr.Markdown("## 🎬 Movie Recommendation Assistant- Hybrid BGE/BM25")

        with gr.Row():
            media_type_input = gr.Dropdown(
                choices=["Movies", "TV Shows"],
                value="Movies",
                label="Media Type",
                multiselect=False,
            )
            genre_input = gr.Dropdown(
                choices=movie_genres,
                label="Filter by Genres",
                multiselect=True,
            )
            provider_input = gr.Dropdown(
                choices=["Netflix", "Hulu", "Max", "Amazon Prime Video", "Disney Plus", "Apple TV+", "Paramount Plus", "Paramount+ with Showtime", "Peacock Premium", "Crunchyroll", "MGM Plus", "fuboTV", "Starz", "AMC+", "Sling TV", "Philo"],
                label="Filter by Streaming Services",
                multiselect=True,
            )
            year_range = RangeSlider(minimum=1920, maximum=2025, value=(1920, 2025), step=1, label="Release Year", scale=2)

        media_type_input.change(
            fn=update_genres,
            inputs=media_type_input,
            outputs=genre_input
        )
        
        with gr.Column():
            chatbot = gr.Chatbot(
                placeholder="<div style='text-align: center;'><h3><strong>Your Personal Movie & TV Show Curator - Powered by AI</strong></h3>Tell me the vibe you're looking for 🍿<br>Like: Psychological dramas that are character-driven, satirical, and thought-provoking</div>",
                type="messages",
                bubble_full_width=False,
            )
            gr.ChatInterface(
                fn=chat_fn,
                type="messages",
                chatbot=chatbot,
                additional_inputs=[media_type_input, genre_input, provider_input, year_range],
                fill_height=True, 
                css="""
                .chatbot .message.markdown { 
                    overflow-y: auto; 
                    max-height: 500px; 
                }
                .markdown-content {
                    transition: none !important;
                }
                """
                    )
    return demo