from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Category, Base, Item, User

engine = create_engine('postgresql://catalog:catalog2015@localhost/catalog')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Create dummy user
User1 = User(name="John Doe", email="johndoe@gmail.com",
             picture='data:image/jpeg;base64,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')
session.add(User1)
session.commit()

# Soccer category
category1 = Category(user_id=1, name="Soccer")

session.add(category1)
session.commit()

item1 = Item(user_id=1, title="Jersey", description="Nice Jersey",
             category=category1)

session.add(item1)
session.commit()

item2 = Item(user_id=1, title="Soccer Cleats", description="Red soccer cleats",
             category=category1)

session.add(item2)
session.commit()

# Baseball category
category2 = Category(user_id=1, name="Baseball")

session.add(category2)
session.commit()

item1 = Item(user_id=1, title="Bat", description="Kid bat",
             category=category2)

session.add(item1)
session.commit()

item1 = Item(user_id=1, title="Glove",
             description="Wilson sporting glove", category=category2)

session.add(item1)
session.commit()

# Hockey category
category3 = Category(user_id=1, name="Hockey")

session.add(category3)
session.commit()

item1 = Item(user_id=1, title="Stick", description="Canadian pro stick",
             category=category3)

session.add(item1)
session.commit()

print "DB ready!"
