from flask import Blueprint, make_response, request
from google.cloud import datastore
import json
from json2html import *
import constants
import functions

client = datastore.Client()

bp = Blueprint('weapons', __name__, url_prefix='/weapons')

@bp.route('', methods=['POST','GET','PUT','PATCH','DELETE'])
def weapons_get_post():
    # create a new weapon
    if request.method == 'POST':
        # validate headers
        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)

        content = request.get_json() 
        
        # validate input
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        elif ('name' in content and 'type' in content and 'level' in content):
            if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                return functions.error_response('Invalid name', 400)
            if not isinstance(content['type'], str) or len(content['type']) > 255 or not content['type'].isprintable():
                return functions.error_response('Invalid type', 400)
            if not (isinstance(content['level'], int)) or content['level'] < 0:
                return functions.error_response('Invalid level', 400)

            # check weapon name for uniqueness
            query = client.query(kind=constants.weapons)
            results = list(query.fetch())
            for element in results:
                if element['name'] == content['name']:
                    return functions.error_response('There is already a weapon with that name', 403)
            
            # add data to datastore
            new_weapon = datastore.entity.Entity(key=client.key(constants.weapons))
            new_weapon.update({'name': content['name'], 'type': content['type'], 
            'level': content['level'], 'carrier': None})
            client.put(new_weapon)
            new_weapon['id'] = new_weapon.key.id
            new_weapon['self'] = constants.base_url + '/weapons/' + str(new_weapon.key.id)

            # create response
            res = make_response(json.dumps(new_weapon))
            res.mimetype = 'application/json'
            res.status_code = 201
            return res

        else:  
            return functions.error_response('The request object is missing at least one of the required attributes', 400)

    # get weapons
    elif request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)

        num_query = client.query(kind=constants.weapons)
        num_results = len(list(num_query.fetch()))

        query = client.query(kind=constants.weapons)

        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        l_iterator = query.fetch(limit= q_limit, offset=q_offset)
        pages = l_iterator.pages
        results = list(next(pages))
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None

        for element in results:
            element['id'] = element.key.id
            element['self'] = constants.base_url + '/weapons/' + str(element.key.id)
            if element['carrier'] is not None:
                character_key = client.key(constants.characters, element['carrier'])
                character = client.get(key=character_key)
                element['carrier'] = {'id': element['carrier'], 'name': character['name'], 'self': constants.base_url + '/characters/' + str(character.key.id)}
            
        output = {'total number of weapons': num_results, 'weapons': results}
        if next_url:
            output['next'] = next_url

        # create response
        res = make_response(json.dumps(output))
        res.mimetype = 'application/json'
        res.status_code = 200
        return res

    else:
        res = functions.error_response('Method not recognized', 405)
        res.headers.set('Allow', 'GET, POST')
        return res

@bp.route('/<id>', methods=['PUT','PATCH','DELETE','GET','POST'])
def weapons_id_put_patch_delete_get(id):
    if request.method == 'DELETE':
        weapon_key = client.key(constants.weapons, int(id))
        weapon = client.get(key=weapon_key)
        if weapon is not None:
            # remove weapon info from relevant characters
            if weapon['carrier'] is not None:
                carrier_character_key = client.key(constants.characters, int(weapon['carrier']))
                carrier_character = client.get(key=carrier_character_key)
                if int(id) in carrier_character['weapons']:
                    carrier_character['weapons'].remove(int(id))
                    client.put(carrier_character)
            client.delete(weapon_key)
            return ('', 204)
        else: 
            return functions.error_response('No weapon with this weapon_id exists', 403)
    
    elif request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes and 'text/html' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        weapon_key = client.key(constants.weapons, int(id))
        weapon = client.get(key=weapon_key)
        if weapon is not None:
            if weapon['carrier'] is not None:
                character_key = client.key(constants.characters, weapon['carrier'])
                character = client.get(key=character_key)
                weapon['carrier'] = {'id': weapon['carrier'], 'name': character['name'], 'self': constants.base_url + '/characters/' + str(character.key.id)}

            weapon['id'] = weapon.key.id
            weapon['self'] = constants.base_url + '/weapons/' + str(weapon.key.id)

            # create response
            if 'application/json' in request.accept_mimetypes:
                res = make_response(json.dumps(weapon))
                res.mimetype = 'application/json'
                res.status_code = 200
                return res
            elif 'text/html' in request.accept_mimetypes:
                res = make_response(json2html.convert(json = json.dumps(weapon)))
                res.mimetype = 'text/html'
                res.status_code = 200
                return res

        else:
            return functions.error_response('No weapon with this weapon_id exists', 404)
    
    elif request.method == 'PUT':
        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        content = request.get_json()
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        if ('name' in content and 'type' in content and 'level' in content):
            # validate input values
            if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                return functions.error_response('Invalid name', 400)
            if not isinstance(content['type'], str) or len(content['type']) > 255 or not content['type'].isprintable():
                return functions.error_response('Invalid class', 400)
            if not isinstance(content['level'], int) or content['level'] < 0:
                return functions.error_response('Invalid level', 400)

            # check for name uniqueness
            query = client.query(kind=constants.weapons)
            results = list(query.fetch())
            for e in results:
                if e['name'] == content['name'] and e.key.id != int(id):
                    return functions.error_response('There is already a weapon with that name', 403)

            # update the weapon
            weapon_key = client.key(constants.weapons, int(id))
            weapon = client.get(key=weapon_key)
            if weapon is not None:
                weapon.update({'name': content['name'], 'type': content['type'], 'level': content['level']})
                client.put(weapon)
                weapon['id'] = weapon.key.id
                weapon['self'] = constants.base_url + '/weapons/' + str(weapon.key.id)

                # make response
                res = make_response(json.dumps(weapon))
                res.mimetype = 'application/json'
                res.status_code = 200
                return res
            else:
                return functions.error_response('No weapon with this weapon_id exists', 404)
        else:
            return functions.error_response('The request object is missing at least one of the required attributes', 400)
    
    elif request.method  == 'PATCH':
        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        content = request.get_json()
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        for key in content:
            if key != 'name' and key != 'type' and key != 'level':
                return functions.error_response('The request object contains at least one extraneous attribute', 400)
        weapon_key = client.key(constants.weapons, int(id))
        weapon = client.get(key=weapon_key)
        if weapon is not None:
            if 'name' in content:
                if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                    return functions.error_response('Invalid name', 400)
                # check for name uniqueness
                query = client.query(kind=constants.characters)
                results = list(query.fetch())
                for e in results:
                    if e['name'] == content['name'] and e.key.id != int(id):
                        return functions.error_response('There is already a character with that name', 403)
                weapon['name'] = content['name']
            if 'type' in content:
                if not isinstance(content['type'], str) or len(content['type']) > 255 or not content['type'].isprintable():
                    return functions.error_response('Invalid type', 400)
                weapon['type'] = content['type']
            if 'level' in content:
                if not isinstance(content['level'], int) or content['level'] < 0:
                    return functions.error_response('Invalid length', 400)
                weapon['level'] = content['level']
            client.put(weapon)
            weapon['id'] = weapon.key.id
            weapon['self'] = constants.base_url + '/weapons/' + str(weapon.key.id)
            
            # make response
            res = make_response(json.dumps(weapon))
            res.mimetype = 'application/json'
            res.status_code = 200
            return res
        else:
            return functions.error_response('No weapon with this weapon_id exists', 404)

    else:
        return functions.error_response('Method not recognized', 405)