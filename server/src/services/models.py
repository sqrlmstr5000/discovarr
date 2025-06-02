from peewee import *
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, List, Any 

# Peewee

database = SqliteDatabase(None)  # Will be initialized with path later

class BaseModel(Model):
    class Meta:
        database = database

class Settings(BaseModel):
    group = CharField(null=False)
    name = CharField(null=False)
    value = CharField(null=True)
    type = CharField(null=True)  # STRING, INTEGER, BOOLEAN, or URL
    description = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = (
            # Unique together constraint on group and name
            (('group', 'name'), True),
        )

class Search(BaseModel):
    name = CharField(null=False) 
    prompt = TextField(null=False)
    kwargs = CharField(null=True)  # JSON string for dict of kwargs
    last_run_date = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.now)

class SearchStat(BaseModel):
    search = ForeignKeyField(Search, backref='stats', on_delete='CASCADE', null=True)
    prompt_token_count = IntegerField(default=0)
    candidates_token_count = IntegerField(default=0)
    thoughts_token_count = IntegerField(default=0)
    total_token_count = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

class Media(BaseModel):
    title = CharField(null=False)
    source_title = CharField(null=True)
    description = TextField(null=True)
    similarity = TextField(null=True)
    media_type = CharField(null=False)
    tmdb_id = CharField(null=True)
    rt_url = CharField(null=True)
    rt_score = IntegerField(null=True)
    poster_url = CharField(null=True)
    media_status = CharField(null=True) # e.g., Rumored, Planned, In Production, Post Production, Released, Canceled
    release_date = DateField(null=True)
    networks = TextField(null=True) 
    genres = TextField(null=True) 
    original_language = CharField(null=True) # e.g., 'en', 'ja'
    ignore = BooleanField(default=False)
    search = ForeignKeyField(Search, backref='media', null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class WatchHistory(BaseModel):
    title = CharField(null=False)
    id = CharField(null=False)
    media_type = CharField(null=False)
    watched_by = CharField(null=False)
    last_played_date = DateTimeField(null=False)
    processed = BooleanField(default=False)
    processed_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Schedule(BaseModel):
    search = ForeignKeyField(Search, backref='schedules', null=True)
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

class Migrations(BaseModel):
    version = IntegerField()
    applied_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'migrations'

MODELS = [Media, WatchHistory, Search, SearchStat, Schedule, Migrations, Settings]

# Application Models

@dataclass
class ItemsFiltered:
    """Represents a filtered recently watched media item."""
    name: str
    id: Optional[str]
    type: Optional[str] # 'movie' or 'tv'
    last_played_date: Optional[str] # ISO 8601 str
    play_count: Optional[int] = None  
    is_favorite: Optional[bool] = None  
