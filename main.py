import characters
import users
import weapons
import constants
import functions
from authlib.integrations.flask_client import OAuth

import json
from urllib.parse import quote_plus, urlencode
from flask import Flask, redirect, render_template, session, url_for, request
from os import environ as env

app = Flask(__name__)
app.register_blueprint(characters.bp)
app.register_blueprint(users.bp)
app.register_blueprint(weapons.bp)
app.secret_key = constants.APP_SECRET_KEY

oauth = OAuth(app)

oauth.register(
    'auth0',
    client_id = constants.CLIENT_ID,
    client_secret = constants.CLIENT_SECRET,
    client_kwargs = {
        'scope': 'openid profile email',
    },
    server_metadata_url=f'https://{(constants.DOMAIN)}/.well-known/openid-configuration',
)

@app.route('/')
def home():
    return render_template(
        'home.html',
        session=session.get('user'),
        pretty=json.dumps(session.get('user'), indent=4),
    )

@app.route('/callback', methods=['GET', 'POST'])
def callback():
    token = oauth.auth0.authorize_access_token()
    session['user'] = token
    return redirect('/')


@app.route('/login')
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for('callback', _external=True)
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(
        'https://'
        + constants.DOMAIN
        + '/v2/logout?'
        + urlencode(
            {
                'returnTo': url_for('home', _external=True),
                'client_id': constants.CLIENT_ID,
            },
            quote_via=quote_plus,
        )
    )

# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = functions.verify_jwt(request)
    if isinstance(payload, int):
        return ('', payload)
    else:
        return payload 

if __name__ == '__main__':
    app.run(host='127.0.0.1',  port=8080, debug=True)
