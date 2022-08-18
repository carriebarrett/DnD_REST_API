from flask import Blueprint, make_response, request
from google.cloud import datastore
import json
import constants
import functions

client = datastore.Client()

bp = Blueprint('users', __name__, url_prefix='/users')
@bp.route('', methods=['POST','GET','PUT','PATCH','DELETE'])
def users_get_post():
    # get all users   
    if request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        for e in results:
            e['id'] = e.key.id

        # create response
        res = make_response(json.dumps(results))
        res.mimetype = 'application/json'
        res.status_code = 200
        return res

    elif request.method == 'POST':
        # create a new user
        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        content = request.get_json()
        if len(content) >  2:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        elif ('name' in content and 'sub' in content):
            # validate input
            if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                return functions.error_response('Invalid name', 400)
            if not isinstance(content['sub'], str) or len(content['sub']) > 255 or not content['sub'].isprintable():
                return functions.error_response('Invalid sub', 400)
           
            # check sub for uniqueness
            query = client.query(kind=constants.users)
            results = list(query.fetch())
            for e in results:
                if e['sub'] == content['sub']:
                    return functions.error_response('There is already a user with that sub', 403)
            # add data to datastore
            new_user = datastore.entity.Entity(key=client.key(constants.users))
            new_user.update({'name': content['name'], 'sub': content['sub']})
            client.put(new_user)
            new_user['id'] = new_user.key.id
            new_user['self'] = constants.base_url + '/users/' + str(new_user.key.id)
            
            # create response
            res = make_response(json.dumps(new_user))
            res.mimetype = 'application/json'
            res.status_code = 201
            return res
        else:
            return functions.error_response('The request object is missing at least one of the required attributes', 400)

    else:
        res = functions.error_response('Method not recognized', 405)
        res.headers.set('Allow', 'GET, POST')
        return res