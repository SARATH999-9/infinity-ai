import json
from datetime import datetime
from sqlalchemy import create_engine, inspect, text, ForeignKey, String, Text, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    plan: Mapped[str] = mapped_column(String(10), default="free")
    plan_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversations: Mapped[list["Conversation"]] = relationship(cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)  # paise
    status: Mapped[str] = mapped_column(String(12), default="created")  # created | paid
    payment_id: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(80), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    messages: Mapped[list["Message"]] = relationship(
        cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))            # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of data: URLs
    files: Mapped[str] = mapped_column(Text, default="[]")   # JSON list of file names
    ctx: Mapped[str] = mapped_column(Text, default="")       # text of attached files
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "imgs": json.loads(self.images or "[]"),
            "files": json.loads(self.files or "[]"),
        }


def init_db():
    Base.metadata.create_all(engine)
    # upgrade databases created by older versions (adds the new columns, keeps all data)
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    add = {
        "name": "VARCHAR(80) DEFAULT ''",
        "plan": "VARCHAR(10) DEFAULT 'free'",
        "plan_until": "TIMESTAMP",
    }
    with engine.begin() as conn:
        for col, ddl in add.items():
            if col not in cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))


def is_pro(u: "User") -> bool:
    return bool(u.plan == "pro" and u.plan_until and u.plan_until > datetime.utcnow())


def plan_info(u: "User") -> dict:
    pro = is_pro(u)
    return {"plan": "pro" if pro else "free", "plan_until": (u.plan_until.isoformat() + "Z") if pro else None}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()