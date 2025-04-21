import gradio as gr
from chatbot import chat
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


def create_interface():
    with gr.Blocks(js=dark_mode) as demo:
        gr.Markdown("## 🎬 Movie Recommendation Assistant")

        with gr.Row():
            genre_input = gr.Dropdown(
                choices=["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family", "Fantasy", "history", "Horror", "Music", "Mystery", "Romance", "Science Fiction", "TV Movie", "Thriller", "War", "Western"],
                label="Filter by Genres",
                multiselect=True,
            )
            provider_input = gr.Dropdown(
                choices=["Netflix", "Hulu", "Disney Plus", "Max", "Amazon Prime Video", "Apple TV+", "Paramount Plus", "Paramount+ with Showtime", "Peacock Premium", "Crunchyroll", "MGM Plus", "fuboTV", "Starz", "AMC+", "Sling TV", "Philo"],
                label="Filter by Streaming Services",
                multiselect=True,
            )
            year_range = RangeSlider(minimum=1920, maximum=2025, value=(1920, 2025), step=1, label="Release Year")

        with gr.Column():
            chatbot = gr.Chatbot(
                placeholder="<div style='text-align: center;'><h3><strong>Your Personal Movie Curator - Powered by AI</strong></h3>Tell me the movie vibe you're looking for 🍿<br>Like: Dark comedies with unexpected endings, moral ambiguity, and reflections on modern society</div>",
            )

            gr.ChatInterface(
                fn=chat,
                type="messages",
                chatbot=chatbot,
                additional_inputs=[genre_input, provider_input, year_range]
            )

    return demo