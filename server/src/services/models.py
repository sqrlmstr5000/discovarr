import enum
from peewee import *
from datetime import datetime
from typing import Optional, Dict, List, Any 
from pydantic import BaseModel, Field
from pgvector.peewee import HalfVectorField

# Peewee Models
database = DatabaseProxy() # Use a Proxy to allow runtime DB selection

class SettingType(str, enum.Enum):
    STRING = "STRING"
    INTEGER = "INTEGER" 
    BOOLEAN = "BOOLEAN"
    URL = "URL"
    FLOAT = "FLOAT"

class PeeweeBaseModel(Model):
    class Meta:
        database = database

class Settings(PeeweeBaseModel):
    group = CharField(null=False)
    name = CharField(null=False)
    value = TextField(null=True)
    type = CharField(null=True)  # STRING, INTEGER, BOOLEAN, or URL
    description = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = (
            # Unique together constraint on group and name
            (('group', 'name'), True),
        )

class Search(PeeweeBaseModel):
    name = CharField(null=False) 
    prompt = TextField(null=False)
    kwargs = CharField(null=True)  # JSON string for dict of kwargs
    last_run_date = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.now)

# DEPRECATED: 6/17/2025 Using LLMStat instead. Keeping for migration purposes.
class SearchStat(PeeweeBaseModel):
    search = ForeignKeyField(Search, backref='search_ref', on_delete='CASCADE', null=True)
    prompt_token_count = IntegerField(default=0)
    candidates_token_count = IntegerField(default=0)
    thoughts_token_count = IntegerField(default=0)
    total_token_count = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

class LLMStat(PeeweeBaseModel):
    source_provider = CharField(null=False) 
    reference = CharField(null=False) 
    prompt_token_count = IntegerField(default=0)
    candidates_token_count = IntegerField(default=0)
    thoughts_token_count = IntegerField(default=0)
    total_token_count = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

