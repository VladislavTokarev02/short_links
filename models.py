from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)  # Хеш пароля

    # Связь с таблицей Link
    links = relationship("Link", back_populates="owner")


class Link(Base):
    __tablename__ = 'links'

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(Text, nullable=False)
    short_code = Column(Text, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    click_count = Column(Integer, default=0)  # Убедитесь, что по умолчанию 0
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'))

    # Связь с пользователем
    owner = relationship("User", back_populates="links")

