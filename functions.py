import json
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen
from google.cloud import datastore
import constants
# from authlib.integrations.flask_client import OAuth
from flask import Blueprint, Flask, redirect, render_template, session, url_for, request, make_response, jsonify, _request_ctx_stack
from jose import jwt
from os import environ as env

# Create a response for an error message
def error_response(error_message, error_code):
    res = make_response(json.dumps({'Error': error_message}))
    res.mimetype = 'application/json'
    res.status_code = error_code
    return res

# Verify the JWT in the request's Authorization header
def verify_jwt(request):
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        token = auth_header[1]
    else:
        return 401
    jsonurl = urlopen("https://"+ constants.DOMAIN +"/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        return 401
    if unverified_header["alg"] == "HS256":
        return 401
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=constants.ALGORITHMS,
                audience=constants.CLIENT_ID,
                issuer="https://"+ constants.DOMAIN +"/"
            )
        except jwt.ExpiredSignatureError:
            return 401
        except jwt.JWTClaimsError:
            return 401
        except Exception:
            return 401
        return payload
    else:
        return 401