from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
app = Flask(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Question, Choice

from flask import session as login_session
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///pollearning.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

import decimal
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

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
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
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
        response = make_response(json.dumps('Current user is already connected.'),
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
    output += ' " style = "width: 200px; height: 200px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

@app.route('/gdisconnect')
def gdisconnect():
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = login_session.get('credentials')
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('home'))
    else:
    	response = make_response(json.dumps('Failed to revoke token for given user.', 400))
    	response.headers['Content-Type'] = 'application/json'
    	return response


@app.route('/')
def home():
    if 'username' not in login_session:
        return render_template('home.html')
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template('homePrivate.html', creator=creator)

@app.route('/polls/')
def showPolls():
    polls = session.query(Question).all()
    if 'username' not in login_session:
        return render_template('showPolls.html', polls=polls)
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template('showPollsPrivate.html', polls=polls, creator=creator)

@app.route('/polls/new/', methods=['GET', 'POST'])
def newPoll():
    creator = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newPoll = Question(title=request.form['pollTitle'], question_text=request.form['pollQuestion'], user_id=login_session['user_id'])
        session.add(newPoll)
        session.commit()
        return redirect(url_for('newImage', poll_id=newPoll.id))
    else:
        return render_template('newPoll.html', creator=creator)

@app.route('/polls/new/<int:poll_id>/image/', methods=['GET', 'POST'])
def newImage(poll_id):
    creator = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    poll = session.query(Question).filter_by(id=poll_id).one()
    if request.method == 'POST':
        target = os.path.join(APP_ROOT, 'static/')
        for file in request.files.getlist("pollImage"):
            filename = file.filename
            filename = str(poll_id) + ".jpg"
            destination = "/".join([target, filename])
            file.save(destination)
            poll.poll_image = filename
            session.add(poll)
            session.commit()
        return redirect(url_for('newChoices', poll_id=poll.id))
    else:
        return render_template('newImage.html', poll=poll, creator=creator)

@app.route('/polls/new/<int:poll_id>/choices/', methods=['GET', 'POST'])
def newChoices(poll_id):
    creator = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    poll = session.query(Question).filter_by(id=poll_id).one()
    if request.method == 'POST':
        if request.form['choiceTitle1']:
            newChoice = Choice(choice_text=request.form['choiceTitle1'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle2']:
            newChoice = Choice(choice_text=request.form['choiceTitle2'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle3']:
            newChoice = Choice(choice_text=request.form['choiceTitle3'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle4']:
            newChoice = Choice(choice_text=request.form['choiceTitle4'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle5']:
            newChoice = Choice(choice_text=request.form['choiceTitle5'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle6']:
            newChoice = Choice(choice_text=request.form['choiceTitle6'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle7']:
            newChoice = Choice(choice_text=request.form['choiceTitle7'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle8']:
            newChoice = Choice(choice_text=request.form['choiceTitle8'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle9']:
            newChoice = Choice(choice_text=request.form['choiceTitle9'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        if request.form['choiceTitle10']:
            newChoice = Choice(choice_text=request.form['choiceTitle10'], q_id=poll_id, user_id=poll.user_id)
            session.add(newChoice)
            session.commit()
        return redirect(url_for('singlePoll', poll_id=poll.id))
    else:
        return render_template('newChoices.html', poll=poll, creator=creator)

@app.route('/polls/<int:poll_id>/', methods=['GET', 'POST'])
def singlePoll(poll_id):
    creator = getUserInfo(login_session['user_id'])
    poll = session.query(Question).filter_by(id=poll_id).one()
    choices = session.query(Choice).filter_by(q_id=poll_id).order_by(Choice.votes.desc()).all()
    count = 1
    total_votes = 0
    for choice in choices:
        choice.rank = count
        session.add(choice)
        session.commit()
        count = count + 1
        decimal.getcontext().prec=4
        total_votes = decimal.Decimal(total_votes) + decimal.Decimal(int(choice.votes))
    if request.method == 'POST':
        for choice in choices:
            if request.form['choiceVote'] == str(choice.id):
                choice = session.query(Choice).filter_by(id=choice.id).one()
                choice.votes = int(choice.votes) + 1
                session.add(choice)
                session.commit()
        choices2 = session.query(Choice).filter_by(q_id=poll_id).order_by(Choice.votes.desc()).all()
        pieVotes = []
        pieLabels = []
        pieColors = []
        explode = []
        counter = 1
        for choice in choices2:
            if choice.votes > 0:
                pieVotes.append(choice.votes)
                pieLabels.append(choice.choice_text)
                if counter == 1:
                    explode.append(0.1)
                    pieColors.append('#4C6CB4')
                if counter == 2:
                    explode.append(0)
                    pieColors.append('#d9593d')
                if counter == 3:
                    explode.append(0)
                    pieColors.append('#54B44C')
                if counter == 4:
                    explode.append(0)
                    pieColors.append('#D7BE54')
                if counter == 5:
                    explode.append(0)
                    pieColors.append('#F2E8B4')
                if counter == 6:
                    explode.append(0)
                    pieColors.append('#D93D6E')
                if counter == 7:
                    explode.append(0)
                    pieColors.append('#3DBCD9')
                if counter == 8:
                    explode.append(0)
                    pieColors.append('#76A19A')
                if counter == 9:
                    explode.append(0)
                    pieColors.append('#A68D60')
                if counter == 10:
                    explode.append(0)
                    pieColors.append('#B0C5BB')
            counter = counter + 1
        total_votes = total_votes + 1
        plt.clf()
        plt.pie(pieVotes, explode=explode, labels=pieLabels, colors=pieColors, autopct='%.2f%%', shadow=True)
        plt.axis('equal')
        plt.savefig("static/pie%s%s" % (poll.id, total_votes))
        count = 1
        for choice in choices2:
            choice.rank = count
            session.add(choice)
            session.commit()
            count = count + 1
        if 'username' not in login_session:
            return render_template('singlePoll.html', poll=poll, choices=choices2, total_votes=total_votes)
        if poll.user_id != login_session['user_id']:
            return render_template('singlePollLoggedIn.html', poll=poll, choices=choices2, total_votes=total_votes, creator=creator)
        else:
            return render_template('singlePollPrivate.html', poll=poll, choices=choices2, total_votes=total_votes, creator=creator)
    else:
        if 'username' not in login_session:
            return render_template('singlePoll.html', poll=poll, choices=choices, total_votes=total_votes)
        if poll.user_id != login_session['user_id']:
            return render_template('singlePollLoggedIn.html', poll=poll, choices=choices, total_votes=total_votes, creator=creator)
        else:
            return render_template('singlePollPrivate.html', poll=poll, choices=choices, total_votes=total_votes, creator=creator)


@app.route('/polls/<int:poll_id>/edit/', methods=['GET', 'POST'])
def editPoll(poll_id):
    creator = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    poll = session.query(Question).filter_by(id=poll_id).one()
    choices = session.query(Choice).filter_by(q_id=poll_id).all()
    total_votes = 0
    for choice in choices:
        total_votes = total_votes + int(choice.votes)
    if request.method == 'POST':
        if request.form['pollTitle']:
            poll.title = request.form['pollTitle']
            session.add(poll)
            session.commit()
        if request.form['pollQuestion']:
            poll.question_text = request.form['pollQuestion']
            session.add(poll)
            session.commit()
        for choice in choices:
            if request.form['choiceTitle%s' % choice.id]:
                choice.choice_text = request.form['choiceTitle%s' % choice.id]
                session.add(choice)
                session.commit()
        if request.form['newChoiceTitle1']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle1'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle2']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle2'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle3']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle3'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle4']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle4'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle5']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle5'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle6']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle6'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle7']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle7'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle8']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle8'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle9']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle9'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        if request.form['newChoiceTitle10']:
            newChoice = Choice(choice_text=request.form['newChoiceTitle10'], q_id=poll_id)
            session.add(newChoice)
            session.commit()
        return redirect(url_for('singlePoll', poll_id=poll.id))
    else:
        return render_template('editPoll.html', poll=poll, choices=choices, total_votes=total_votes, creator=creator)

@app.route('/polls/<int:poll_id>/delete/', methods=['GET', 'POST'])
def deletePoll(poll_id):
    creator = getUserInfo(login_session['user_id'])
    if 'username' not in login_session:
        return redirect('/login')
    poll = session.query(Question).filter_by(id=poll_id).one()
    choices = session.query(Choice).filter_by(q_id=poll_id).all()
    if request.method == 'POST':
        session.delete(poll)
        session.commit()
        for choice in choices:
            session.delete(choice)
            session.commit()
        return redirect(url_for('showPolls'))
    else:
        return render_template('deletePoll.html', poll=poll, creator=creator)



if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host = '0.0.0.0')
