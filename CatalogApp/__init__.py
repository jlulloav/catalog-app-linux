from flask import Flask, render_template, request, redirect, jsonify, url_for, \
    flash
from sqlalchemy import create_engine, asc, func
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('/var/www/CatalogApp/CatalogApp/client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Catalog Application"


# Connect to Database and create database session
engine = create_engine('postgresql://catalog:catalog2015@localhost/catalog')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# # Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('/var/www/CatalogApp/CatalogApp/fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('/var/www/CatalogApp/CatalogApp/fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/' \
          'oauth/access_token?grant_type=fb_exchange_token&client_id=%s' \
          '&client_secret=%s&fb_exchange_token=%s' \
          % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.4/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order
    # to properly logout, let's strip out the information
    # before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/' \
          'picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;' \
              '-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
        facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('/var/www/CatalogApp/CatalogApp/client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: ' \
              '150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;">'
    flash("You are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# User Helper Functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
        'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def isCreatorLogged(creator_id):
    return 'username' in login_session and 'user_id' in login_session \
           and creator_id == login_session['user_id']


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# JSON APIs to view Catalog Information
@app.route('/catalog/<string:category_name>/JSON')
def categoryItemsJSON(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    items = session.query(Item).filter_by(
        category_id=category.id).all()
    return jsonify(items=[i.serialize for i in items])


@app.route('/catalog/<string:category_name>/<string:item_title>/JSON')
def itemJSON(category_name, item_title):
    item = session.query(Item).filter_by(title=item_title).one()
    return jsonify(item=item.serialize)


@app.route('/catalog/JSON')
def categoriesJSON():
    categories = session.query(Category).all()
    return jsonify(categories=[c.serialize for c in categories])


# Show all categories
@app.route('/')
@app.route('/catalog/')
def showCategories():
    categories = session.query(Category).order_by(asc(Category.name))
    user_id = getLoggedUserId()
    return render_template('categories.html', categories=categories,
                           user_id=user_id)


def getLoggedUserId():
    user_id = -1
    if 'user_id' in login_session:
        user_id = login_session['user_id']
    return user_id


# Create a new category
@app.route('/catalog/new/', methods=['GET', 'POST'])
def newCategory():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        category_name = request.form['name']

        if category_name:
            categories = session.query(Category).filter(
                func.lower(Category.name) == func.lower(category_name)).all()

            if categories == []:
                newCategory = Category(
                    name=category_name, user_id=login_session['user_id'])
                session.add(newCategory)
                flash('New Category %s Successfully Created' % newCategory.name)
                session.commit()
                return redirect(url_for('showCategories'))
            else:
                flash('Category %s already exist!' % category_name)
        else:
            flash('Category name is required.')

    return render_template('newCategory.html')


# Edit a category
@app.route('/catalog/<string:category_name>/edit/', methods=['GET', 'POST'])
def editCategory(category_name):
    if 'username' not in login_session:
        return redirect('/login')

    editedCategory = session.query(
        Category).filter_by(name=category_name).one()

    if editedCategory.user_id != login_session['user_id']:
        return render_template('notAllowed.html',
                               message='You are not authorized to edit '
                                       'this category. Please create your '
                                       'own category in order to edit.')

    if request.method == 'POST':
        new_category_name = request.form['name']

        if new_category_name:
            categories = session.query(Category).filter(
                func.lower(Category.name) == func.lower(
                    new_category_name)).all()

            if categories == [] or new_category_name == category_name:
                editedCategory.name = new_category_name
                session.commit()
                flash('Category Successfully Edited %s' % editedCategory.name)
                return redirect(url_for('showCategories'))
            else:
                flash('Category %s already exist!' % category_name)
        else:
            flash('Category name is required.')

    return render_template('editCategory.html',
                           category_name=editedCategory.name)


# Delete a category
@app.route('/catalog/<string:category_name>/delete/', methods=['GET', 'POST'])
def deleteCategory(category_name):
    if 'username' not in login_session:
        return redirect('/login')

    categoryToDelete = session.query(
        Category).filter_by(name=category_name).one()

    if categoryToDelete.user_id != login_session['user_id']:
        return render_template('notAllowed.html',
                               message='You are not authorized to delete '
                                       'this category. Please create your '
                                       'own category in order to delete.')

    if request.method == 'POST':
        session.delete(categoryToDelete)
        flash('%s Successfully Deleted' % categoryToDelete.name)
        session.commit()
        return redirect(url_for('showCategories'))
    else:
        return render_template('deleteCategory.html',
                               category_name=categoryToDelete.name)


# Show item
@app.route('/catalog/<string:category_name>/<string:item_title>/')
def showItemDetail(category_name, item_title):
    category = session.query(Category).filter_by(name=category_name).one()
    creator = getUserInfo(category.user_id)
    item = session.query(Item).filter_by(
        title=item_title).one()
    is_option_visible = isCreatorLogged(creator.id)
    return render_template('itemDetail.html', item=item,
                           category_name=category.name,
                           is_option_visible=is_option_visible)


# Show list of items
@app.route('/catalog/<string:category_name>/')
@app.route('/catalog/<string:category_name>/items/')
def showItems(category_name):
    category = session.query(Category).filter_by(name=category_name).one()
    creator = getUserInfo(category.user_id)
    items = session.query(Item).filter_by(
        category_id=category.id).all()
    is_option_visible = isCreatorLogged(creator.id)
    return render_template('items.html', items=items, category=category,
                           is_option_visible=is_option_visible)


# Create a new item
@app.route('/catalog/<string:category_name>/new/', methods=['GET', 'POST'])
def newItem(category_name):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(name=category_name).one()

    if request.method == 'POST':
        item_title = request.form['title']

        if item_title:
            items = session.query(Item).filter(
                func.lower(Item.title) == func.lower(
                    item_title) and Item.category_id == category.id).all()

            if items == []:
                newItem = Item(title=item_title,
                               description=request.form['description'],
                               category_id=category.id,
                               user_id=category.user_id)
                session.add(newItem)
                session.commit()
                flash('New %s Item Successfully Created' % (newItem.title))
                return redirect(
                    url_for('showItems', category_name=category.name))
            else:
                flash('Item %s already exist!' % item_title)
        else:
            flash('Item title is required.')

    return render_template('newItem.html', category_name=category.name)


# Edit an item
@app.route('/catalog/<string:category_name>/<string:item_title>/edit/',
           methods=['GET', 'POST'])
def editItem(category_name, item_title):
    if 'username' not in login_session:
        return redirect('/login')
    categories = session.query(Category).order_by(asc(Category.name))
    category = session.query(Category).filter_by(name=category_name).one()
    editedItem = session.query(Item).filter_by(title=item_title,
                                               category_id=category.id).one()

    if editedItem.user_id != login_session['user_id']:
        return render_template('notAllowed.html',
                               message='You are not authorized to edit '
                                       'this item. Please create your own '
                                       'item in order to edit.')

    if request.method == 'POST':
        new_item_title = request.form['title']

        if item_title:
            items = session.query(Item).filter(
                func.lower(Item.title) == func.lower(
                    new_item_title) and Item.category_id == category.id).all()

            if items == [] or new_item_title == item_title:
                editedItem.title = new_item_title
                editedItem.description = request.form['description']
                editedItem.category_id = request.form['category']
                session.add(editedItem)
                session.commit()
                flash('Item Successfully Edited')
                return redirect(
                    url_for('showItems', category_name=category_name))
            else:
                flash('Item %s already exist!' % item_title)
        else:
            flash('Item title is required.')

    return render_template('editItem.html', category_name=category_name,
                           item_title=editedItem.title,
                           item=editedItem, categories=categories)


# Delete an item
@app.route('/catalog/<string:category_name>/<string:item_title>/delete/',
           methods=['GET', 'POST'])
def deleteItem(category_name, item_title):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(name=category_name).one()
    itemToDelete = session.query(Item).filter_by(title=item_title,
                                                 category_id=category.id).one()

    if itemToDelete.user_id != login_session['user_id']:
        return render_template('notAllowed.html',
                               message='You are not authorized to delete'
                                       ' this item. Please create your '
                                       'own item in order to delete.')

    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Item Successfully Deleted')
        return redirect(url_for('showItems', category_name=category_name))
    else:
        return render_template('deleteItem.html', category_name=category_name,
                               item_title=itemToDelete.title)


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showCategories'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCategories'))


if __name__ == '__main__':
    app.run()
