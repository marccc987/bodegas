from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: str = Field(primary_key=True)  # X user ID
    username: str = Field(index=True)
    display_name: str = ""
    bio: str = ""
    location: str = ""
    followers_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    created_at: Optional[datetime] = None
    is_verified: bool = False
    has_avatar: bool = False
    has_bio: bool = False
    profile_url: str = ""
    avatar_url: str = ""

    # Computed fields
    bot_score: Optional[float] = None
    bot_label: Optional[str] = None  # "bot", "suspicious", "human"
    community_id: Optional[int] = None

    # Metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    is_seed: bool = False


class Tweet(SQLModel, table=True):
    __tablename__ = "tweets"

    id: str = Field(primary_key=True)  # Tweet ID
    author_id: str = Field(index=True, foreign_key="accounts.id")
    text: str = ""
    created_at: Optional[datetime] = None
    language: str = ""
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    is_retweet: bool = False
    is_reply: bool = False
    is_quote: bool = False
    in_reply_to_user_id: Optional[str] = None
    retweeted_tweet_id: Optional[str] = None

    collected_at: datetime = Field(default_factory=datetime.utcnow)


class Relationship(SQLModel, table=True):
    __tablename__ = "relationships"

    source_id: str = Field(primary_key=True, foreign_key="accounts.id")
    target_id: str = Field(primary_key=True, foreign_key="accounts.id")
    relationship_type: str = Field(primary_key=True)  # follows, retweet, mention, reply, quote
    weight: int = 1
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)


class CollectionJob(SQLModel, table=True):
    __tablename__ = "collection_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_type: str  # "profile_lookup", "csv_import"
    target: str = ""  # e.g. batch identifier or filename
    status: str = "pending"  # pending, running, completed, failed
    items_collected: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
