import jwt
import uuid
import datetime
from functools import wraps
from flask import request
from flask import jsonify
from flask import make_response

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from src.config import app
from src.models import UserModel, TodoModel
from src.models import db
from src.schemas import UserSchema, TodoSchema

''' Schemas '''
user_schema = UserSchema()
users_schema = UserSchema(many=True)
todo_schema = TodoSchema()
todos_schema = TodoSchema(many=True)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'status': 'x-access-token is missing'}), 401
        try:

            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = UserModel.query.filter_by(
                username=data['username']).first()
        except Exception:
            return jsonify({'status': 'x-access-token is invalid'}), 401

        return f(current_user, *args, **kwargs)

    return decorated

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'Online'})

""" User API """
@app.route('/user', methods=['POST'])
def create_user():
    ''' Create new user in Database '''
    username = request.json['username'].lower()
    password = request.json['password']

    user = UserModel.query.filter_by(username=username).first()
    if user is None:
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = UserModel(public_id=str(
            uuid.uuid4().hex), username=username, password=hashed_password, admin=False)
        db.session.add(new_user)
        db.session.commit()
        return user_schema.jsonify(new_user)

    return jsonify({'status': f'{username} is already in database'})


@app.route('/user', methods=['GET'])
@token_required
def get_all_users(current_user):
    ''' get all users from database '''
    if not current_user.admin:
        return jsonify({'status':  'You are not an admin.'})
    users = UserModel.query.all()
    result = users_schema.dump(users)
    return jsonify(result)


@app.route('/user/<username>', methods=['GET'])
@token_required
def get_user_by_username(current_user, username):
    ''' get user by username '''
    if not current_user.admin:
        return jsonify({'status': 'You are not an admin.'})

    user = UserModel.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'Status': f'There is no user by {username}'})

    return user_schema.jsonify(user)


@app.route('/user/<username>', methods=['PUT'])
@token_required
def promote_demote_user(current_user, username):
    ''' promote admin status or change password '''
    if not current_user.admin:
        return jsonify({'status':  'You are not an admin.'})

    admin = request.json['admin']

    user = UserModel.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'Status': f'There is no user by {username}'})

    user.admin = admin
    db.session.commit()
    return user_schema.jsonify(user)


@app.route('/user/<username>', methods=['DELETE'])
@token_required
def delete_user(current_user, username):
    ''' Delete the user records from database '''
    if not current_user.admin:
        return jsonify({'status':  'You are not an admin.'})

    username = request.json['username'].lower()

    user = UserModel.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'Status': f'There is no user by {username}'})

    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': f'{username} got deleted from db'})


@app.route('/login')
def login():
    ''' generate the jwt token using HTTPBasicAuth '''
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response('could not verify !', 401, {'WWW-Authenticate': 'Basic realm="Login Required!'})

    user = UserModel.query.filter_by(username=auth.username).first()

    if not user:
        return make_response('could not verify !', 401, {'WWW-Authenticate': 'Basic realm="Login Required!'})

    if check_password_hash(user.password, auth.password):
        token = jwt.encode({'username': user.username},
                           app.config['SECRET_KEY'])
        return jsonify({'token': token.decode('UTF-8')})

    return make_response('could not verify !', 401, {'WWW-Authenticate': 'Basic realm="Login Required!'})

""" Todo API """
@app.route('/todo', methods=['POST'])
@token_required
def create_todo(current_user):
    ''' create new todo '''
    todo_name = request.json["todo_name"].lower()
    author = current_user.username

    todo = TodoModel.query.filter_by(todo_name=todo_name).first()

    if todo is None:
        new_todo = TodoModel(todo_name=todo_name, is_complete=False, author=author)

        db.session.add(new_todo)
        db.session.commit()

        return todo_schema.jsonify(new_todo)

@app.route('/todo', methods=['GET'])
@token_required
def get_all_todos(current_user):
    ''' get all todos list '''
    todos = TodoModel.query.filter_by(author=current_user.username).all()
    result = todos_schema.dump(todos)

    return jsonify(result)

@app.route('/todo/<todo_id>', methods=['GET'])
@token_required
def get_one_todo(current_user, todo_id):
    """ get todo by id """
    todo = TodoModel.query.filter_by(todo_id=todo_id, author=current_user.username).first()

    if todo is None:
        return jsonify({'Status': 'There is no todo'})

    return todo_schema.jsonify(todo)

@app.route('/todo/<todo_id>', methods=['PUT'])
@token_required
def update_complete(current_user, todo_id):
    ''' update the todo by id '''
    is_complete = request.json['is_complete']

    todo = TodoModel.query.filter_by(todo_id=todo_id, author=current_user.username).first()
    if not todo:
        return jsonify({'Status': f'There is no user by {todo}'})

    todo.is_complete = is_complete
    db.session.commit()

    return jsonify({"status": "Todo has been completed"})

@app.route('/todo/<todo_id>', methods=['DELETE'])
@token_required
def delete_todo(current_user, todo_id):
    ''' delete todo record by id '''
    todo = TodoModel.query.filter_by(todo_id=todo_id, author=current_user.username).first()

    if todo is None:
        return jsonify({'status': 'Invalid todo Id'})

    db.session.delete(todo)
    db.session.commit()

    return jsonify({'status': f"{todo.todo_name} deleted from db"})