class Media(PeeweeBaseModel):
    title = CharField(null=False)
    entity_type = CharField(null=False) # e.g., 'suggestion', 'library'
    source_provider = CharField(null=True)
    source_title = CharField(null=True)
    description = TextField(null=True)
    similarity = TextField(null=True)
    media_type = CharField(null=False)
    tmdb_id = CharField(null=True)
    rt_url = CharField(null=True)
    rt_score = IntegerField(null=True)
    poster_url = CharField(null=True)
    poster_url_source = CharField(null=True)
    media_status = CharField(null=True) # e.g., Rumored, Planned, In Production, Post Production, Released, Canceled
    release_date = DateField(null=True)
    networks = TextField(null=True) 
    genres = TextField(null=True) 
    original_language = CharField(null=True) # e.g., 'en', 'ja'
    ignore = BooleanField(default=False)
    search = ForeignKeyField(Search, backref='search', null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    favorite = BooleanField(default=False)
    # Watch history fields
    watched = BooleanField(default=False)
    watch_count = IntegerField(default=0)

class MediaResearch(PeeweeBaseModel):
    media = ForeignKeyField(Media, backref='media_ref', unique=False, null=True, on_delete='CASCADE') # One-to-many relationship
    title = CharField(null=False)
    research = TextField(null=False) # To store research notes or extended details
    embedding = HalfVectorField(dimensions=4000) 
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class WatchHistory(PeeweeBaseModel):
    media = ForeignKeyField(Media, backref='media_ref', on_delete='CASCADE') # One Media to Many WatchHistory entries
    watched_by = CharField(null=False)
    last_played_date = DateTimeField(null=False)
    processed = BooleanField(default=False)
    processed_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Schedule(PeeweeBaseModel):
    search = ForeignKeyField(Search, backref='search_ref', null=True)
    job_id = TextField(unique=True)
    func_name = TextField()
    year = CharField(null=True)
    month = CharField(null=True)
    hour = IntegerField(null=True)
    minute = IntegerField(null=True)
    day = CharField(null=True)
    day_of_week = CharField(null=True)
    args = CharField(null=True)  # JSON string for list of args
    kwargs = CharField(null=True)  # JSON string for dict of kwargs
    enabled = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Migrations(PeeweeBaseModel):
    version = IntegerField()
    applied_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'migrations'

MODELS = [Media, WatchHistory, Search, LLMStat, Schedule, Migrations, Settings]

# Application Models

class ItemsFiltered(BaseModel):
    """Represents a filtered recently watched media item."""
    name: str
    id: Optional[str] # Assumes this is the TMDB ID
    type: Optional[str] # 'movie' or 'tv'
    last_played_date: Optional[str] # ISO 8601 str
    play_count: Optional[int] = None  
    is_favorite: Optional[bool] = False  
    poster_url: Optional[str] = None
    
class LibraryUser(BaseModel):
    """Represents a user from a library provider."""
    id: str
    name: str
    thumb: Optional[str] = None
    source_provider: str

class MediaType(enum.Enum):
    MOVIE = "movie"
    TV = "tv"

class Suggestion(BaseModel):
    title: str = Field(description="The title of the media.")
    description: str = Field(description="Description of the media.")
    similarity: str = Field(description="A short summary of how this media relates to the request.")
    mediaType: MediaType
    rt_url: str = Field(description="Full Rotten Tomatoes URL for the media.")
    rt_score: int = Field(description="Rotten Tomatoes Score for the media.")

class SuggestionList(BaseModel):
    suggestions: List[Suggestion]

# FastAPI/Pydantic Models 
class WatchHistoryCreateRequest(BaseModel):
    title: str
    media_id: Optional[str] = None
    media_type: str  # 'movie' or 'tv'
    watched_by: str
    last_played_date: Optional[str] = None # ISO 8601 string
    source: Optional[str] = None
    poster_url_source: Optional[str] = None # Original URL of the poster

# Constants
DEFAULT_PROMPT_TEMPLATE = "Recommend {{limit}} tv series or movies similar to {{media_name}}. \n\nExclude the following media from your recommendations: {{all_media}}"
DEFAULT_PROMPT_RESEARCH_TEMPLATE = """Please provide an in-depth analysis of {{media_name}}. Use the following markdown template as a basis for your research.

# Movie/TV Series Analysis

**Title:** [Insert Movie/TV Series Title Here] 

**Director(s):** [Insert Director(s) Here] 

**Writer(s):** [Insert Writer(s) Here] 

**Year of Release:** [Insert Year Here] 

**Genre(s):** [Insert Genre(s) Here, e.g., Sci-Fi, Drama, Comedy, Thriller]

## I. Core Elements
### Theme(s)
What are the central ideas or messages the story explores? (e.g., redemption, loss, coming-of-age, the corrupting influence of power, the nature of good vs. evil, family bonds).
Are there multiple layers to the themes? How are they presented?

### Vibe/Atmosphere
What is the overall feeling or mood of the movie/series? (e.g., suspenseful, whimsical, gritty, romantic, melancholic, hopeful).
How is this vibe established and maintained throughout? Consider pacing, music, and visual elements.

## II. Narrative & Plot
### Plot Summary (Brief)
Provide a concise overview of the main story arc without giving away major spoilers.
### Plot Twists/Surprises
Were there any significant plot twists or unexpected turns?
How effective were they? Did they feel earned or contrived?
How did they impact your understanding of the story or characters?

## III. Characters & Relationships
### Character Progression/Development
Choose 1-3 main characters. How do they change, grow, or regress throughout the story?
What are their motivations, flaws, and strengths?
Are their transformations believable?

### Key Relationships (and Love)
Analyze the significant relationships (romantic, platonic, familial, adversarial).
How do these relationships evolve? What conflicts or harmonies exist within them?
If love is a central element, how is it portrayed? Is it healthy, toxic, realistic, idealistic?

## IV. Artistic & Technical Aspects
### Artistic Styling/Aesthetics
Comment on the visual style, cinematography, and production design.
Are there recurring visual motifs or a distinct color palette?
How do these elements contribute to the storytelling or atmosphere?

### Sound Design & Music
How is sound used to enhance the experience? (e.g., ambient noise, sound effects).
Discuss the original score and/or soundtrack. How does it complement the scenes and themes?

### Pacing & Structure
How does the story unfold? Is it fast-paced, slow-burn, episodic?
Is the narrative linear, or does it utilize flashbacks/flashforwards? How effective is the chosen structure?

## V. Deeper Meaning & Impact
### Moral of the Story/Key Takeaways
What deeper insights or lessons can be drawn from the narrative?
Does the story leave you with a particular message or call to action?

### Cultural Significance/Impact
Does the movie/series reflect or comment on any societal issues or cultural trends?
Has it had a significant impact on popular culture or the genre?

### Personal Reflection
What was your overall impression of the movie/series?
What did you like or dislike?
Did it challenge your perspectives or evoke strong emotions?

## VI. Overall Rating
### Recommendation
Would you recommend this movie/series to others? Why or why not?
### Rating: [e.g., 1-10]
What would you rate this movie/series on a 1-10 scale?
"""