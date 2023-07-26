from flask import Flask, render_template, redirect, url_for, jsonify, request
from flask_wtf import FlaskForm
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from wtforms import StringField, SubmitField, BooleanField, DecimalField
from wtforms.validators import DataRequired, URL, NumberRange
from decimal import Decimal
import random
import json
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", 'sqlite:///cafes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
db = SQLAlchemy(app)
cafe_column_names = ["Cafe Name", "Maps URL", "Image", "Location", "Seats", "Toilets",
                     "Wi-Fi", "Power Sockets", "Can Take Calls", "Coffee Price"]
with open("documentation.json", mode="r") as file:
    documentation = json.load(file)


def format_field_value(value):
    if type(value) == Decimal:
        return "£ " + "{:.2f}".format(float(value))
    return value


def boolify(string):
    if string == 'True':
        return True
    elif string == 'False':
        return False
    return string


class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    map_url = db.Column(db.String(500), nullable=False)
    img_url = db.Column(db.String(500), nullable=False)
    location = db.Column(db.String(250), nullable=False)
    seats = db.Column(db.String(250), nullable=False)
    has_toilet = db.Column(db.Boolean, nullable=False)
    has_wifi = db.Column(db.Boolean, nullable=False)
    has_sockets = db.Column(db.Boolean, nullable=False)
    can_take_calls = db.Column(db.Boolean, nullable=False)
    coffee_price = db.Column(db.String(250), nullable=True)


