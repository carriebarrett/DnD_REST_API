import json
from json2html import *
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen
from google.cloud import datastore
import constants
import functions
# from authlib.integrations.flask_client import OAuth
from flask import Blueprint, Flask, redirect, render_template, session, url_for, request, make_response, jsonify, _request_ctx_stack
from jose import jwt
from os import environ as env

client = datastore.Client()

bp = Blueprint('characters', __name__, url_prefix='/characters')

@bp.route('', methods=['POST','GET','PUT','PATCH','DELETE'])
def characters_get_post():
    # create a new character
    if request.method == 'POST':
        # verify authorization
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)

        # validate headers
        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)

        content = request.get_json() 
        
        # validate input
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        elif ('name' in content and 'class' in content and 'level' in content):
            if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                return functions.error_response('Invalid name', 400)
            if not isinstance(content['class'], str) or len(content['class']) > 255 or not content['class'].isprintable():
                return functions.error_response('Invalid class', 400)
            if not (isinstance(content['level'], int)) or content['level'] < 0:
                return functions.error_response('Invalid level', 400)

            # check character name for uniqueness
            query = client.query(kind=constants.characters)
            results = list(query.fetch())
            for element in results:
                if element['name'] == content['name']:
                    return functions.error_response('There is already a character with that name', 403)
            
            # add data to datastore
            new_character = datastore.entity.Entity(key=client.key(constants.characters))
            new_character.update({'name': content['name'], 'class': content['class'], 
            'level': content['level'], 'weapons': [], 'user': payload['sub']})
            client.put(new_character)
            new_character['id'] = new_character.key.id
            new_character['self'] = constants.base_url + '/characters/' + str(new_character.key.id)

            # create response
            res = make_response(json.dumps(new_character))
            res.mimetype = 'application/json'
            res.status_code = 201
            return res

        else:  
            return functions.error_response('The request object is missing at least one of the required attributes', 400)

    # get characters
    elif request.method == 'GET':
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)

        # verify authorization
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)
        num_query = client.query(kind=constants.characters)
        num_query.add_filter('user', '=', payload['sub'])
        num_results = len(list(num_query.fetch()))

        query = client.query(kind=constants.characters)
        query.add_filter('user', '=', payload['sub'])

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
            element['self'] = constants.base_url + '/characters/' + str(element.key.id)
            new_weapons_list = []
            for weapon_id in element['weapons']:
                weapon_key = client.key(constants.weapons, int(weapon_id))
                weapon = client.get(key=weapon_key)
                new_weapon = {"name": weapon["name"], "id": weapon.key.id, "self": constants.base_url + '/weapons/' + str(weapon.key.id)}
                new_weapons_list.append(new_weapon)
            element['weapons'] = new_weapons_list

        output = {'total number of user characters': num_results, 'characters': results}
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
def characters_id_put_patch_delete_get(id):
    if request.method == 'DELETE':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)

        character_key = client.key(constants.characters, int(id))
        character = client.get(key=character_key)
        if character is not None:
            if character['user'] == payload['sub']:
                client.delete(character_key)

                # remove character info from relevant weapons
                weapons_list = character['weapons']
                for weapon_id in weapons_list:
                    weapon_key = client.key(constants.weapons, int(weapon_id))
                    weapon = client.get(key=weapon_key)
                    weapon['carrier'] = None
                    client.put(weapon)
                return ('', 204)
            else:
                return functions.error_response('Not authorized to access a character with that character_id', 403)
        else: 
            return functions.error_response('No character with this character_id exists', 403)
    
    elif request.method == 'GET':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)

        if 'application/json' not in request.accept_mimetypes and 'text/html' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        character_key = client.key(constants.characters, int(id))
        character = client.get(key=character_key)
        if character is not None:
            if character['user'] == payload['sub']:
                new_weapons_list = []
                for weapon_id in character['weapons']:
                    weapon_key = client.key(constants.weapons, int(weapon_id))
                    weapon = client.get(key=weapon_key)
                    new_weapon = {"name": weapon["name"], "id": weapon.key.id, "self": constants.base_url + '/weapons/' + str(weapon.key.id)}
                    new_weapons_list.append(new_weapon)
                character['weapons'] = new_weapons_list

                character['id'] = character.key.id
                character['self'] = constants.base_url + '/characters/' + str(character.key.id)

                # create response
                if 'application/json' in request.accept_mimetypes:
                    res = make_response(json.dumps(character))
                    res.mimetype = 'application/json'
                    res.status_code = 200
                    return res
                elif 'text/html' in request.accept_mimetypes:
                    res = make_response(json2html.convert(json = json.dumps(character)))
                    res.mimetype = 'text/html'
                    res.status_code = 200
                    return res
            else:
                return functions.error_response('Not authorized to access a character with that character_id', 403)
        else:
            return functions.error_response('No character with this character_id exists', 404)
    
    elif request.method == 'PUT':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)

        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        content = request.get_json()
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        if ('name' in content and 'class' in content and 'level' in content):
            # validate input values
            if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                return functions.error_response('Invalid name', 400)
            if not isinstance(content['class'], str) or len(content['class']) > 255 or not content['class'].isprintable():
                return functions.error_response('Invalid class', 400)
            if not isinstance(content['level'], int) or content['level'] < 0:
                return functions.error_response('Invalid level', 400)

            # check for name uniqueness
            query = client.query(kind=constants.characters)
            results = list(query.fetch())
            for e in results:
                if e['name'] == content['name'] and e.key.id != int(id):
                    return functions.error_response('There is already a character with that name', 403)

            # update the character
            character_key = client.key(constants.characters, int(id))
            character = client.get(key=character_key)
            if character is not None:
                if character['user'] == payload['sub']:
                    character.update({'name': content['name'], 'class': content['class'], 'level': content['level']})
                    client.put(character)
                    character['id'] = character.key.id
                    character['self'] = constants.base_url + '/characters/' + str(character.key.id)

                    # make response
                    res = make_response(json.dumps(character))
                    res.mimetype = 'application/json'
                    res.status_code = 200
                    return res
            else:
                return functions.error_response('No character with this character_id exists', 404)
        else:
            return functions.error_response('The request object is missing at least one of the required attributes', 400)
    
    elif request.method  == 'PATCH':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)

        if request.headers['Content-Type'] != 'application/json':
            return functions.error_response('Invalid Content-Type', 415)
        if 'application/json' not in request.accept_mimetypes:
            return functions.error_response('Invalid Accept', 406)
        content = request.get_json()
        if len(content) > 3:
            return functions.error_response('The request object contains at least one extraneous attribute', 400)
        for key in content:
            if key != 'name' and key != 'class' and key != 'level':
                return functions.error_response('The request object contains at least one extraneous attribute', 400)
        character_key = client.key(constants.characters, int(id))
        character = client.get(key=character_key)
        if character is not None:
            if 'name' in content:
                if not isinstance(content['name'], str) or len(content['name']) > 255 or not content['name'].isprintable():
                    return functions.error_response('Invalid name', 400)
                # check for name uniqueness
                query = client.query(kind=constants.characters)
                results = list(query.fetch())
                for e in results:
                    if e['name'] == content['name'] and e.key.id != int(id):
                        return functions.error_response('There is already a character with that name', 403)
                character['name'] = content['name']
            if 'class' in content:
                if not isinstance(content['class'], str) or len(content['class']) > 255 or not content['class'].isprintable():
                    return functions.error_response('Invalid type', 400)
                character['class'] = content['class']
            if 'level' in content:
                if not isinstance(content['level'], int) or content['level'] < 0:
                    return functions.error_response('Invalid length', 400)
                character['level'] = content['level']
            client.put(character)
            character['id'] = character.key.id
            character['self'] = constants.base_url + '/characters/' + str(character.key.id)
            
            # make response
            res = make_response(json.dumps(character))
            res.mimetype = 'application/json'
            res.status_code = 200
            return res
        else:
            return functions.error_response('No character with this character_id exists', 404)

    else:
        return functions.error_response('Method not recognized', 405)

