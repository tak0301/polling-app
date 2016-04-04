import sys
import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):

    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))

class Question(Base):

    __tablename__ = 'question'

    id = Column(Integer, primary_key = True)
    title = Column(String(80))
    question_text = Column(String(250))
    pub_date = Column(DateTime, default=datetime.datetime.utcnow)
    poll_image = Column(String(80), default="noPic")
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)


class Choice(Base):

    __tablename__ = 'choice'

    id = Column(Integer, primary_key = True)
    choice_text = Column(String(250))
    votes = Column(Integer, default=0)
    rank = Column(Integer, default=0)
    q_id = Column(Integer, ForeignKey('question.id'))
    question = relationship(Question)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)



engine = create_engine('sqlite:///pollearning.db')
Base.metadata.create_all(engine)