class AddCafeForm(FlaskForm):
    name = StringField(label="Cafe Name", validators=[DataRequired()])
    map_url = StringField(label="Map URL", validators=[DataRequired(), URL()])
    img_url = StringField(label="Image URL", validators=[DataRequired(), URL()])
    location = StringField(label="Location", validators=[DataRequired()])
    seats = StringField(label="Seats", validators=[DataRequired()])
    has_toilet = BooleanField(label="Toilets")
    has_wifi = BooleanField(label="Wi-Fi")
    has_sockets = BooleanField(label="Power Sockets")
    can_take_calls = BooleanField(label="Can take calls")
    coffee_price = DecimalField(label="Coffee Price (£)", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField(label='Add')


table_columns_names = Cafe.__table__.columns.keys()[1:]

with app.app_context():
        db.create_all()


@app.route('/')
def home():
    cafes = Cafe.query.all()
    return render_template("index.html",
                           cafe_list=cafes,
                           cafe_columns=table_columns_names,
                           display_names=cafe_column_names)


@app.route('/add', methods=["GET", "POST"])
def add_cafe():
    add_form = AddCafeForm()
    if add_form.validate_on_submit():
        cafe_entries = {field_name: format_field_value(value) for field_name, value in add_form.data.items()
                        if field_name not in ("submit", "csrf_token")}
        new_cafe = Cafe(**cafe_entries)
        db.session.add(new_cafe)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("add.html", form=add_form)


@app.route("/cafe/random")
def random_cafe():
    rd_cafe = random.choice(db.session.query(Cafe).all())
    json_file = jsonify(cafe={f"{column.name}": getattr(rd_cafe, column.name) for column in rd_cafe.__table__.columns})
    return json_file


@app.route("/cafe/all")
def all_cafes():
    all_cafes_list = db.session.query(Cafe).all()
    json_file = jsonify(cafes=[{f"{column.name}": getattr(cafe, column.name) for column in cafe.__table__.columns}
                               for cafe in all_cafes_list])
    return json_file


@app.route("/cafe/search")
def search_cafe():
    location = request.args.get('loc')
    if location is None:
        return jsonify(error="missing query parameter", message="'loc' parameter is missing"), 400
    loc_cafes = db.session.query(Cafe).filter_by(location=location).all()
    if len(loc_cafes) == 0:
        json_file = jsonify(error="not found", message="no cafe in such location was found in the database."), 404
    else:
        json_file = jsonify(
            cafes=[{f"{column.name}": getattr(cafe, column.name) for column in cafe.__table__.columns}
                   for cafe in loc_cafes])
    return json_file


@app.route("/cafe/add", methods=["POST"])
def add_new_cafe():
    data_params = [pair[0] for pair in request.form.items()]
    bool_param_names = ['has_toilet', 'has_sockets', 'has_wifi', 'can_take_calls']
    non_bool_params = []
    for param in bool_param_names:
        if request.form.get(param) is None:
            pass
        elif not isinstance(boolify(request.form.get(param).title()), bool):
            non_bool_params.append("'" + param + "'")
    if non_bool_params:
        return jsonify(error='invalid value',
                       message=f"the parameter(s) {' ,'.join(non_bool_params)} must be boolean"), 400
    url_params = ['img_url', 'map_url']
    not_a_url = []
    for param in url_params:
        input_url_param = request.form.get(param)
        if request.form.get(param) is None:
            pass
        elif "http" not in input_url_param.lower():
            not_a_url.append("'" + param + "'")
    if not_a_url:
        return jsonify(error="invalid value",
                       message=f"the parameter(s) {' ,'.join(not_a_url)} must be a website URL."), 400
    try:
        if float(request.form.get('coffee_price')) < 0:
            raise ValueError
        cafe_data = {param: "£ " + "{:.2f}".format(float(value)) if param == "coffee_price"
                     else boolify(value.title()) if param in bool_param_names else value
                     for param, value in request.form.items()}
        new_cafe = Cafe(**cafe_data)
        db.session.add(new_cafe)
        db.session.commit()
    except exc.IntegrityError as e:
        db.session.rollback()
        if "UNIQUE" in str(e.orig):
            error = "invalid value for 'name'"
            message = f"a cafe with the 'name' '{request.form.get('name')}' already exists."
        else:
            missing_params = ["'" + param + "'" for param in table_columns_names if param not in data_params]
            error = 'missing parameters'
            message = f'the parameter(s) {", ".join(missing_params)} is(are) required to add a new cafe.'
        return jsonify(error=error, message=message), 400
    except TypeError:
        db.session.rollback()
        missing_params = ["'" + param + "'" for param in table_columns_names if param not in data_params]
        incorrect_params = ["'" + param + "'" for param in data_params if param not in table_columns_names]
        return jsonify(error='incorrect parameters',
                       message=f'The parameter(s) {" ,".join(missing_params)} is(are) expected, '
                               f'but received {" ,".join(incorrect_params)} instead.'), 400
    except ValueError:
        return jsonify(error='invalid value',
                       message=f"The parameter 'coffee_price' must be a positive number, "
                               f"but received '{request.form.get('coffee_price')}' instead."), 400
    else:
        json_file = jsonify(response={"success": "Successfully added the new cafe."})
        return json_file, 200


@app.route("/cafe/update-price/<int:cafe_id>", methods=["PATCH"])
def update_price(cafe_id):
    try:
        new_price = request.args.get('new_price')
        if new_price is None:
            return jsonify(error="missing query parameter", message="'new_price' parameter is missing"), 400
        new_price = float(new_price)
        if new_price < 0:
            raise ValueError
    except ValueError:
        return jsonify(error='incorrect value',
                       message=f"The parameter 'new_price' must be a positive number, "
                               f"but received '{request.args.get('new_price')}' instead."), 400
    cafe_price_update = db.session.get(Cafe, cafe_id)
    if cafe_price_update:
        cafe_price_update.coffee_price = new_price
        db.session.commit()
        json_file = jsonify(success="Successfully updated the price.")
        return json_file
    else:
        return jsonify(error="not found", message="a cafe with that id was not found in the database."), 404


@app.route('/cafe/report-closed/<int:cafe_id>', methods=["DELETE"])
def delete_cafe(cafe_id):
    if request.args.get('api-key') == "fwjMpyXFAYP7H8RhkkAavdFPK9rgfC2Q":
        cafe_to_del = db.session.get(Cafe, cafe_id)
        if cafe_to_del:
            db.session.delete(cafe_to_del)
            db.session.commit()
            return jsonify(success="this cafe was successfully deleted.")
        else:
            return jsonify(error="not found", message="a cafe with that id was not found in the database."), 404
    else:
        return jsonify(error="unauthorized request", message="make sure you have the correct api-key."), 403


@app.route("/documentation")
def api_doc():
    return render_template("api.html", methods=documentation)


if __name__ == "__main__":
    app.run()