@bp.route('/<character_id>/weapons/<weapon_id>', methods=['PUT','PATCH','DELETE','GET','POST'])
def add_delete_weapon(character_id, weapon_id):
    if request.method == 'PUT':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)
 
        character_key = client.key(constants.characters, int(character_id))
        character = client.get(key=character_key)
        weapon_key = client.key(constants.weapons, int(weapon_id))
        weapon = client.get(key=weapon_key)
        if character is not None and weapon is not None:
            # check authorization for this character
            if character['user'] == payload['sub']:
                # make sure the weapon is not already in use by another character
                if weapon['carrier'] is not None:
                    return functions.error_response("The weapon is already in use by a character", 403)
                # add the weapon to the character 
                if 'weapons' in character.keys():
                    character['weapons'].append(weapon.id)
                else:
                    character['weapons'] = [weapon.id]
                client.put(character)
                # add the carrier on the weapon
                weapon.update({"name": weapon["name"], "carrier": int(character_id), "type": weapon["type"], "level": weapon["level"]})
                client.put(weapon)

                return('',204)
            else: 
                return functions.error_response('Not authorized to access a character with that character_id', 403)
        else:
            return functions.error_response("The specified character and/or weapon does not exist", 404)
    
    if request.method == 'DELETE':
        payload = functions.verify_jwt(request)
        if isinstance(payload, int):
            return functions.error_response('Missing or invalid authorization', payload)
 
        character_key = client.key(constants.characters, int(character_id))
        character = client.get(key=character_key)
        if character is not None:
            if character['user'] == payload['sub']:
                if int(weapon_id) in character['weapons']:
                    # remove weapon from character
                    character['weapons'].remove(int(weapon_id))
                    client.put(character)
                    # remove carrier from weapon
                    weapon_key = client.key(constants.weapons, int(weapon_id))
                    weapon = client.get(key=weapon_key)
                    weapon['carrier'] = None
                    client.put(weapon)
                    return('',204)
                else: 
                    return functions.error_response("No character with this character_id is carrying a weapon with this weapon_id", 404)
            else: 
                return functions.error_response('Not authorized to access a character with that character_id', 403)
        else:
            return functions.error_response("No character with this character_id is carrying a weapon with this weapon_id", 404)
    
    else:
        return functions.error_response('Method not recognized', 405)