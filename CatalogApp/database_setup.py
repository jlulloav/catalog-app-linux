from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy import UniqueConstraint

Base = declarative_base()


class User(Base):
    """Store user information"""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(Text, nullable=False)

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'name': self.name,
            'email': self.email,
            'picture': self.picture,
            'id': self.id
        }


class Category(Base):
    """Store category information"""
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    items = relationship("Item", cascade="all,delete", backref="category")

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'name': self.name,
            'id': self.id,
            'items': [item.serialize for item in self.items]
        }


class Item(Base):
    """Store item information"""
    __tablename__ = 'item'

    id = Column(Integer, primary_key=True)
    title = Column(String(80), nullable=False)
    description = Column(String(250))
    category_id = Column(Integer, ForeignKey('category.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    UniqueConstraint('category_id', 'title')

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'title': self.title,
            'description': self.description,
            'id': self.id
        }


engine = create_engine('postgresql://catalog:catalog2015@localhost/catalog')

Base.metadata.create_all(engine)
