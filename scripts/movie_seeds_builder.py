from reelix_core.config import (
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    QDRANT_MOVIE_COLLECTION_NAME,
)
from reelix_retrieval.qdrant_filter import build_qfilter
from reelix_retrieval.vectorstore import connect_qdrant

SEEDS_300 = {
    "Action": [
        {
            "title": "Mad Max: Fury Road",
            "year": 2015,
            "vibes": ["Dystopian", "Post-Apocalyptic", "Dieselpunk"],
        },
        {
            "title": "John Wick",
            "year": 2014,
            "vibes": ["Action Thriller", "Revenge", "Action-Packed"],
        },
        {
            "title": "Mission: Impossible - Fallout",
            "year": 2018,
            "vibes": ["Espionage", "High-Stakes", "Fast-Paced"],
        },
        {"title": "Skyfall", "year": 2012, "vibes": ["Espionage", "High-stakes"]},
        {
            "title": "Crouching Tiger, Hidden Dragon",
            "year": 2000,
            "vibes": ["Action epic", "Martial Arts"],
        },
        {"title": "Die Hard", "year": 1988, "vibes": ["High-Stakes", "Action-packed", "Christmas Movie"]},
        {
            "title": "Gladiator",
            "year": 2000,
            "vibes": ["Action Epic", "Grand Journey", "Sword and Sandal"],
        },
        {
            "title": "The Bourne Ultimatum",
            "year": 2007,
            "vibes": ["Conspiracy Thriller", "Fast-Paced", "Espionage"],
        },
        {
            "title": "Edge of Tomorrow",
            "year": 2014,
            "vibes": ["Military Sci-Fi", "Time-Loop", "Redemption"],
        },
        {
            "title": "The Dark Knight",
            "year": 2008,
            "vibes": ["Crime Epic", "High-stakes", "Gritty Realism"],
        },
        {
            "title": "Casino Royale",
            "year": 2006,
            "vibes": ["Espionage", "Neo-Noir Spy", "Gritty Realism"],
        },
        {
            "title": "Top Gun: Maverick",
            "year": 2022,
            "vibes": ["High-Octane", "Nostalgic", "Spectacular"],
        },
        {
            "title": "The Northman",
            "year": 2022,
            "vibes": ["Historical Epic", "Mythic", "Gritty"],
        },
        {
            "title": "Terminator 2: Judgment Day",
            "year": 1991,
            "vibes": ["Techno-Thriller", "Action Epic", "Free Will"],
        },
        {
            "title": "Heat",
            "year": 1995,
            "vibes": ["Crime Epic", "Methodical", "Somber"],
        },
        {
            "title": "Wonder Woman",
            "year": 2017,
            "vibes": ["Historical Epic", "Empowering", "Superhero"],
        },
        {
            "title": "Dawn of the Planet of the Apes",
            "year": 2014,
            "vibes": ["Post-Apocalyptic", "Dystopian Sci-Fi", "Visceral"],
        },
        {
            "title": "The Matrix",
            "year": 1999,
            "vibes": ["Sci-fi action", "Mind-bending", "Revolutionary"],
        },
        {
            "title": "Face/Off",
            "year": 1997,
            "vibes": ["Over-the-top", "High-concept", "Explosive"],
        },
        {
            "title": "Speed",
            "year": 1994,
            "vibes": ["High-concept thriller", "Non-stop action"],
        },
        # {'title': 'Aliens', 'year': 1986, 'vibes': ['Sci-fi action', 'Military', 'Intense']},
        {
            "title": "Kill Bill: Vol. 1",
            "year": 2003,
            "vibes": ["Stylized violence", "Revenge", "Martial arts"],
        },
        {
            "title": "The Rock",
            "year": 1996,
            "vibes": ["Blockbuster", "High-stakes", "Island setting"],
        },
        # {'title': 'Logan', 'year': 2017, 'vibes': ['Dystopian', 'Neo-Western', 'Character-Driven']},
        {
            "title": "John Wick: Chapter 4",
            "year": 2023,
            "vibes": ["Stylized Action", "Revenge", "Modern"],
        },
        {
            "title": "Blood Diamond",
            "year": 2006,
            "vibes": ["Action Epic", "Political Thriller", "Emotional"],
        },
        {
            "title": "Atomic Blonde",
            "year": 2017,
            "vibes": ["Stylish", "Espionage", "Female-led"],
        },
        {
            "title": "The Equalizer",
            "year": 2014,
            "vibes": ["Vigilante Justice", "Methodical", "Modern"],
        },
        {
            "title": "Nobody",
            "year": 2021,
            "vibes": ["Suburban Dad Action", "Dark Comedy", "Cathartic"],
        },
        {
            "title": "Extraction",
            "year": 2020,
            "vibes": ["Military action", "International", "Gritty"],
        },
    ],
    "Adventure": [
        {
            "title": "Raiders of the Lost Ark",
            "year": 1981,
            "vibes": ["Epic scale", "Grand journey"],
        },
        {
            "title": "The Lord of the Rings: The Fellowship of the Ring",
            "year": 2001,
            "vibes": ["Swashbuckler", "Grand journey", "Euphoric"],
        },
        {
            "title": "Spirited Away",
            "year": 2001,
            "vibes": ["Whimsical", "Visually-stunning"],
        },
        {
            "title": "Pirates of the Caribbean: The Curse of the Black Pearl",
            "year": 2003,
            "vibes": ["Whimsical", "Visually-stunning"],
        },
        {
            "title": "Into the Wild",
            "year": 2007,
            "vibes": ["Philosophical", "Poignant", "Somber"],
        },
        {
            "title": "Life of Pi",
            "year": 2012,
            "vibes": ["Visually-stunning", "Grand journey"],
        },
        {"title": "Up", "year": 2009, "vibes": ["Whimsical", "Grand journey"]},
        {
            "title": "Avengers: Endgame",
            "year": 2019,
            "vibes": ["Epic scale", "Visually-stunning"],
        },
        {
            "title": "The Revenant",
            "year": 2015,
            "vibes": ["Grand journey", "Epic scale"],
        },
        {
            "title": "The Secret Life of Walter Mitty",
            "year": 2013,
            "vibes": ["Whimsical", "Grand Journey"],
        },
        {
            "title": "Moana",
            "year": 2016,
            "vibes": ["Grand journey", "Visually-stunning"],
        },
        {
            "title": "Indiana Jones and the Last Crusade",
            "year": 1989,
            "vibes": ["Classic Adventure", "Father-son dynamic"],
        },
        {
            "title": "The Princess Bride",
            "year": 1987,
            "vibes": ["Fairy tale", "Swashbuckler", "Quotable"],
        },
        {
            "title": "Jurassic Park",
            "year": 1993,
            "vibes": ["Monster Adventure", "Groundbreaking Effects"],
        },
        {
            "title": "The Mummy",
            "year": 1999,
            "vibes": ["Pulp adventure", "Horror-comedy", "Treasure hunt"],
        },
        {
            "title": "National Treasure",
            "year": 2004,
            "vibes": ["Modern treasure hunt", "Puzzle-solving"],
        },
        {
            "title": "The Jungle Book",
            "year": 2016,
            "vibes": ["Coming-of-age", "Nature adventure"],
        },
        {
            "title": "Finding Nemo",
            "year": 2003,
            "vibes": ["Underwater adventure", "Father-son journey"],
        },
        {
            "title": "Interstellar",
            "year": 2014,
            "vibes": ["Adventure Epic", "Time Travel", "Emotional"],
        },
        # {'title': 'Stand by Me', 'year': 1986, 'vibes': ['Coming-of-age journey', 'Friendship']},
        {
            "title": "Lawrence of Arabia",
            "year": 1962,
            "vibes": ["Epic desert adventure", "Historical"],
        },
        {
            "title": "The Wild Robot",
            "year": 2024,
            "vibes": ["Animal Adventure", "Heartwarming", "Introspective"],
        },
        {
            "title": "Tomb Raider",
            "year": 2018,
            "vibes": ["Modern Adventure", "Female Protagonist"],
        },
        {
            "title": "Jumanji: Welcome to the Jungle",
            "year": 2017,
            "vibes": ["Video game adventure", "Comedy"],
        },
        {
            "title": "The Lion King",
            "year": 1994,
            "vibes": ["Adventure epic", "Coming-of-Age", "Family"],
        },
        {
            "title": "Sherlock Holmes",
            "year": 2009,
            "vibes": ["Action Adventure", "Mystery", "Witty"],
        },
        {
            "title": "Jungle Cruise",
            "year": 2021,
            "vibes": ["Theme park adventure", "Comedy"],
        },
        {
            "title": "The Way Back",
            "year": 2010,
            "vibes": ["Survival epic", "Historical journey"],
        },
        {
            "title": "Wild",
            "year": 2014,
            "vibes": ["Personal journey", "Memoir adaptation"],
        },
        {
            "title": "King Kong",
            "year": 2005,
            "vibes": ["Adventure Epic", "Jungle adventure", "Tragic"],
        },
    ],
    "Comedy": [
        {
            "title": "The Grand Budapest Hotel",
            "year": 2014,
            "vibes": ["Quirky", "Melancholic"],
        },
        # {"title": "Green Book", "year": 2018, "vibes": ["Road Movie", "Feel-Good", "Period Drama"]},
        {
            "title": "Poor Things",
            "year": 2023,
            "vibes": ["Absurd", "Gothic", "Dark Comedy"],
        },
        {"title": "Zombieland", "year": 2009, "vibes": ["Light-Hearted", "Satirical"]},
        {
            "title": "Mean Girls",
            "year": 2004,
            "vibes": ["Coming-of-age", "Light-hearted", "Teen Comedy"],
        },
        {"title": "Jojo Rabbit", "year": 2019, "vibes": ["Satirical", "Quirky"]},
        {
            "title": "Anchorman: The Legend of Ron Burgundy",
            "year": 2004,
            "vibes": ["Light-hearted", "Absurd"],
        },
        {"title": "Hot Fuzz", "year": 2007, "vibes": ["Quirky", "Satirical"]},
        {
            "title": "Paddington 2",
            "year": 2017,
            "vibes": ["Feel-good", "Light-hearted", "Family"],
        },
        {
            "title": "The Big Lebowski",
            "year": 1998,
            "vibes": ["Absurd", "Satirical", "Neo-Noir"],
        },
        {
            "title": "Superbad",
            "year": 2007,
            "vibes": ["Coming-of-age", "Raunchy", "Friendship"],
        },
        {
            "title": "Bridesmaids",
            "year": 2011,
            "vibes": ["Female-driven", "Raunchy", "Wedding Comedy"],
        },
        {
            "title": "The Hangover",
            "year": 2009,
            "vibes": ["Slapstick", "Mystery Comedy", "Raunchy"],
        },
        {
            "title": "Borat: Cultural Learnings of America for Make Benefit Glorious Nation of Kazakhstan",
            "year": 2006,
            "vibes": ["Mockumentary", "Satirical", "Controversial"],
        },
        {
            "title": "Tropic Thunder",
            "year": 2008,
            "vibes": ["Hollywood satire", "Action comedy"],
        },
        {
            "title": "21 Jump Street",
            "year": 2012,
            "vibes": ["Buddy Comedy", "Action Comedy"],
        },
        {
            "title": "Knives Out",
            "year": 2019,
            "vibes": ["Murder mystery", "Ensemble", "Witty"],
        },
        {
            "title": "Game Night",
            "year": 2018,
            "vibes": ["Dark comedy", "Thriller comedy"],
        },
        {"title": "Snatch", "year": 2000, "vibes": ["Dark Comedy", "Caper", "Witty"]},
        {
            "title": "Hunt for the Wilderpeople",
            "year": 2016,
            "vibes": ["New Zealand comedy", "Adventure"],
        },
        {
            "title": "In Bruges",
            "year": 2008,
            "vibes": ["Dark comedy", "Crime comedy", "Philosophical"],
        },
        # {'title': 'Kiss Kiss Bang Bang', 'year': 2005, 'vibes': ['Neo-noir comedy', 'Shane Black']},
        {
            "title": "The Nice Guys",
            "year": 2016,
            "vibes": ["Buddy comedy", "70s setting", "Crime"],
        },
        {
            "title": "Thor: Ragnarok",
            "year": 2017,
            "vibes": ["Superhero comedy", "Space adventure"],
        },
        {
            "title": "Deadpool",
            "year": 2016,
            "vibes": ["Superhero parody", "Meta-humor", "R-rated"],
        },
        {
            "title": "Booksmart",
            "year": 2019,
            "vibes": ["Coming-of-age", "Female friendship", "Smart"],
        },
        {
            "title": "The Other Guys",
            "year": 2010,
            "vibes": ["Buddy cops", "Will Ferrell", "Satirical"],
        },
        {
            "title": "Step Brothers",
            "year": 2008,
            "vibes": ["Absurd", "Family comedy", "Childish humor"],
        },
        {
            "title": "Pineapple Express",
            "year": 2008,
            "vibes": ["Stoner comedy", "Action comedy"],
        },
        {
            "title": "Little Miss Sunshine",
            "year": 2006,
            "vibes": ["Coming-of-Age", "Road Trip", "Offbeat"],
        },
    ],
    "Crime": [
        {"title": "Heat", "year": 1995, "vibes": ["Gritty"]},
        {"title": "Se7en", "year": 1995, "vibes": ["Neo-Noir", "Plot-twisty"]},
        {"title": "The Departed", "year": 2006, "vibes": ["Plot-twisty"]},
        {"title": "Chinatown", "year": 1974, "vibes": ["Slow-burn", "Neo-Noir"]},
        {"title": "City of God", "year": 2002, "vibes": ["Gritty"]},
        {"title": "Memories of Murder", "year": 2003, "vibes": ["Slow-burn", "Gritty"]},
        {"title": "Oldboy", "year": 2003, "vibes": ["Neo-Noir", "Plot-twisty"]},
        {
            "title": "The Gentlemen",
            "year": 2020,
            "vibes": ["Fast-paced", "Dark comedy"],
        },
        {"title": "The Godfather", "year": 1972, "vibes": ["Slow-burn"]},
        {"title": "Prisoners", "year": 2013, "vibes": ["Gritty", "Plot-twisty"]},
        {
            "title": "Pulp Fiction",
            "year": 1994,
            "vibes": ["Satirical", "Non-linear narrative"],
        },
        {
            "title": "GoodFellas",
            "year": 1990,
            "vibes": ["Crime epic", "Darkly funny", "Rise and fall"],
        },
        {
            "title": "The Godfather Part II",
            "year": 1974,
            "vibes": ["Epic sequel", "Multi-generational"],
        },
        {
            "title": "Casino",
            "year": 1995,
            "vibes": ["Las Vegas crime", "Epic scope", "Scorsese"],
        },
        {
            "title": "Scarface",
            "year": 1983,
            "vibes": ["Rise and fall", "Excess", "Iconic"],
        },
        {
            "title": "Léon: The Professional",
            "year": 1994,
            "vibes": ["Action Thriller", "Neo-Noir", "Somber"],
        },
        {
            "title": "Miller's Crossing",
            "year": 1990,
            "vibes": ["Prohibition era", "Coen Brothers"],
        },
        {
            "title": "L.A. Confidential",
            "year": 1997,
            "vibes": ["Neo-noir", "1950s Los Angeles"],
        },
        {
            "title": "The Usual Suspects",
            "year": 1995,
            "vibes": ["Caper", "Plot-twisty", "Neo-Noir"],
        },
        {
            "title": "Donnie Brasco",
            "year": 1997,
            "vibes": ["Undercover", "Mafia infiltration"],
        },
        {
            "title": "Training Day",
            "year": 2001,
            "vibes": ["Cop Drama", "Denzel Washington", "Police Procedural"],
        },
        {
            "title": "Collateral",
            "year": 2004,
            "vibes": ["Night in LA", "Hitman thriller"],
        },
        {
            "title": "Baby Driver",
            "year": 2017,
            "vibes": ["Music-driven", "Stylish", "Heist"],
        },
        {
            "title": "Hell or High Water",
            "year": 2016,
            "vibes": ["Modern western", "Bank robbery"],
        },
        {
            "title": "Wind River",
            "year": 2017,
            "vibes": ["Murder mystery", "Neo-western", "Snow"],
        },
        {
            "title": "The Town",
            "year": 2010,
            "vibes": ["Boston crime", "Bank robbery", "Ben Affleck"],
        },
        {
            "title": "Gone Baby Gone",
            "year": 2007,
            "vibes": ["Missing child", "Boston setting"],
        },
        {
            "title": "Zodiac",
            "year": 2007,
            "vibes": ["Serial killer investigation", "70s period"],
        },
        {
            "title": "The Irishman",
            "year": 2019,
            "vibes": ["Crime epic", "Aging gangsters", "Scorsese"],
        },
        {
            "title": "Knives Out",
            "year": 2019,
            "vibes": ["Murder mystery", "Ensemble", "Modern whodunit"],
        },
        {
            "title": "The Hateful Eight",
            "year": 2015,
            "vibes": ["Suspense Mystery", "Gritty", "Intense"],
        },
        {
            "title": "Mystic River",
            "year": 2003,
            "vibes": ["Neo-noir", "Mystery", "Somber"],
        },
    ],
    "Drama": [
        {
            "title": "Moonlight",
            "year": 2016,
            "vibes": ["Character-driven", "Emotional"],
        },
        {
            "title": "Parasite",
            "year": 2019,
            "vibes": ["Social commentary", "Character-driven", "Class warfare"],
        },
        {
            "title": "There Will Be Blood",
            "year": 2007,
            "vibes": ["Character-driven", "Historical"],
        },
        {
            "title": "12 Years a Slave",
            "year": 2013,
            "vibes": ["Historical", "Emotional"],
        },
        {
            "title": "Manchester by the Sea",
            "year": 2016,
            "vibes": ["Emotional", "Character-driven"],
        },
        {
            "title": "Nomadland",
            "year": 2021,
            "vibes": ["Social Commentary", "Freedom", "Reflective"],
        },
        {
            "title": "The Social Network",
            "year": 2010,
            "vibes": ["Docudrama", "Social Commentary", "Biography"],
        },
        {
            "title": "Ford v Ferrari",
            "year": 2019,
            "vibes": ["Docudrama", "Period drama"],
        },
        {
            "title": "The King's Speech",
            "year": 2010,
            "vibes": ["Historical", "Emotional", "Biography"],
        },
        {"title": "Whiplash", "year": 2014, "vibes": ["Character-driven", "Emotional"]},
        {
            "title": "Birdman or (The Unexpected Virtue of Ignorance)",
            "year": 2014,
            "vibes": ["Meta-theatrical", "Character study", "Long takes"],
        },
        {
            "title": "Spotlight",
            "year": 2015,
            "vibes": ["Investigative Journalism", "Social Issue Drama", "True Story"],
        },
        {
            "title": "Room",
            "year": 2015,
            "vibes": ["Psychological", "Mother-Child"],
        },
        {
            "title": "Call Me by Your Name",
            "year": 2017,
            "vibes": ["Coming-of-Age", "Steamy", "Summer Romance"],
        },
        {
            "title": "Lady Bird",
            "year": 2017,
            "vibes": ["Coming-of-Age", "Mother-Daughter", "Heartfelt"],
        },
        {
            "title": "Three Billboards Outside Ebbing, Missouri",
            "year": 2017,
            "vibes": ["Dark comedy-drama", "Small town"],
        },
        {
            "title": "The Big Short",
            "year": 2015,
            "vibes": ["Biography", "Dark comedy", "Docudrama"],
        },
        {
            "title": "Green Book",
            "year": 2018,
            "vibes": ["Racial Relations", "Road Movie", "Feel-Good"],
        },
        {
            "title": "First Man",
            "year": 2018,
            "vibes": ["Historical Drama", "Biography", "Tragic"],
        },
        {
            "title": "A Star Is Born",
            "year": 2018,
            "vibes": ["Music Industry", "Addiction", "Romance"],
        },
        {
            "title": "Marriage Story",
            "year": 2019,
            "vibes": ["Divorce", "Domestic Drama", "Melancholic"],
        },
        {
            "title": "1917",
            "year": 2019,
            "vibes": ["WWI", "Single-Shot Style", "Gritty"],
        },
        {
            "title": "Conclave",
            "year": 2024,
            "vibes": ["Papal", "Political Drama", "Character-Driven"],
        },
        {
            "title": "Anora",
            "year": 2024,
            "vibes": ["Dark Comedy", "Poignant", "Neorealism"],
        },
        {
            "title": "The Father",
            "year": 2020,
            "vibes": ["Dementia", "Disorienting", "Perspective"],
        },
        {
            "title": "CODA",
            "year": 2021,
            "vibes": ["Deaf family", "Coming-of-age", "Music"],
        },
        {
            "title": "Bohemian Rhapsody",
            "year": 2018,
            "vibes": ["Docudrama", "Biography", "Melodramatic"],
        },
        {
            "title": "Oppenheimer",
            "year": 2023,
            "vibes": ["Historical Epic", "Courtroom Drama", "Character Study"],
        },
        {
            "title": "TÁR",
            "year": 2022,
            "vibes": ["Classical Music", "Power Dynamics", "Psychological Drama"],
        },
        {
            "title": "Million Dollar Baby",
            "year": 2004,
            "vibes": ["Sports Drama", "Emotional", "Boxing"],
        },
        {
            "title": "Schindler's List",
            "year": 1993,
            "vibes": ["Historical Epic", "Redemption", "Hopeful"],
        },
    ],
    "Fantasy": [
        {
            "title": "Pan's Labyrinth",
            "year": 2006,
            "vibes": ["Dreamlike", "Mythic", "Magical"],
        },
        {
            "title": "The Lord of the Rings: The Two Towers",
            "year": 2002,
            "vibes": ["High fantasy", "Mythic"],
        },
        {
            "title": "Harry Potter and the Prisoner of Azkaban",
            "year": 2004,
            "vibes": ["Magical"],
        },
        {
            "title": "Howl's Moving Castle",
            "year": 2004,
            "vibes": ["Dreamlike", "Magical"],
        },
        {
            "title": "The Shape of Water",
            "year": 2017,
            "vibes": ["Fantasy Romance", "Dreamlike", "Magical"],
        },
        {"title": "Stardust", "year": 2007, "vibes": ["Magical", "High Fantasy"]},
        {
            "title": "The Curious Case of Benjamin Button",
            "year": 2008,
            "vibes": ["Period Piece", "Whimsical", "Melancholic"],
        },
        {"title": "Big Fish", "year": 2003, "vibes": ["Dreamlike", "Magical"]},
        {
            "title": "Avatar",
            "year": 2009,
            "vibes": ["Fantasy Epic", "Mythic", "Reverent"],
        },
        {
            "title": "The Lord of the Rings: The Return of the King",
            "year": 2003,
            "vibes": ["Epic Conclusion", "Mythic"],
        },
        {
            "title": "Harry Potter and the Goblet of Fire",
            "year": 2005,
            "vibes": ["Tournament", "Darker tone"],
        },
        {
            "title": "The Chronicles of Narnia: The Lion, the Witch and the Wardrobe",
            "year": 2005,
            "vibes": ["Children's Fantasy", "Christian Allegory"],
        },
        {
            "title": "Fantastic Beasts and Where to Find Them",
            "year": 2016,
            "vibes": ["Wizarding World", "Nostalgia", "Magical"],
        },
        {
            "title": "The Green Knight",
            "year": 2021,
            "vibes": ["Arthurian Legend", "A24", "Medieval"],
        },
        {
            "title": "The Lighthouse",
            "year": 2019,
            "vibes": ["Psychological Fantasy", "Black and white"],
        },
        {
            "title": "Barbie",
            "year": 2023,
            "vibes": ["Musical Fantasy", "High-Concept Comedy", "Satirical"],
        },
        {
            "title": "The Golden Compass",
            "year": 2007,
            "vibes": ["Parallel Worlds", "Young Adult"],
        },
        {
            "title": "Percy Jackson & the Olympians: The Lightning Thief",
            "year": 2010,
            "vibes": ["Greek Mythology", "Young Adult"],
        },
        # {
        #     "title": "The Spiderwick Chronicles",
        #     "year": 2008,
        #     "vibes": ["Children's Fantasy", "Fairy creatures"],
        # },
        {
            "title": "Spider-Man: Into the Spider-Verse",
            "year": 2018,
            "vibes": ["Teen Adventure", "Quirky", "Imaginative"],
        },
        {
            "title": "Interview with the Vampire",
            "year": 1994,
            "vibes": ["Dark Fantasy", "Gothic Horror", "Vampire"],
        },
        {
            "title": "Okja",
            "year": 2017,
            "vibes": ["Dystopian", "Heartwarming", "Satirical"],
        },
        {
            "title": "The Hunger Games",
            "year": 2012,
            "vibes": ["Dystopian", "Teen Adventure", "Survival"],
        },
        {
            "title": "Wicked",
            "year": 2024,
            "vibes": ["Pop Musical", "Vibrant", "Emotional"],
        },
        {
            "title": "Legend",
            "year": 1985,
            "vibes": ["Ridley Scott", "Tim Curry", "Dark fantasy"],
        },
        {
            "title": "Beauty and the Beast",
            "year": 2017,
            "vibes": ["Romantic Fantasy", "Fairy-Tale", "Musical"],
        },
        {
            "title": "Edward Scissorhands",
            "year": 1990,
            "vibes": ["Dark Fantasy", "Gothic Romance", "Tragic"],
        },
        {
            "title": "Hugo",
            "year": 2011,
            "vibes": ["Period drama", "Whimsical magic", "Heartfelt"],
        },
        {
            "title": "My Neighbor Totoro",
            "year": 1988,
            "vibes": ["Magical realism", "Nostalgia", "Heartwarming"],
        },
        {
            "title": "300",
            "year": 2007,
            "vibes": ["Action epic", "Mythic", "Sword and Sandal"],
        },
    ],
    "Horror": [
        {"title": "Alien", "year": 1979, "vibes": ["Space Opera", "Monster Horror"]},
        {"title": "The Substance", "year": 2024, "vibes": ["Body Horror", "Sardonic"]},
        {
            "title": "American Psycho",
            "year": 2000,
            "vibes": ["Slasher", "Psychological"],
        },
        {
            "title": "Hereditary",
            "year": 2018,
            "vibes": ["Folk Horror", "Twisted", "Nihilistic"],
        },
        {
            "title": "Get Out",
            "year": 2017,
            "vibes": ["Social Thriller", "Twisted", "Satirical"],
        },
        {
            "title": "A Nightmare on Elm Street",
            "year": 1984,
            "vibes": ["Visceral", "Slasher", "Dream"],
        },
        {
            "title": "Midsommar",
            "year": 2019,
            "vibes": ["Folk Horror", "Unsettling", "Visceral"],
        },
        {
            "title": "It",
            "year": 2017,
            "vibes": ["Monster Horror", "Suspenseful", "Coming-of-Age"],
        },
        {
            "title": "A Quiet Place",
            "year": 2018,
            "vibes": ["Survival", "Monster Horror"],
        },
        {"title": "Split", "year": 2017, "vibes": ["Suspenseful", "Claustrophobic"]},
        {
            "title": "Nosferatu",
            "year": 2024,
            "vibes": ["Gothic Horror", "Grotesque", "Vampire"],
        },
        {
            "title": "Halloween",
            "year": 1978,
            "vibes": ["Slasher", "Michael Myers", "Suspense"],
        },
        {
            "title": "The Lighthouse",
            "year": 2019,
            "vibes": ["Folk Horror", "Claustrophobic", "Character Study"],
        },
        {
            "title": "Psycho",
            "year": 1960,
            "vibes": ["Hitchcock", "Shower scene", "Twist ending"],
        },
        {
            "title": "The Shining",
            "year": 1980,
            "vibes": ["Kubrick", "Hotel Isolation", "Madness"],
        },
        {
            "title": "Jaws",
            "year": 1975,
            "vibes": ["Monster Horror", "Ominous", "Survival"],
        },
        {
            "title": "The Babadook",
            "year": 2014,
            "vibes": ["Psychological", "Grief metaphor", "Australian"],
        },
        {
            "title": "The Conjuring",
            "year": 2013,
            "vibes": ["Haunted House", "Paranormal Investigators", "Atmospheric"],
        },
        {
            "title": "Sinister",
            "year": 2012,
            "vibes": ["Found footage elements", "Writer protagonist"],
        },
        {
            "title": "Requiem for a Dream",
            "year": 2000,
            "vibes": ["Body Horror", "Tragic", "Disturbing"],
        },
        {
            "title": "The Ring",
            "year": 2002,
            "vibes": ["J-horror remake", "Cursed videotape"],
        },
        {
            "title": "Scream",
            "year": 1996,
            "vibes": ["Meta-horror", "Slasher revival", "Wes Craven"],
        },
        {
            "title": "Saw",
            "year": 2004,
            "vibes": ["Torture Porn", "Puzzle Traps", "Low Budget"],
        },
        {
            "title": "The Blair Witch Project",
            "year": 1999,
            "vibes": ["Found Footage", "Marketing Phenomenon"],
        },
        {
            "title": "Paranormal Activity",
            "year": 2007,
            "vibes": ["Found footage", "Suburban setting"],
        },
        {
            "title": "The Witch",
            "year": 2016,
            "vibes": ["Period horror", "Puritan family", "Folklore"],
        },
        {
            "title": "It Follows",
            "year": 2015,
            "vibes": ["STD metaphor", "Retro aesthetic", "Unique premise"],
        },
        {
            "title": "Train to Busan",
            "year": 2016,
            "vibes": ["Zombie thriller", "Korean", "Emotional"],
        },
        {
            "title": "The Descent",
            "year": 2005,
            "vibes": ["Claustrophobic", "Cave exploration", "Creatures"],
        },
        {
            "title": "28 Days Later",
            "year": 2002,
            "vibes": ["Zombie apocalypse", "Fast zombies", "Post-9/11"],
        },
    ],
    "Romance": [
        {
            "title": "When Harry Met Sally...",
            "year": 1989,
            "vibes": ["Romantic comedy"],
        },
        {
            "title": "Pride & Prejudice",
            "year": 2005,
            "vibes": ["Heartwarming", "Period drama"],
        },
        {
            "title": "The Big Sick",
            "year": 2017,
            "vibes": ["Romantic comedy", "Heartwarming"],
        },
        {"title": "Before Sunrise", "year": 1995, "vibes": ["Bittersweet"]},
        {"title": "Call Me by Your Name", "year": 2017, "vibes": ["Bittersweet"]},
        {
            "title": "Eternal Sunshine of the Spotless Mind",
            "year": 2004,
            "vibes": ["Bittersweet"],
        },
        {"title": "Titanic", "year": 1997, "vibes": ["Tragic love"]},
        {
            "title": "La La Land",
            "year": 2016,
            "vibes": ["Bittersweet", "Visually-stunning"],
        },
        {
            "title": "The Notebook",
            "year": 2004,
            "vibes": ["Tragic love", "Heartwarming"],
        },
        {
            "title": "Midnight in Paris",
            "year": 2011,
            "vibes": ["Nostalgic", "Metaphorical", "Romantic comedy"],
        },
        {
            "title": "Notting Hill",
            "year": 1999,
            "vibes": ["Romantic comedy", "Heartwarming"],
        },
        {
            "title": "The Handmaiden",
            "year": 2016,
            "vibes": ["Dark romance", "Erotic thriller", "Steamy romance"],
        },
        {
            "title": "Begin Again",
            "year": 2014,
            "vibes": ["Musical Drama", "Second Chances", "Feel-good"],
        },
        {
            "title": "Sleepless in Seattle",
            "year": 1993,
            "vibes": ["Destined love", "Cross-country romance"],
        },
        {
            "title": "You've Got Mail",
            "year": 1998,
            "vibes": ["Email romance", "Small business vs corporate"],
        },
        {
            "title": "Pretty Woman",
            "year": 1990,
            "vibes": ["Modern fairy tale", "Class differences"],
        },
        {
            "title": "Ghost",
            "year": 1990,
            "vibes": ["Supernatural Romance", "Sentimental", "Suspenseful"],
        },
        {
            "title": "Brokeback Mountain",
            "year": 2005,
            "vibes": ["Neo-Western", "Melancholic", "Steamy Romance"],
        },
        {
            "title": "Up in the Air",
            "year": 2009,
            "vibes": ["Workplace Drama", "Witty", "Tragic Romance"],
        },
        {
            "title": "Past Lives",
            "year": 2023,
            "vibes": ["Indie Drama", "Anti-Fairy Tale", "Bittersweet"],
        },
        {
            "title": "Before Sunset",
            "year": 2004,
            "vibes": ["Sequel", "Paris setting", "Real-time conversation"],
        },
        {
            "title": "The Great Gatsby",
            "year": 2013,
            "vibes": ["Period Drama", "Tragic Romance", "Dreamlike"],
        },
        {
            "title": "(500) Days of Summer",
            "year": 2009,
            "vibes": ["Anti-romantic comedy", "Expectations vs reality"],
        },
        {
            "title": "Silver Linings Playbook",
            "year": 2012,
            "vibes": ["Romantic Comedy", "Heartfelt", "Bittersweet"],
        },
        {
            "title": "Lost in Translation",
            "year": 2003,
            "vibes": ["Cross-cultural", "Tokyo", "Age gap friendship"],
        },
        {
            "title": "Amélie",
            "year": 2001,
            "vibes": ["French romance", "Whimsical", "Paris", "Color palette"],
        },
        # {'title': 'The Shape of Water', 'year': 2017, 'vibes': ['Interspecies romance', 'Cold War', 'Guillermo del Toro']},
        {
            "title": "Carol",
            "year": 2015,
            "vibes": ["1950s lesbian romance", "Cate Blanchett", "Period piece"],
        },
        {
            "title": "Moonrise Kingdom",
            "year": 2012,
            "vibes": ["Young love", "Wes Anderson", "Summer camp"],
        },
        {
            "title": "About Time",
            "year": 2013,
            "vibes": ["Time travel romance", "Family relationships", "British"],
        },
    ],
    "Science Fiction": [
        {
            "title": "Inception",
            "year": 2010,
            "vibes": ["Mind-bending", "Cerebral", "Psychological"],
        },
        {"title": "The Matrix", "year": 1999, "vibes": ["Cyberpunk", "Mind-bending"]},
        {
            "title": "Blade Runner 2049",
            "year": 2017,
            "vibes": ["Cyberpunk", "Thought-provoking", "Dystopian"],
        },
        {"title": "Arrival", "year": 2016, "vibes": ["Thought-provoking"]},
        {"title": "Ex Machina", "year": 2015, "vibes": ["Thought-provoking"]},
        {
            "title": "Children of Men",
            "year": 2006,
            "vibes": ["Dystopian", "Thought-provoking"],
        },
        {
            "title": "Everything Everywhere All at Once",
            "year": 2022,
            "vibes": ["Quirky", "Existential", "Mind-bending"],
        },
        {"title": "Gattaca", "year": 1997, "vibes": ["Dystopian", "Thought-provoking"]},
        {
            "title": "Gravity",
            "year": 2013,
            "vibes": ["Claustrophobic", "Visually Stunning", "Tense"],
        },
        {"title": "Her", "year": 2013, "vibes": ["Poignant", "Thought-provoking"]},
        {
            "title": "Ghost in the Shell",
            "year": 1995,
            "vibes": ["Cyberpunk", "Thought-provoking"],
        },
        {
            "title": "Blade Runner",
            "year": 1982,
            "vibes": ["Neo-noir sci-fi", "Replicants", "Philip K. Dick"],
        },
        {
            "title": "2001: A Space Odyssey",
            "year": 1968,
            "vibes": ["Kubrick", "HAL 9000", "Evolution"],
        },
        {
            "title": "Star Wars",
            "year": 1977,
            "vibes": ["Space opera", "Hero's journey"],
        },
        {
            "title": "E.T. the Extra-Terrestrial",
            "year": 1982,
            "vibes": ["Family sci-fi", "Spielberg", "Friendship"],
        },
        {
            "title": "Logan",
            "year": 2017,
            "vibes": ["Dystopian", "Neo-Western", "Character-Driven"],
        },
        {
            "title": "Terminator 2: Judgment Day",
            "year": 1991,
            "vibes": ["Time travel", "AI apocalypse", "Action"],
        },
        {
            "title": "Back to the Future",
            "year": 1985,
            "vibes": ["Time travel", "Comedy", "Family-friendly"],
        },
        {
            "title": "Star Trek",
            "year": 2009,
            "vibes": ["Space Adventure", "Time Travel", " Fast-Paced"],
        },
        {
            "title": "V for Vendetta",
            "year": 2006,
            "vibes": ["Distopian Sci-Fi", "Cold War", "Political Drama"],
        },
        {
            "title": "Ghostbusters",
            "year": 1984,
            "vibes": ["Irreverent", "Quirky", "Deadpan Humor"],
        },
        {
            "title": "District 9",
            "year": 2009,
            "vibes": ["Apartheid allegory", "South African", "Found footage"],
        },
        {
            "title": "Moon",
            "year": 2009,
            "vibes": ["Isolation", "AI companion", "Sam Rockwell"],
        },
        {
            "title": "Primer",
            "year": 2004,
            "vibes": ["Low-budget", "Complex time travel", "Engineers"],
        },
        {
            "title": "Looper",
            "year": 2012,
            "vibes": ["Time travel assassins", "Joseph Gordon-Levitt"],
        },
        {
            "title": "Minority Report",
            "year": 2002,
            "vibes": ["Pre-crime", "Philip K. Dick", "Spielberg"],
        },
        {
            "title": "Total Recall",
            "year": 1990,
            "vibes": ["Memory implants", "Mars", "Philip K. Dick"],
        },
        {
            "title": "The Fifth Element",
            "year": 1997,
            "vibes": ["Vibrant Visual", "Luc Besson", "Cyberpunk"],
        },
        {
            "title": "Dune: Part Two",
            "year": 2024,
            "vibes": ["Space Opera", "Sci-Fi Epic", "Gritty"],
        },
        # {'title': 'Elysium', 'year': 2013, 'vibes': ['Class warfare', 'Space station', 'Matt Damon']}
    ],
    "Thriller": [
        {
            "title": "The Silence of the Lambs",
            "year": 1991,
            "vibes": ["Police Procedural", "Intense Suspense", "Unnerving"],
        },
        {
            "title": "Shutter Island",
            "year": 2010,
            "vibes": ["Mystery", "Suspenseful", "Disorienting"],
        },
        {
            "title": "Gone Girl",
            "year": 2014,
            "vibes": ["Psychological", "Suspenseful", "Unsettling"],
        },
        {
            "title": "No Country for Old Men",
            "year": 2007,
            "vibes": ["Neo-Western", "Grim Realism", "Intense"],
        },
        {"title": "Nightcrawler", "year": 2014, "vibes": ["Dark", "Psychological"]},
        {
            "title": "Donnie Darko",
            "year": 2001,
            "vibes": ["Mystery", "Enigmatic", "Philosophical"],
        },
        {
            "title": "Sicario",
            "year": 2015,
            "vibes": ["Neo-Western", "Political Thriller", "Visceral"],
        },
        {
            "title": "The Prestige",
            "year": 2006,
            "vibes": ["Period Drama", "Dark", "Enigmatic"],
        },
        {
            "title": "Black Swan",
            "year": 2010,
            "vibes": ["Psychological", "Duality", "Suspenseful"],
        },
        {
            "title": "The Girl with the Dragon Tattoo",
            "year": 2011,
            "vibes": ["Suspenseful", "Dark"],
        },
        # {
        #     "title": "Zodiac",
        #     "year": 2007,
        #     "vibes": ["Serial killer", "Investigation", "1970s"],
        # },
        {
            "title": "The Game",
            "year": 1997,
            "vibes": ["Conspiracy Thriller", "Paranoid", "Disorienting"],
        },
        {
            "title": "Fight Club",
            "year": 1999,
            "vibes": ["Identity Crisis", "Twist Ending", "Social Commentary"],
        },
        {
            "title": "Memento",
            "year": 2000,
            "vibes": ["Reverse Chronology", "Psychological Thriller", "Existential"],
        },
        {
            "title": "Rear Window",
            "year": 1954,
            "vibes": ["Hitchcock", "Voyeurism", "Apartment setting"],
        },
        {
            "title": "The Secret in Their Eyes",
            "year": 2009,
            "vibes": ["Dark Romance", "Erotic Thriller", "Tragic"],
        },
        {
            "title": "Joker",
            "year": 2019,
            "vibes": ["Psychological Thriller", "Character-driven", "Tragic"],
        },
        {
            "title": "Cape Fear",
            "year": 1991,
            "vibes": ["Stalker", "Family threat", "De Niro"],
        },
        {
            "title": "Fatal Attraction",
            "year": 1987,
            "vibes": ["Adultery Consequences", "Stalker", "Family"],
        },
        {
            "title": "The Lives of Others",
            "year": 2006,
            "vibes": ["Political Thriller", "Humanistic", "Thought-Provoking"],
        },
        {
            "title": "Misery",
            "year": 1990,
            "vibes": ["Stephen King", "Writer captive", "Kathy Bates"],
        },
        {
            "title": "The Sixth Sense",
            "year": 1999,
            "vibes": ["Supernatural", "Suspenseful", "Eerie"],
        },
        {
            "title": "What Lies Beneath",
            "year": 2000,
            "vibes": ["Supernatural thriller", "Marriage secrets"],
        },
        {
            "title": "The Others",
            "year": 2001,
            "vibes": ["Ghost Story", "Nicole Kidman", "Twist Ending"],
        },
        {
            "title": "Identity",
            "year": 2003,
            "vibes": ["Multiple personalities", "Motel setting", "Twist"],
        },
        {
            "title": "The Machinist",
            "year": 2004,
            "vibes": ["Insomnia", "Christian Bale", "Psychological"],
        },
        {
            "title": "Shutter",
            "year": 2004,
            "vibes": ["Thai horror-thriller", "Photography", "Guilt"],
        },
        {
            "title": "The Wailing",
            "year": 2016,
            "vibes": ["Korean supernatural", "Village mystery", "Ambiguous"],
        },
        {
            "title": "Burning",
            "year": 2018,
            "vibes": ["Korean Psychological", "Class Tensions", "Mysterious"],
        },
        {
            "title": "Nightmare Alley",
            "year": 2021,
            "vibes": ["Psychological Thriller", "Neo-Noir", "Cynical"],
        },
    ],
}


def query_qdrant(filter):
    points, _ = qdrant_client.scroll(
        collection_name=QDRANT_MOVIE_COLLECTION_NAME,
        scroll_filter=filter,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    return points


qdrant_client = connect_qdrant(QDRANT_API_KEY, QDRANT_ENDPOINT)

for genre, medias in SEEDS_300.items():
    print(f"\n== {genre} ==")
    for m in medias:
        filter = build_qfilter(titles=[m["title"]], release_year=m["year"])
        # print (m['title'])
        points = query_qdrant(filter)
        if points and points[0].payload:
            payload = points[0].payload
            m["poster_url"] = payload["poster_url"]
            m["media_id"] = payload["media_id"]
        else:
            print(f"Missing {m['title']}")
            m["poster_url"] = ""
            m["media_id"] = ""

SEEDS_300
